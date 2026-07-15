# Assignment 1.3 — Employee History with SCD Type 2

> **You build this.** Answer every question in writing before coding. Prep: [Project 1.3 EXPLANATION](../phase-1-foundation/project-1.3-scd-instacart/EXPLANATION.md).

**Dataset:** IBM HR Analytics Employee Attrition (Kaggle) — a *static* snapshot you must animate by simulating change over time.

---

## 📊 Business questions your history tracking must answer

You're the DE for a People-Analytics team. Every ask below is impossible (or silently wrong) if the employee table is updated in place — your SCD design must make them all answerable:

| Stakeholder | Business question |
|---|---|
| **HR leadership** | Headcount by department **as it was on any past date** — not restated by later transfers |
| **HR leadership** | Attrition rate by the department the employee was in **at the time they left** |
| **Finance** | Monthly compensation cost trend at the salaries **actually paid each month**, not today's salaries |
| **Comp & benefits** | Each employee's full salary/role change timeline — who got promoted, when, from what to what? |
| **Org planning** | Who moved departments this quarter, and what do internal-mobility flows look like? |
| **HRBP (data fix)** | "This transfer actually happened two months ago — backdate it **without corrupting** the reports in between" |

Before designing, ask yourself:
- [ ] Which of these needs the point-in-time join, and which only needs `is_current`?
- [ ] Which ask decides whether MonthlyIncome is Type 1 or Type 2? What about a name-spelling fix?
- [ ] Which ask is the **late-arriving correction** — and what must stay true of your date ranges after you handle it?

---

## Framing questions to answer first

### Simulate change
- [ ] The data is one static snapshot. How will you produce **3 load batches over time**?
- [ ] Which attributes will you **mutate for ~15% of employees** between batches (Department, JobRole, MonthlyIncome)? How do you keep the same employee identifiable across batches?

### Keys and dates
- [ ] What's the **business key** (stable per employee) vs the **surrogate key** (per version)?
- [ ] What's your **effective-date convention** — NULL end date or a sentinel? Closed or half-open interval? (Pick one and use it *everywhere*.)

### Type 1 vs Type 2 per attribute
- [ ] For **each** tracked attribute, decide: does a change create a **new version (Type 2)** or **overwrite (Type 1)**? Justify each. (Is a MonthlyIncome change history-worthy? A JobRole change? A typo in a name?)
- [ ] How do you detect a *tracked* change while ignoring noise? How do NULLs affect that comparison?

### The point-in-time join
- [ ] How will the fact table join to the **version valid at the time of the record**, not the current one?
- [ ] How will you **prove** it — a query comparing "current" vs "at time of record" for one employee who changed departments?

### The hard part
- [ ] Simulate a **late-arriving correction** (you learn today that a change actually happened two months ago). How do you insert a version *between* existing ones and **re-split the date ranges** without creating gaps or overlaps?

---

## Playbook requirements (self-check when done)
- [ ] 3 load batches; ~15% of employees mutated between batches
- [ ] Type 2 dimension with correct surrogate key, business key, effective dates, is_current
- [ ] Merge/upsert: new version only when a tracked attribute changes; Type 1 vs 2 decided per attribute and justified
- [ ] Fact joins to point-in-time-correct row; proven with a current-vs-at-time query
- [ ] One late-arriving correction handled correctly
- [ ] effective_end_date convention (null vs sentinel) documented and used consistently
