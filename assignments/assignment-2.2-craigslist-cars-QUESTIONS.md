# Assignment 2.2 — Multi-Source Merge with Conflicting Data (Craigslist Cars)

> **You build this.** Answer every question in writing before coding. Prep: [Project 2.2 EXPLANATION](../phase-2-core-etl/project-2.2-multisource-flights/EXPLANATION.md).

**Dataset:** Used Car Listings / Craigslist Cars (Kaggle) — vehicle listings with price, condition, odometer, location, etc.

---

## Framing questions to answer first

### Before any join
- [ ] What's the **expected cardinality** of each join, and the **expected row-count range** afterward? Write it down *before* you merge.
- [ ] How will you use `COUNT(*)` **before and after** each join to catch a fan-out or a silent drop? What will you do when the numbers surprise you?

### Nulls — classify each
- [ ] Pick **≥5 columns** and classify each column's nulls as **structural**, **source-missing**, or **join-induced**. What's the *different* justified strategy for each?
- [ ] Which nulls are valid states you should label, not fill?

### Conflicts (the new bit vs. the guided project)
- [ ] Simulate **two sources** for the same listing (e.g. a scrape vs. a dealer feed) that **disagree** on one attribute (price? condition?). What's your **explicit conflict-resolution rule** — "most recently updated wins," "source A authoritative," or "flag for review"?
- [ ] Where does that rule live (transformation logic + documentation), and how do you mark conflicts with a `_data_quality_flag`?

### The INNER-vs-LEFT demonstration
- [ ] Write **one query that produces wrong results under INNER JOIN** but correct under LEFT JOIN. What's the exact **row-count difference**, and what does it represent?

---

## Playbook requirements (self-check when done)
- [ ] Expected cardinality + row-count range stated before each join
- [ ] `COUNT(*)` before/after each join; surprises reconciled and documented
- [ ] ≥5 columns' nulls classified (structural / source-missing / join-induced) with different strategies
- [ ] Explicit conflict-resolution rule for one attribute across simulated sources; `_data_quality_flag` where conflicts detected
- [ ] One INNER-vs-LEFT query showing the row-count difference
