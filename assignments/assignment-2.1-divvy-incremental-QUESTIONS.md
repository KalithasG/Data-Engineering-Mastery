# Assignment 2.1 — Watermark-Based Incremental Loader for Divvy

> **You build this.** Answer every question in writing before coding. Prep: [Project 2.1 EXPLANATION](../phase-2-core-etl/project-2.1-incremental-nyc-taxi/EXPLANATION.md).

**Dataset:** Chicago Divvy Bikeshare (Kaggle) — bike trip records with start/end times and stations.

---

## Framing questions to answer first

### Choose the watermark
- [ ] Which column is your **watermark**? A trip `end_time`, an `updated_at`, an auto-increment id, or a partition date? What are the trade-offs (does the source ever *update* a row after insert)?
- [ ] Where will the watermark live so it survives across runs and isn't **hardcoded**? What's the schema of that **control table** (per-source)?

### Ordering & safety
- [ ] At what exact moment do you **advance** the watermark? What breaks if you advance it *before* the load succeeds?
- [ ] Advance to "now" or to "max value actually loaded"? Why does the difference matter?

### Idempotency
- [ ] What's your dedup key? How will you **prove** running the loader twice on the same new data yields **zero duplicates**?
- [ ] How will you **simulate a crash mid-load** and show the watermark did **not** advance and the retry picks up cleanly?

### Late data
- [ ] How wide is your **lookback window**? Why is re-scanning it safe (what property must the load have)?

### When to change tools
- [ ] In 2–3 sentences: when would you abandon watermark loading for **true CDC**? (Think deletes, latency, source load.)

---

## Playbook requirements (self-check when done)
- [ ] Control table tracking last_loaded_timestamp **per source** (not hardcoded)
- [ ] Chunked incremental loading using the watermark
- [ ] Idempotency proven: run twice → zero duplicates
- [ ] Crash simulated mid-load; watermark **not** advanced; clean retry
- [ ] Lookback window for simulated late-arriving rows
- [ ] README: 2–3 sentences on when you'd switch to true CDC
