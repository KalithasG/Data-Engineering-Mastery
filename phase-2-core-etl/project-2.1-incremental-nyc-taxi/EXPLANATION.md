# Project 2.1 — Line-by-Line Explanation

Walks through the incremental taxi ETL block by block. After this you'll be ready for **Assignment 2.1 (Chicago Divvy bikeshare incremental loader)** on your own.

**Files covered:** `generate_sample_data.py`, `taxi_etl.py`, `benchmark.py`, `test_taxi_etl.py`.

---

## The problem (read first)

Full reloads cost grows with **total** data size; incremental loading costs grow only with **how much changed**. A pipeline that reprocesses all of history every night works fine at 1 GB and falls over at 1 TB. The watermark pattern is how you load only what's new.

---

## Part A — `generate_sample_data.py`

### Two batches, split by `updated_at`
```python
batch1 = make_trips(N_BATCH_1, WINDOW_START, WINDOW_MID, id_offset=1)
batch2 = make_trips(N_BATCH_2, WINDOW_MID, WINDOW_END, id_offset=1 + N_BATCH_1)
```
Batch 1's `updated_at` values fall in Jan–Mar; batch 2's in Apr–Jun. This split is what lets you *see* incremental loading: load batch 1, and batch 2 is "the new data that arrived later." `id_offset` keeps `trip_id` unique across batches (a stable business key).

### `updated_at` is the watermark column
```python
upd = updated_start + timedelta(seconds=random.uniform(0, span))
pickup = upd - timedelta(minutes=random.uniform(0, 120))
```
`updated_at` is when the source system last touched the row — the column the loader tracks. `pickup` is set slightly *before* it (a trip is recorded shortly after it happens). This is why you'll see a few Dec-2022 partitions: a Jan-1 00:08 `updated_at` can have a pickup at 23:xx on Dec 31. **Partitioning is on event time (pickup), watermarking is on `updated_at` — two different time columns doing two different jobs.** Internalize that distinction.

### Deliberate outliers
```python
df.loc[bad[:third], "fare_amount"] = [-5.0, 0.0, -12.5]     # bad fares
df.loc[..., "trip_distance"] = [0.0, 250.0, 999.9]           # bad distances
df.loc[..., "dropoff_datetime"] = pickup - 1h                # negative duration
```
Three categories of dirt, each matching one transform filter. Without injected dirt you'd never see the filter do anything.

---

## Part B — `taxi_etl.py`

### The `@retry` decorator
```python
def retry(attempts=3, backoff=0.5):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delay = backoff
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    if attempt == attempts:
                        raise
                    time.sleep(delay)
                    delay *= 2
```
A generic retry-with-exponential-backoff wrapper. `delay *= 2` doubles the wait each time (0.5s → 1s → 2s). `@functools.wraps(fn)` preserves the wrapped function's name for logging. It re-raises after the final attempt — retries hide *transient* failures, they must not hide *permanent* ones. Applied to `_write_partition`, the one step most likely to hit a transient I/O error.

### The watermark control table
```python
CREATE TABLE IF NOT EXISTS etl_watermark (
    source_name  VARCHAR PRIMARY KEY,
    watermark    TIMESTAMP,
    updated_at   TIMESTAMP
)
```
The watermark lives in a **persistent control table**, keyed by `source_name` — not hardcoded, not in memory. Keying by source means many feeds can track progress independently. (Assignment 2.1 explicitly requires a control table "not hardcoded" — this is it.)

```python
def get_watermark(self):
    ...
    return pd.Timestamp(row[0]) if row else pd.Timestamp("1970-01-01")
```
"Never loaded" is represented as epoch 0, so the *first* run's `updated_at > epoch` matches everything. No special-casing of the first run.

```python
def set_watermark(self, value):
    INSERT ... ON CONFLICT (source_name) DO UPDATE SET watermark = excluded.watermark
```
An **upsert**: first run inserts, later runs update. This is called *only* from `incremental_load`, and *only* after a successful load.

### `extract` — the generator
```python
def extract(self, source_path):
    for chunk in pd.read_csv(source_path, chunksize=CHUNK_SIZE,
                             parse_dates=[...]):
        yield chunk
```
`chunksize` makes `read_csv` return an *iterator* of DataFrames instead of one giant DataFrame. `yield`ing chunks keeps the whole pipeline streaming — memory is bounded by one chunk, not the file. `parse_dates` casts the timestamp columns at read time so you never do string-to-datetime math later.

### `transform` — features then filters
```python
df["trip_duration_min"] = (df["dropoff_datetime"] - df["pickup_datetime"]).dt.total_seconds() / 60.0
df["year"]  = df["pickup_datetime"].dt.year
df["month"] = df["pickup_datetime"].dt.month
df["hour"]  = df["pickup_datetime"].dt.hour
df["day_of_week"] = df["pickup_datetime"].dt.dayofweek
```
Derived features. `year`/`month` double as **partition columns**; `hour`/`day_of_week` are analytical dimensions. Note `trip_duration_min` is computed *before* filtering because the duration filter depends on it.
```python
df = df[
    df["trip_distance"].between(*DISTANCE_RANGE)
    & df["fare_amount"].between(*FARE_RANGE)
    & df["trip_duration_min"].between(*DURATION_RANGE)
]
```
Boolean-mask filtering. `.between()` is inclusive on both ends. A negative-duration row (dropoff before pickup) yields a negative `trip_duration_min`, which fails `between(0.5, 300)` and is dropped. The log line quantifies exactly how much was dropped — you always want that number visible.

