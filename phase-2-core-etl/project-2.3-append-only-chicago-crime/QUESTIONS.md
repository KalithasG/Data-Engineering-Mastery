# Project 2.3 — Framing Questions (ask these BEFORE you build)

> **Step 0 of the learning loop.** Answers point back to `README.md` / `EXPLANATION.md`.

Dataset: **Chicago crime records**, delivered as **three overlapping batches**.

---

### Q1. What is this dataset and why "overlapping"?
Crime incident records (ID, Date, Primary Type, Description, Arrest, District, location). The source **re-sends recent records** in the next batch — so consecutive batches overlap. A naive `INSERT` would double-count.

### Q2. What defines record *identity*?
Which fields make two rows "the same crime"? Here: `ID | Date | Primary Type`, hashed to an MD5 fingerprint. Getting identity right is the whole game — if it's wrong, dedup fails.

### Q3. What should the pipeline guarantee?
- Re-ingesting the same batch inserts **zero** new rows (idempotent).
- Overlapping batches yield the **union**, not the sum.
- Every run is recorded in an **immutable audit log** — even a no-op run.

### Q4. What do we expect to be *wrong* / tricky?
- **Duplicates across batches** (the overlap) — the core challenge.
- **Duplicates within a batch** — a single file can repeat a record.
- **At-least-once delivery** — the same batch may arrive several times.

### Q5. What's the target output/shape?
An append-only `crimes` table keyed by `record_hash`, an `ingested_at` audit column, and a **separate immutable `ingest_audit`** log (batch, rows in/inserted/skipped, status).

### Q6. Key decisions to reason through
- **Which fields go into the hash?** (identity, not volatile fields.)
- **Where does dedup happen?** (within batch, against history, and as a PK.)
- **Append-only vs upsert** — why never mutate the raw table?
- **What does the audit log capture**, and why keep it separate from the data?

### Q7. Gotchas
- If record content depends on **position in the batch** instead of the stable ID, "overlapping" rows differ and dedup fails (this was a real bug in the build — see EXPLANATION).
- Forgetting to log no-op runs leaves gaps in the audit trail.
- **Exactly-once *delivery*** is hard; **exactly-once *outcome*** via idempotent processing is the pragmatic path.

---

➡️ Read [README.md](README.md) / [EXPLANATION.md](EXPLANATION.md). Then attempt **Assignment 2.3**: [assignments/assignment-2.3-audit-pipeline-QUESTIONS.md](../../assignments/assignment-2.3-audit-pipeline-QUESTIONS.md).
