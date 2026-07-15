# Project 2.1 — Incremental ETL with NYC Taxi

> **Guided Project** from Phase 2 of the DE Playbook.
> Concepts: chunked extraction, watermark-based incremental loading, partitioned Parquet, retry/backoff, idempotency, lookback windows.

📖 **Line-by-line walkthrough: [EXPLANATION.md](EXPLANATION.md).**

## What this project builds

A `TaxiETL` class that ingests NYC-taxi-style trip records **incrementally** — loading only rows newer than the last successful run — using a **watermark** stored in a control table. Output is Hive-style **partitioned Parquet** (`year=/month=`), and the whole thing is safe to retry.

```
extract (chunked)  ->  transform (features + outlier filter)  ->  load (partitioned, dedup)
                              ^                                          |
                              |          watermark control table         |
                              +---- read watermark ... advance only after success
```

## How to run

```bash
python generate_sample_data.py                          # 2 batches (old + new)
python taxi_etl.py                                       # loads batch 1
python taxi_etl.py                                       # re-run -> 0 net new (idempotent)
python taxi_etl.py --source data/raw/taxi_batch_2.csv    # loads only the new rows
python benchmark.py                                      # full vs incremental timing
pytest test_taxi_etl.py -v                               # 5 tests
```

## Design decisions

### 1. The watermark golden rule
The watermark (last loaded `updated_at`) is read at the start of a run, and **advanced only *after* every partition writes successfully**. If a load throws, the watermark stays put and the next run reprocesses the failed batch. Advancing *before* the load would mean **silent data loss** on failure. `test_watermark_not_advanced_on_load_failure` proves this.

### 2. Chunked extraction
`pd.read_csv(chunksize=500_000)` streams the source in fixed-size chunks, so memory stays flat whether the file is 40 K rows or 40 M. You never hold the whole file at once.

### 3. Outlier filtering maps to real failure modes
| Filter | Bound | Real-world cause it catches |
|---|---|---|
| `trip_distance` | 0.05–200 mi | GPS glitches (0-mile or 999-mile trips) |
| `fare_amount` | 0.01–1000 | data-entry errors (negative/zero fares) |
| `trip_duration_min` | 0.5–300 | clock skew (dropoff before pickup) |

The generator injects ~4% of exactly these, and the transform drops ~5–6% per batch.

### 4. Partitioned Parquet, idempotent by dedup-on-write
Rows are routed to `year=YYYY/month=MM/data.parquet`. Each partition write reads the existing partition, concatenates the new rows, and **drops duplicates on `trip_id`** before rewriting. This is the "partition overwrite" idempotency technique — re-loading the same rows can never create duplicates.

### 5. Lookback window for late-arriving data
The cutoff is `watermark − 1h`, not the exact watermark, so rows that arrive slightly late (event time before the watermark but ingested after) are still picked up. This deliberately **re-scans a small window on every run** — which is only safe *because* the load is idempotent. You saw this in the re-run: 13 rows re-scanned, **0 duplicates created**. That interplay (at-least-once re-scan + idempotent write = effectively-exactly-once) is the key Phase 2 mental model.

### 6. Retry decorator
`@retry(attempts=3)` wraps the partition write with exponential backoff. Transient failures (locks, brief I/O errors) are normal in batch ETL; a single blip shouldn't fail the whole run.

## Deliverables checklist

- [x] ETL class with chunked extraction (`taxi_etl.py`)
- [x] Partitioned Parquet output (`year=/month=`)
- [x] Watermark-based incremental load with control table
- [x] Logging + retry decorator
- [x] Performance benchmark (`benchmark.py`) — incremental ~2.5x faster here, and the gap grows with history
- [x] Tests incl. idempotency + watermark safety (`test_taxi_etl.py`)