### `_write_partition` — idempotency by dedup-on-write
```python
if part_file.exists():
    existing = pd.read_parquet(part_file)
    combined = pd.concat([existing, df], ignore_index=True)
else:
    combined = df
combined = combined.drop_duplicates(subset=["trip_id"], keep="last")
combined.to_parquet(part_file, index=False)
```
This is the heart of idempotency. Rather than blindly appending (which duplicates on re-run), it reads the current partition, merges, and **dedups on the business key `trip_id`**. `keep="last"` means a reprocessed row overwrites its earlier copy (correct if the row was *updated*). Re-loading the same data → same result. This is the "partition overwrite" technique from Primer 2.3, applied per partition.

### `load` — route to partitions
```python
for (year, month), part in df.groupby(["year", "month"]):
    total = self._write_partition(int(year), int(month), part)
```
`groupby(["year","month"])` splits the batch by partition, and each group is written to its own `year=/month=` folder. This is Hive-style partitioning — the same layout Spark, Athena, and DuckDB all understand natively.

### `incremental_load` — the orchestration (the exam question)
```python
watermark = self.get_watermark()
cutoff = watermark - LOOKBACK
for chunk in self.extract(source_path):
    new_rows = chunk[chunk["updated_at"] > cutoff]
    if new_rows.empty:
        continue
    max_seen = max(max_seen, new_rows["updated_at"].max())
    clean = self.transform(new_rows)
    total_loaded += self.load(clean)

if total_loaded > 0:
    self.set_watermark(max_seen)
```
The ordering is the entire lesson:
1. **Read** the watermark.
2. **Filter** each chunk to `updated_at > cutoff`, where `cutoff = watermark − lookback`. The lookback re-scans the last hour so late-arriving rows aren't missed.
3. **Transform + load** the new rows. Track `max_seen` = the newest `updated_at` actually processed.
4. **Advance** the watermark to `max_seen` — *only after* the loop completed without throwing.

If `load` raises in step 3, execution never reaches step 4, so the watermark is unchanged and the next run retries the same batch. That's **watermark safety**, and it's why the ordering is non-negotiable.

Why advance to `max_seen` (max loaded) and not "now"? Because using wall-clock "now" would skip any source rows whose `updated_at` is between the max you actually read and now — a subtle data-loss bug. Always advance to the max value you *actually processed*.

---

## Part C — `benchmark.py`

Times `incremental` (watermark already past batch 1, so only batch 2 is processed) against `full_reload` (reprocess everything). Incremental was ~2.5x faster here on a tiny dataset — and crucially, the incremental cost is fixed at "one new batch" while the full-reload cost grows every day as history accumulates. On real data the gap is orders of magnitude.

---

## Part D — `test_taxi_etl.py`

- `test_rerun_creates_no_duplicates` — **the idempotency test.** Loads the same source twice; asserts warehouse row count is unchanged and `COUNT(*) - COUNT(DISTINCT trip_id) == 0`. Note it asserts *no duplicates*, not *zero rows re-scanned* — because the lookback intentionally re-scans a little. No-duplicates is the real guarantee.
- `test_watermark_not_advanced_on_load_failure` — monkeypatches `load` to raise, then asserts the watermark is unchanged and nothing was written. This is the crash-safety property in Assignment 2.1 ("simulate crash mid-load; prove watermark is *not* advanced").
- `test_outliers_are_filtered` — feeds one bad-distance and one bad-fare row; asserts only the 2 clean rows survive.

The `isolated_env` fixture `monkeypatch`es `WAREHOUSE_DIR` and `CONTROL_DB` to a `tmp_path`, so tests never touch your real warehouse.

---

## Your Assignment 2.1 checklist, mapped to what you just learned

| Assignment requirement | Where this project taught it |
|---|---|
| Control table tracking last_loaded_timestamp per source (not hardcoded) | `etl_watermark` table, keyed by `source_name` |
| Chunked incremental loading using watermark | `extract()` + `incremental_load()` |
| Prove idempotency: run twice → zero duplicates | `test_rerun_creates_no_duplicates` |
| Simulate crash mid-load; watermark not advanced | `test_watermark_not_advanced_on_load_failure` |
| Lookback window for late-arriving rows | `cutoff = watermark - LOOKBACK` |
| When to switch to true CDC | see below |

**When would you switch to true CDC (Change Data Capture)?** Watermark loading has two blind spots: it **cannot detect deletes** (a row removed at the source just stops appearing — the watermark never notices), and it **adds read load** on the source by polling. Switch to CDC (Debezium, AWS DMS reading the DB transaction log) when you need to capture deletes, need near-real-time latency, or the source can't tolerate repeated large scans. Watermark for batch; CDC for deletes/low-latency. Now go build the Divvy loader.
