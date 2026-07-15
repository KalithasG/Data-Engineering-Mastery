# Project 1.2 — Framing Questions (ask these BEFORE you build)

> **Step 0 of the learning loop.** Answer "what are we expecting from this dataset?" before reading the code. Answers point back to `README.md` / `EXPLANATION.md`.

Dataset: **FIFA player catalog** (one wide table of players).

---

### Q1. What is this dataset?
One row per football player with attributes: name, age, nationality, club, position, overall/potential ratings, market value, wage, join date, physicals. Human-entered and exported — so it's **dirty in systematic ways**.

### Q2. What's the unit of analysis?
One **player** (`player_id`). The cleaner's job is to make each player row typed, valid, de-duplicated, and analysis-ready — without destroying real signal.

### Q3. What should the clean output let us do?
- Aggregate value/wage numerically (they arrive as strings like `€105.5M`).
- Compare true ratings (they arrive as `90+2`).
- Group by nationality/club/position without double-counting.
- Trust that every row is unique and every value in-range.

### Q4. What do we expect to be *wrong*? (map each to a quality dimension)
| Expected dirt | Example | Quality dimension |
|---|---|---|
| Currency strings | `€105.5M`, `€500K` | Validity |
| Composite ratings | `90+2`, `78-1` | Validity |
| Mixed date formats | `2019-07-01`, `7/1/2019`, `1 Jul 2019` | Validity + Consistency |
| Whitespace/casing | `  BRAZIL ` vs `Brazil` | Consistency |
| Duplicate rows | same `player_id` twice | Uniqueness |
| Null `club` | free agents | Completeness — but a **valid state** |
| Null `value` | obscure players | Completeness (MAR) |

### Q5. What's the target output/shape?
A **chainable, class-based cleaner** producing typed Parquet + a **quality-report artifact**, provably idempotent.

### Q6. Key decisions to reason through
- **One parser per systematic pattern** (currency, rating, date) — never hand-fix.
- **Per-column null strategy**: which nulls are *structural/valid* (leave/label), which are *MAR* (impute conditionally + flag), which are *MNAR* (flag, don't fill)?
- **Idempotency**: does running twice change anything? (It must not.)
- **Validation**: which invariants are hard gates (raise) vs. warnings?

### Q7. Gotchas
- Filling `club=None` destroys the "free agent" signal → the "when NOT to clean" trap.
- Imputing without a flag hides that a value was estimated.
- A parser that *raises* on one bad row kills the batch; return `None` and log instead.
- Idempotency breaks subtly (e.g. a flag column overwritten on re-run) — test it explicitly.

---

➡️ Read [README.md](README.md) / [EXPLANATION.md](EXPLANATION.md). Then attempt **Assignment 1.2**: [assignments/assignment-1.2-netflix-QUESTIONS.md](../../assignments/assignment-1.2-netflix-QUESTIONS.md).
