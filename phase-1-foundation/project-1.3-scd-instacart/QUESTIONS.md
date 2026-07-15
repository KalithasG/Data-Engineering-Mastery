# Project 1.3 — Framing Questions (ask these BEFORE you build)

> **Step 0 of the learning loop.** Answers point back to `README.md` / `EXPLANATION.md`.

Dataset: **Instacart-style product catalog**, delivered as **three monthly snapshots**.

---

### Q1. What is this dataset and why snapshots?
A product catalog (`product_id`, name, aisle, department, price). SCD only matters when data **changes over time**, so we take a snapshot each month; between snapshots a slice of products change aisle/department/price, some names get typo-fixed, and a few new products appear.

### Q2. What's the unit of analysis, and what are the two keys?
One **version** of a product. Two keys you must keep straight:
- **Business key** `product_id` — stable, identifies the same product across versions.
- **Surrogate key** `product_key` — changes with every new version.

### Q3. What should the model answer?
- What is a product's *current* state? (`is_current`)
- What did it look like on a *past* date? (point-in-time)
- What is its full change history?
- For an order, what price did we *actually charge* vs. the current price?

### Q4. What changes do we expect, and how should each be tracked?
| Change | Track as | Why |
|---|---|---|
| Aisle / department move | **Type 2** (new version) | history matters for reports |
| Price change | **Type 2** | revenue must reflect price-at-time |
| Name typo fix | **Type 1** (overwrite all versions) | cosmetic — a version would be noise |
| New product | Insert new current row | never existed before |

### Q5. What's the target output/shape?
`dim_product_type1/2/3` implementations + a `fact_orders` that joins each order to the **point-in-time-correct** version, with a hard 1:1 gate.

### Q6. Key decisions to reason through
- **Which attributes are Type 1 vs Type 2?** (hybrid design)
- **Effective-date convention**: NULL end date or a sentinel? Closed or half-open interval?
- **Change detection**: how do you compare only the *tracked* attributes and handle NULLs?
- **Expiry**: when a new version starts on date D, when does the old one end?

### Q7. Gotchas
- **The #1 SCD bug**: joining facts on `is_current` (or business key alone) instead of a **date-range** — it stamps today's values onto historical facts.
- **Dimension explosion**: tracking noisy fields (a `last_login` timestamp) creates a new version on every load.
- **Overlap/gap**: if version date ranges overlap or leave gaps, the point-in-time join stops being 1:1.
- **`<>` vs `IS DISTINCT FROM`**: plain `<>` skips NULL→value changes silently.

---

➡️ Read [README.md](README.md) / [EXPLANATION.md](EXPLANATION.md). Then attempt **Assignment 1.3**: [assignments/assignment-1.3-ibm-hr-scd-QUESTIONS.md](../../assignments/assignment-1.3-ibm-hr-scd-QUESTIONS.md).
