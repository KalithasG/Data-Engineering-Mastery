# Assignment 2.4 — Quality Gate for a Content Catalog

> **You build this.** Answer every question in writing before coding. Prep: [Project 2.4 EXPLANATION](../phase-2-core-etl/project-2.4-quality-framework-playstore/EXPLANATION.md).

**Dataset:** Amazon Products or Zomato Restaurants (Kaggle) — a catalog of items with ratings, prices, categories.

---

## Framing questions to answer first

### Cover all six categories
- [ ] Define **≥12 expectations** spanning **schema, completeness, validity, uniqueness, referential, and distributional**. Which columns does each target?
- [ ] For each check, what does a **passing row** look like (your rule returns True for it)?

### The volume/distributional check
- [ ] What's your **baseline** row count (rolling average? last N runs?)?
- [ ] Build one check like "today's row count shouldn't differ from baseline by >20%." How will you **simulate a bad batch** (~10% of data) and prove it's caught — even when individual rows look fine?

### Severity policy
- [ ] For every check, assign **hard-fail**, **soft-fail/log**, or **quarantine** — and justify. Which failures should *block the pipeline*? Which just need logging? Which route rows aside?
- [ ] Why is **row-level** rule output necessary to quarantine?

### Reporting & gating
- [ ] What's in your **HTML/Markdown report** per run (pass/fail counts, sample failing rows)? Do you write it **before or after** enforcing the gate — and why?
- [ ] How does the pipeline **signal failure** to CI (exit code)?

### The data contract
- [ ] As the **producing team**, what schema + quality guarantees would you **commit to** — and what would you **explicitly not** guarantee? How do your severity tiers map to contract strength?

---

## Playbook requirements (self-check when done)
- [ ] ≥12 expectations spanning all 6 categories
- [ ] One distributional/volume expectation; bad batch simulated and caught
- [ ] Three-tier response (hard-fail / soft-fail / quarantine), each justified
- [ ] HTML/Markdown quality report per run (counts + sample failing rows)
- [ ] One-page "data contract" doc: what you guarantee and what you explicitly don't
