# Project 2.2 — Framing Questions (ask these BEFORE you build)

> **Step 0 of the learning loop.** Answers point back to `README.md` / `EXPLANATION.md`.

Dataset: **three sources** — `flights` (fact-like) + `airlines` + `airports` (dimensions).

---

### Q1. What is this dataset?
A fact-like flights table (one row per scheduled flight, with delay/cancellation columns) plus two small dimension files that flights reference by code (`airline_code`, `origin`, `destination`).

### Q2. Before ANY join — what's the cardinality on each side?
Every join here is **many flights : one dimension row**. So a LEFT join must leave the flight row count **unchanged**. Ask this *before* writing `merge`, then reconcile the count after. Guessing cardinality is how you silently double-count.

### Q3. What should the enriched table answer?
- On-time performance and cancellation rate by airline?
- Busiest origin airports?
- Worst routes by schedule adherence?
- How many rows reference a dimension key we don't have? (a QA metric)

### Q4. What do we expect to be *wrong*? (three kinds of null)
| Null type | Example | Right response |
|---|---|---|
| **Structural** | cancelled flight has no delay | sentinel (`-999`) **+ keep `is_cancelled` flag** |
| **Join-induced** | unmatched airline/airport code | label `UNKNOWN` **+ `*_missing` flag** — surface it |
| **Guarded derived** | variance where elapsed is a sentinel | compute only on real values |

### Q5. What's the target output/shape?
One enriched `fact_flights` table bulk-loaded into a SQL DB via SQLAlchemy, indexed, with 5 analytical queries and a row-count reconciliation.

### Q6. Key decisions to reason through
- **INNER vs LEFT**: which side is the source of truth? (Flights — so LEFT, keep every flight.)
- **Sentinel vs 0 vs NULL** for structural nulls (why not 0?).
- **Bulk-load mechanics**: `chunksize`, `method="multi"`, index *after* load.
- **Which columns to index** (the ones queries filter/group by).

### Q7. Gotchas
- INNER join silently **drops** unmatched flights → shrinking row counts nobody notices.
- Filling a structural delay with **0** corrupts the average (0 is a real on-time value).
- Doing arithmetic on a sentinel (`-999 - 120`) produces garbage metrics.
- Joining the airports dim twice (origin + destination) needs column renaming to avoid collisions.

---

➡️ Read [README.md](README.md) / [EXPLANATION.md](EXPLANATION.md). Then attempt **Assignment 2.2**: [assignments/assignment-2.2-craigslist-cars-QUESTIONS.md](../../assignments/assignment-2.2-craigslist-cars-QUESTIONS.md).
