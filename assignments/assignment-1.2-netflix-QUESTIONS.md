# Assignment 1.2 — Cleaning Class for Netflix Catalog

> **You build this.** Answer every question in writing before coding. Prep: [Project 1.2 EXPLANATION](../phase-1-foundation/project-1.2-data-cleaning-fifa/EXPLANATION.md).

**Dataset:** Netflix Movies and TV Shows (Kaggle) — one row per title (movie or show).

---

## 📊 Business questions your clean data must unblock

You're the DE for a content-strategy team. Each ask below is currently blocked by dirt in the raw catalog — your cleaner must unblock all of them:

| Stakeholder | Business question |
|---|---|
| **Content strategy** | How has catalog growth (titles **added** per month/year) trended, split movies vs TV? |
| **Content strategy** | What's the average movie *length in minutes* vs average show *season count* — and how do they trend by release year? |
| **Acquisition team** | Which **genres** dominate the catalog, with correct counts per genre? |
| **Acquisition team** | Who are the most prolific directors and most-featured actors? |
| **Regional teams** | Catalog composition and maturity-rating mix by **country** |
| **Compliance** | Exact, duplicate-free title counts per rating category |

Before designing, ask yourself:
- [ ] Which mess pattern blocks *each* ask? (e.g. duration mixing `"90 min"`/`"2 Seasons"` blocks the length question; multi-value `listed_in` breaks genre counts if not exploded; `date_added` needs parsing for the growth trend)
- [ ] For the genre and actor asks — what happens to counts if you *don't* explode the multi-value columns?
- [ ] Which asks tolerate a null (`director` unknown) vs which need a labelled category?

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
