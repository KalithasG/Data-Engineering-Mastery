# Project 2.4 — Framing Questions (ask these BEFORE you build)

> **Step 0 of the learning loop.** Answers point back to `README.md` / `EXPLANATION.md`.

Dataset: **Google Play Store apps** — a clean-ish batch plus a deliberately "bad" (low-volume) batch.

---

### Q1. What is this dataset?
One row per app: name, category, rating, reviews, installs, price, content rating. Real-world app-store data is famously dirty (the notorious `19.0` rating on a 5-point scale).

### Q2. Why a *framework* instead of ad-hoc `assert`s?
Scattered checks don't scale, can't be reused, and give no consistent response. The question this project answers: *how do you turn quality checks into declarative, reusable **expectations** with a policy for what happens when one fails?*

### Q3. What should the framework produce?
- A pass/fail result per check, with counts and sample failures.
- A **quality-report artifact** (HTML + CSV) per run.
- A **quarantine** of failing rows (kept separate from the clean output).
- A **CI gate**: exit non-zero when a severe check fails.

### Q4. What do we expect to be *wrong*? (all six categories)
Schema (column exists/typed), Completeness (nulls), Validity (ratings 1–5, non-negative installs), Accepted values (known category set), Uniqueness (dup app ids), Referential (reviews imply a rating), and **Distributional/volume** (a batch that's 10% of normal size).

### Q5. What's the target output/shape?
`DataQualityCheck(name, column, rule, severity)` + `DataQualityRunner.add_check().run()`, 12 expectations across all 6 categories, severity-tiered responses, report + rejects + clean Parquet.

### Q6. Key decisions to reason through
- **Row-level vs table-level rules** — which enables quarantine? (Row-level.)
- **Severity policy**: which failures **hard-fail** (block), which are **warn** (log), which **quarantine** (route aside)?
- **Baseline for the volume check** — where does "normal row count" come from?
- **Report-first or gate-first?** (Generate the artifact *before* you fail.)

### Q7. Gotchas
- A single-row rule can't catch a **partial-extract** (right values, wrong *count*) — that's what the volume check is for.
- Hard-failing everything makes the gate useless; quarantine is often the best default.
- If you gate before writing the report, you lose the artifact exactly when you need it most.

---

➡️ Read [README.md](README.md) / [EXPLANATION.md](EXPLANATION.md). Then attempt **Assignment 2.4**: [assignments/assignment-2.4-amazon-zomato-quality-QUESTIONS.md](../../assignments/assignment-2.4-amazon-zomato-quality-QUESTIONS.md).
