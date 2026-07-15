# Project 2.1 — Framing Questions (ask these BEFORE you build)

> **Step 0 of the learning loop.** Answers point back to `README.md` / `EXPLANATION.md`.

Dataset: **NYC taxi trip records**, delivered as **two batches** (an old batch and a later "new" batch).

---

### Q1. What is this dataset?
One row per taxi trip: pickup/dropoff timestamps, passenger count, distance, fare, plus an **`updated_at`** column (when the source last touched the row) that drives incremental loading.

### Q2. Why not just reload everything each run?
Full-reload cost grows with **total** history, not with **how much changed**. At scale that stops working. The question this project answers: *how do you load only what's new since last time?*

### Q3. What is the watermark, and what's the golden rule?
The **watermark** is the max `updated_at` successfully loaded so far, kept in a control table. Golden rule: **advance it only *after* a load succeeds** — advancing first means silent data loss on failure.

### Q4. What do we expect to be *wrong* / tricky?
- **Outliers**: negative/zero fares, 0- or 999-mile trips, dropoff-before-pickup (negative duration). Each maps to a filter.
- **Late-arriving rows**: an `updated_at` slightly behind the watermark → needs a **lookback window**.
- **Two different time columns**: partition on **event time (pickup)**, watermark on **`updated_at`** — don't conflate them.

### Q5. What's the target output/shape?
Hive-style **partitioned Parquet** (`year=/month=`), written idempotently (dedup on `trip_id`), plus a watermark control table, retry/backoff, and a full-vs-incremental benchmark.

### Q6. Key decisions to reason through
- **Watermark column**: `updated_at` timestamp vs. auto-increment id vs. partition-date? (Trade-offs: does the source update the column on every change?)
- **Chunk size**: how big a read chunk keeps memory flat?
- **Idempotency mechanism**: strict `>` watermark, or dedup-on-write, or partition overwrite?
- **Lookback length**: long enough to catch late rows, short enough to stay cheap.

### Q7. Gotchas
- Advancing the watermark to wall-clock "now" instead of "max value actually loaded" skips rows in between.
- A lookback window re-scans rows every run → only safe **because** the load is idempotent (at-least-once re-scan + idempotent write = exactly-once outcome).
- Watermark loading **cannot detect deletes** and adds read-load on the source — know when to switch to CDC.

---

➡️ Read [README.md](README.md) / [EXPLANATION.md](EXPLANATION.md). Then attempt **Assignment 2.1**: [assignments/assignment-2.1-divvy-incremental-QUESTIONS.md](../../assignments/assignment-2.1-divvy-incremental-QUESTIONS.md).
