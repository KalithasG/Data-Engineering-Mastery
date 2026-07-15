# Assignment 1.2 — Cleaning Class for Netflix Catalog

> **You build this.** Answer every question in writing before coding. Prep: [Project 1.2 EXPLANATION](../phase-1-foundation/project-1.2-data-cleaning-fifa/EXPLANATION.md).

**Dataset:** Netflix Movies and TV Shows (Kaggle) — one row per title (movie or show).

---

## Framing questions to answer first

### Understand the data
- [ ] What does one row represent? What distinguishes a **movie** row from a **TV show** row?
- [ ] Which columns are single-valued vs **multi-valued** (e.g. `listed_in`, `cast`, `director`)?

### Classify the dirt (all 6 quality dimensions)
- [ ] List **≥5 real issues** and tag each with its quality dimension (completeness, validity, consistency, uniqueness, accuracy, timeliness).

### The `duration` problem
- [ ] `duration` is `"90 min"` for movies but `"2 Seasons"` for shows. **Why does a single global parser fail here?**
- [ ] What two columns will you split it into, and how do you branch on content type?

### Multi-value columns
- [ ] For `listed_in` / `cast`: do you **explode into rows**, store an **array**, or build a **bridge table**? What does each choice cost downstream (counting, joins, storage)?

### Nulls
- [ ] Pick one column (e.g. `director`, `date_added`, `rating`). Is its missingness **MCAR, MAR, or MNAR**? How do you justify imputing vs. flagging vs. leaving it?
- [ ] Which nulls here are **valid states**, not errors?

### Design the cleaner
- [ ] What are the chainable steps, in order? Which return `self`?
- [ ] What invariants become **hard validation gates**?
- [ ] How will you **prove idempotency** with a test?

---

## Playbook requirements (self-check when done)
- [ ] Chainable, class-based cleaner (not ad-hoc scripts)
- [ ] ≥5 issues classified by the 6 quality dimensions
- [ ] `duration` split into two columns by content type, with a written explanation of why a global transform fails
- [ ] Multi-value `listed_in`/`cast` handled, strategy justified (bridge vs array)
- [ ] One column's MCAR/MAR/MNAR diagnosis + imputation decision in writing
- [ ] A data-quality **report artifact** (not print statements)
- [ ] A unit test proving **idempotency** (twice = once)
