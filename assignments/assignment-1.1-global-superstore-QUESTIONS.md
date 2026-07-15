# Assignment 1.1 — Star Schema for Global Superstore

> **You build this.** Answer every question **in writing** before coding. No answers are given here — that's the point. Prep by re-reading [Project 1.1 EXPLANATION](../phase-1-foundation/project-1.1-star-schema-olist/EXPLANATION.md).

**Dataset:** Global Superstore (Kaggle) — retail orders with customer, product, geography, and shipping info.

---

## Framing questions to answer first

### Understand the data
- [ ] What does one row in the raw file represent? Is it order-grain or line-grain?
- [ ] Which columns are **measures** (numeric, additive) vs **descriptive** (dimension attributes)?
- [ ] Which columns naturally group into a dimension (customer? product? geography? shipping?)?

### Declare the grain
- [ ] **What will one fact row represent?** Write it as a one-line comment before any DDL.
- [ ] Can you roll up from this grain to every question you want to answer? Can you drill down if you go coarser?

### Design the dimensions
- [ ] Which **≥4 dimensions** will you build, and *why is each one not just folded into the fact*?
- [ ] What's the **surrogate key** strategy for each? What natural key does each replace?
- [ ] What goes in `dim_date`? Beyond day/month/year: **day-of-week, is_weekend, fiscal_quarter, is_holiday** — how will you compute fiscal quarter (does it start in January)? Where do holidays come from?

### Measures & additivity
- [ ] Which measures are fully additive?
- [ ] Identify **one semi-additive or non-additive** measure (e.g. profit *ratio*, discount *rate*). How must it be aggregated correctly, and why does averaging it mislead?

### Queries
- [ ] Write **8 analytical queries**, each **one join hop** from fact to a dimension. What business question does each answer?

### Anticipate the trap
- [ ] If you added a **second fact table** (e.g. returns, or shipments) at a different grain, where's the **fan-trap** risk? How does your design avoid joining two facts directly?

---

## Playbook requirements (self-check when done)
- [ ] Grain stated explicitly in a comment before any DDL
- [ ] ≥4 dimension tables, each justified
- [ ] Surrogate keys for every dimension
- [ ] `dim_date` built from scratch (day-of-week, is_weekend, fiscal_quarter, is_holiday)
- [ ] One semi/non-additive measure identified + correct aggregation explained in README
- [ ] 8 analytical queries, one join hop each
- [ ] README describes a fan-trap scenario for a hypothetical second fact and how you avoid it
