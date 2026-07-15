# Project 2.3 — Line-by-Line Explanation

Walks through the append-only crime ingest. After this you'll be ready for **Assignment 2.3 (a provably-idempotent audit pipeline)** on your own.

**Files covered:** `generate_sample_data.py`, `crime_ingest.py`, `test_crime_ingest.py`.

---

## The idea (read first)

In distributed systems, **retries and re-deliveries are normal**, not exceptional. A pipeline that corrupts data every time it's re-run is a pipeline you can never safely retry. **Idempotency** — running N times equals running once — is what makes retries safe. This project achieves it with record hashing.

---

## Part A — `generate_sample_data.py`

### Content must be a function of identity, not position
```python
def build_master(max_id):
    for rid in range(1, max_id + 1):
        rng = random.Random(rid)           # per-ID RNG, seeded by the ID itself
        dt = base + timedelta(hours=rid * 2, minutes=rng.randint(0, 59))
        rows.append({"ID": rid, "Date": dt.strftime(...), ...})
```
This is the single most important detail in the generator, and it was a **real bug in the first draft**. Originally each record's fields depended on its *position within the batch*, so record `ID=801` in batch 1 got a different `Date` than `ID=801` in batch 2 — different `Date` → different hash → the dedup thought they were two different crimes. Only 2 of 200 overlaps were caught.

The fix: seed a per-record RNG with the **ID** (`random.Random(rid)`), so a given ID *always* produces byte-identical fields no matter which batch it lands in. Then overlapping batches contain true duplicates.
```python
b1 = master[master["ID"].between(1, 1000)]
b2 = master[master["ID"].between(801, 1800)]     # ids 801..1000 identical to b1's
```
**Lesson for your own generators:** if you want reproducible "same record re-sent" behaviour, derive content from the stable key, never from row position.

---

## Part B — `crime_ingest.py`

### `generate_record_hash` — the fingerprint
```python
HASH_FIELDS = ["ID", "Date", "Primary Type"]
def generate_record_hash(row):
    key = "|".join(str(row[f]) for f in HASH_FIELDS)
    return hashlib.md5(key.encode()).hexdigest()
```
- **Which fields?** The ones that define record *identity*. `ID` alone might be enough here, but including `Date` + `Primary Type` guards against ID reuse and demonstrates the general pattern (compose a hash from the business-relevant columns).
- **Why the `'|'` separator?** Without it, `ID=12, Date=34...` and `ID=1, Date=234...` could concatenate to the same string. A separator that can't appear in the values prevents such collisions.
- **Why hash at all instead of just comparing IDs?** Hashing generalizes to composite/natural keys and to "has this exact row content changed?" checks — it's the reusable technique.

### The schema — two tables with different rules
```python
CREATE TABLE crimes (record_hash VARCHAR PRIMARY KEY, ..., ingested_at TIMESTAMP)
CREATE TABLE ingest_audit (audit_id, batch_name, ingested_at, rows_in_batch,
                           rows_inserted, rows_skipped, status)
```
- `crimes` is **append-only** and uses `record_hash` as PRIMARY KEY — a database-level guarantee against duplicates.
- `ingest_audit` is a **separate, immutable log**. Keeping it separate is deliberate: the data table holds *what the records are*; the audit table holds *what each run did*. You never mutate either after writing.

### `append_only_load` — the five steps
```python
batch = pd.read_csv(batch_path)
batch["record_hash"] = batch.apply(generate_record_hash, axis=1)      # (1)
batch = batch.drop_duplicates(subset=["record_hash"], keep="first")   # (2)
```
(1) fingerprint every row. (2) dedup *within* the batch — the source might repeat a record inside one file.
```python
existing = set(r[0] for r in con.execute("SELECT record_hash FROM crimes").fetchall())
new = batch[~batch["record_hash"].isin(existing)].copy()              # (3)
new["ingested_at"] = datetime.now()
```
(3) the **anti-join**: `~...isin(existing)` keeps only hashes not already stored. This is the dedup-against-history step. (Loading all existing hashes into a Python `set` is fine at this scale; at billions of rows you'd push the anti-join into SQL — a `LEFT JOIN ... WHERE existing IS NULL` or a `MERGE`.)
```python
con.execute("INSERT INTO crimes SELECT * FROM insert_df")             # (4)
self._write_audit(con, batch_path.name, rows_in_batch,
                  rows_inserted, rows_skipped, "SUCCESS")             # (5)
```
(4) append-only insert of just the new rows. (5) record what happened — **always**, even when `rows_inserted == 0`. An audit log with gaps is worse than useless.

### `_write_audit` — append, never overwrite
```python
next_id = con.execute("SELECT COALESCE(MAX(audit_id), 0) + 1 FROM ingest_audit").fetchone()[0]
con.execute("INSERT INTO ingest_audit VALUES (?, ?, ?, ?, ?, ?, ?)", [...])
```
A monotonic `audit_id` and a plain `INSERT`. There is no code path anywhere that updates or deletes an audit row — that's what "immutable" means in practice.

---

## Part C — `test_crime_ingest.py`

- `test_rerun_inserts_zero` — **the idempotency test.** Load a batch, load it again; assert the second run inserted 0 and the table total is unchanged.
- `test_at_least_once_delivery_three_times` — feed the same batch 3×; assert exactly one copy survives. This is the "exactly-once outcome from at-least-once delivery" proof.
- `test_overlapping_batches_yield_union` — b1 = ids 1–100, b2 = ids 81–180; assert 180 unique (the union), not 200 (the sum). This is the real-world overlap scenario.
- `test_audit_log_is_append_only` — after two runs (one inserting, one all-dupes), assert the audit log has exactly 2 rows with the expected `(inserted, skipped)` counts. Proves even a no-op run is logged and nothing is overwritten.

The `isolated_db` fixture monkeypatches `DB_PATH` and `RAW_DIR` to a `tmp_path`, so tests never touch your real database.

---

## Your Assignment 2.3 checklist, mapped to what you just learned

| Assignment requirement | Where this project taught it |
|---|---|
| Implement all three idempotency techniques (dedup-key upsert, record hashing, partition overwrite) | record hashing here; partition-overwrite in Project 2.1; upsert in Project 1.3 |
| Automated test: full load twice → identical | `test_rerun_inserts_zero` |
| Simulate at-least-once: feed same batch 3× → correct final state | `test_at_least_once_delivery_three_times` |
| Separate immutable audit-log table (timestamp, row count, status) | `ingest_audit` + `_write_audit` |
| Explain why exactly-once processing ≠ exactly-once delivery | see below |

**Exactly-once processing without exactly-once delivery** — the paragraph the assignment asks for, using this pipeline: The Kafka/source layer only promises *at-least-once delivery* — it may hand you the same record several times (a re-send after a missed ack, a replay after a crash). Guaranteeing *exactly-once delivery* across systems is genuinely hard and usually impractical. But we don't need it: because our *processing* is idempotent (the record hash makes a re-delivered record a no-op), the **observable outcome** is exactly one stored copy regardless of how many times it was delivered. Idempotent processing turns cheap, reliable at-least-once delivery into an exactly-once *result*. That reframe — "make the effect idempotent instead of making delivery perfect" — is one of the most important mental models in distributed data. For your assignment you'll add the other two techniques (upsert + partition overwrite) on different data slices and document when each fits. Now go build it.
