# Project 2.3 — Append-Only Pipeline with Chicago Crime

> **Guided Project** from Phase 2 of the DE Playbook.
> Concepts: append-only ingest, record hashing, deduplication, idempotency, immutable audit logs, at-least-once vs. exactly-once.

📖 **Line-by-line walkthrough: [EXPLANATION.md](EXPLANATION.md).**

## What this project builds

An **append-only** crime-record ingest that is **provably idempotent**. Consecutive source batches deliberately *overlap* (the source re-sends recent records), so a naive `INSERT` would double-count. **Record hashing** makes re-ingesting the same records a guaranteed no-op, and a **separate immutable audit log** records exactly what every run did.

```
batch CSV -> hash each record -> dedup within batch -> anti-join vs stored hashes
                                                            |
                                            insert only NEW records (append-only)
                                                            |
                                            append one row to the immutable audit log
```

## How to run

```bash
python generate_sample_data.py                     # 3 overlapping batches (3000 rows, 2600 unique)
python crime_ingest.py --batch crime_batch_1.csv   # inserts 1000
python crime_ingest.py --batch crime_batch_1.csv   # re-run -> inserts 0 (idempotent)
python crime_ingest.py --batch crime_batch_2.csv   # inserts only the 800 new records
python crime_ingest.py --batch crime_batch_3.csv   # -> 2600 unique total
pytest test_crime_ingest.py -v                      # 7 tests
```

## Design decisions

### 1. Record hashing defines identity
`generate_record_hash()` computes an MD5 over `ID | Date | Primary Type` — the fields that make a record *that* crime. Two rows with the same fingerprint are the same event, even if delivered in different batches. The `'|'` separator prevents collisions like `('12','34')` vs `('1','234')`.

### 2. The dedup happens in three places
- **within the batch** — `drop_duplicates` on the hash (a single batch can repeat a record);
- **against history** — an anti-join `~batch.isin(existing_hashes)` keeps only never-seen records;
- **at the schema** — `record_hash` is the table's PRIMARY KEY, a last-line guarantee.

### 3. Append-only, never mutate
The `crimes` table is only ever `INSERT`ed into — no `UPDATE`, no `DELETE`. Each row carries an `ingested_at` audit timestamp. This is the immutable-log pattern: the raw record of what happened is preserved exactly.

### 4. The audit log is separate and immutable
`ingest_audit` is a *different* table that gets one appended row per run (batch name, rows in / inserted / skipped, status). It is **never** updated or deleted — even a run that inserts 0 records is logged. Keeping the audit log separate from the data means you can answer "what did the 3pm run do?" without touching the data itself.

### 5. Exactly-once *outcome* from at-least-once *delivery*
The source may send the same record any number of times (at-least-once delivery — normal and unavoidable). Because the *processing* is idempotent (hash dedup), the final state is exactly one copy — an **exactly-once outcome without exactly-once delivery**. `test_at_least_once_delivery_three_times` proves it: feed a batch 3×, get one copy.

## Proof it works (from the run above)

| Step | Rows in batch | Inserted | Skipped (dupe) | Table total |
|---|---|---|---|---|
| batch 1 | 1000 | 1000 | 0 | 1000 |
| batch 1 (re-run) | 1000 | **0** | 1000 | 1000 |
| batch 2 (overlaps 801–1000) | 1000 | 800 | 200 | 1800 |
| batch 3 (overlaps 1601–1800) | 1000 | 800 | 200 | **2600** |

3,000 rows delivered → 2,600 unique stored. The overlap is deduplicated exactly.

## Deliverables checklist

- [x] Append-only ingest with deduplication (`crime_ingest.py`)
- [x] Record-hash fingerprinting (`generate_record_hash`)
- [x] Immutable ingest audit log (`ingest_audit` table)
- [x] Idempotent run script + tests (`test_crime_ingest.py`, 7 tests)
