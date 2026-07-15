# 🎫 Scenario — Project 1.3: Price-History Tracking for a Grocery Delivery Platform

> Read this like a ticket handed to you at work. Everything you must do is in the question. Try to plan it yourself **before** opening [BUILD_GUIDE.md](BUILD_GUIDE.md).

## The situation

You're a Data Engineer at an Instacart-style grocery platform. Finance just discovered a serious reporting bug: when a product's price changes, the catalog table is **updated in place** — so last quarter's revenue reports are recomputed with *today's* prices and quietly change every time someone re-runs them. The same happens when products move departments: historical "revenue by department" reports rewrite history.

Every month you receive a **full catalog snapshot** from the source system. Products change price (~8%), move aisle/department (~5%), get name typo-fixes (~2%), and a few new products appear.

Your tech lead assigns you this ticket:

## The ticket

> **Make historical reports stop changing: track product history with Slowly Changing Dimensions, and make every order join to the product version that was true on the order date.**

Before writing any code, you must be able to answer — and your implementation must then prove:

1. **Why SCD exists:** What exactly is lost when you UPDATE a dimension in place, and which of finance's two bugs does it explain?
2. **All three types:** Implement SCD **Type 1** (overwrite), **Type 2** (new row per version), and **Type 3** (previous-value column) side by side. When is each the right tool, and what can each *not* answer?
3. **Two keys:** What's the difference between the **business key** (`product_id`, stable) and the **surrogate key** (`product_key`, new per version), and why does Type 2 require both?
4. **Effective dates:** What's your convention — closed interval? sentinel `9999-12-31` instead of NULL end date? old version ends the day *before* the new one starts? Why must there be **no gaps and no overlaps**?
5. **Change detection:** How do you create a new version **only when a tracked attribute** (aisle, department, price) changes — and why must name typo-fixes be Type 1 inside your Type 2 table (hybrid SCD)? Why compare with `IS DISTINCT FROM` instead of `<>`?
6. **The merge algorithm:** For each monthly snapshot: detect changed products → expire their current versions → insert new versions with fresh surrogate keys → insert brand-new products. Write it so loading snapshots *in order* builds correct history.
7. **The point-in-time join (the whole point):** How must `fact_orders` join to the dimension so each order gets the version valid **on the order date** — and why is joining on `is_current` (or business key alone) the #1 SCD bug?
8. **Prove it:** Which single assertion validates the entire implementation (hint: the point-in-time join must be exactly 1:1)? Then demonstrate with a query: for a product whose price changed, show `price_at_order_time` vs `current_price` and the revenue error a naive join would cause.

## Deliverables (definition of done)

- [ ] SCD Type 1 / 2 / 3 implementations over three monthly snapshots
- [ ] Point-in-time query examples: current state, as-of-date lookup, full history per product
- [ ] `fact_orders` with the date-range join + 1:1 hard gate
- [ ] README comparing when to use each SCD type and documenting your effective-date convention

## Data

- **To test:** `python generate_sample_data.py` creates three monthly snapshots with the mutations above, plus orders.
- **To practice for real:** download [Instacart Market Basket Analysis](https://www.kaggle.com/datasets/psparks/instacart-market-basket-analysis) — it's a *static* snapshot (`products.csv`, `orders.csv`), so simulate change yourself: copy `products.csv` three times and randomly mutate aisle/department/price between copies (exactly what the generator does). Simulating the batches is part of the skill — you'll do it again in Assignment 1.3.

➡️ Ready to build? Follow [BUILD_GUIDE.md](BUILD_GUIDE.md). Reference implementation in this folder, explained in [EXPLANATION.md](EXPLANATION.md).
