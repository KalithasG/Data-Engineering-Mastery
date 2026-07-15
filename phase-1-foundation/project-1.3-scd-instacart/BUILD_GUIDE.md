# 🛠️ Build Guide — Project 1.3: Slowly Changing Dimensions with Instacart

> Step-by-step guidance to build this **yourself** before peeking at the reference (`scd_pipeline.py`, explained in [EXPLANATION.md](EXPLANATION.md)). This is the hardest Phase 1 project — go slow on Steps 4–6.

**Prereqs:** requirements installed · read [SCENARIO.md](SCENARIO.md) first.

---

## Step 0 — Get snapshots that actually change
**Do:** `python generate_sample_data.py` → three monthly `products_snapshot_*.csv` + `orders.csv`. Diff snapshot 1 vs 2 for one product that changed department.
**Checkpoint:** You can point at: a re-categorized product, a re-priced product, a typo-fixed name, and a brand-new product.

## Step 1 — Write your conventions down BEFORE coding
**Do:** In a comment block, commit to: business key = `product_id` · surrogate key = `product_key` (new per version) · closed interval `effective_start_date..effective_end_date` · current row = end date **sentinel `9999-12-31`** (never NULL — `BETWEEN` must just work) · expiry = day **before** the new version starts · tracked attrs = `[aisle, department, unit_price]` (name is Type 1).
**Why first:** every SCD bug is an inconsistency between these rules.
**Checkpoint:** The block exists; you can defend each choice aloud.

## Step 2 — SCD Type 1 (the warm-up)
**Do:** `dim_product_type1` = plain upsert per snapshot: UPDATE matching `product_id`s in place, INSERT unknown ones.
**Checkpoint:** After loading all 3 snapshots, the table equals the *latest* snapshot exactly — and you can articulate what was lost.

## Step 3 — SCD Type 3 (the second warm-up)
**Do:** `dim_product_type3(product_id, product_name, current_department, previous_department)`. On department change: shift current→previous, set new current. Insert new products with previous = NULL.
**Checkpoint:** Products that changed show both values; you can explain why a *second* change destroys the first (why Type 3 is rare).

## Step 4 — SCD Type 2: schema + first load
**Do:** Create `dim_product_type2` with both keys, tracked attrs, name, both effective dates, `is_current`. Load snapshot 1: every product = version 1, start = load date, end = sentinel, `is_current = TRUE`, `product_key` = `ROW_NUMBER()`-style fresh keys.
**Checkpoint:** 400 rows, all current, keys unique.

## Step 5 — The Type 2 merge (the heart — take your time)
**Do:** A function `scd_type2_merge(snapshot, load_date)` executing **in this order**:
1. **Hybrid Type 1 pass:** UPDATE `product_name` in place on ALL versions where it differs (typo fixes must NOT create versions).
2. **Detect changes:** stage the snapshot; join to `is_current` rows on business key; keep rows where any tracked attr differs — compare with **`IS DISTINCT FROM`**, not `<>` (`<>` silently skips NULL transitions).
3. **Expire:** for changed keys, set current row's `end = load_date - 1 day`, `is_current = FALSE`.
4. **Insert new versions:** fresh surrogate keys (`MAX(product_key) + ROW_NUMBER()`), `start = load_date`, `end = sentinel`, current.
5. **Insert brand-new products** (no version exists at all).
**Do:** Loop snapshots **in date order**, logging changed/total/current counts per merge.
**Checkpoint:** After all 3 loads: total rows > current rows; a product that changed twice has 3 versions with contiguous, non-overlapping date ranges; typo-fixed products did NOT gain a version.

## Step 6 — The point-in-time fact join (the payoff)
**Do:** Build `fact_orders` joining orders to the dimension **on business key AND date range**:
```
ON  o.product_id = d.product_id
AND o.order_date BETWEEN d.effective_start_date AND d.effective_end_date
```
Compute `line_revenue = quantity * d.unit_price` (price *at order time*). Then the single most important assertion in the project: **fact row count == raw orders count** (fewer ⇒ a gap in ranges; more ⇒ overlapping versions).
**Checkpoint:** Assertion passes. Try joining on `is_current` instead and observe the revenue difference — that's the #1 SCD bug, felt firsthand.

## Step 7 — Demo queries
**Do:** (1) current state via `is_current`; (2) as-of lookup: `WHERE '2023-01-15' BETWEEN start AND end`; (3) full history of one changed product; (4) for a product whose **price** changed: `price_at_order_time` vs `current_price` per order, with the difference column.
**Checkpoint:** Query 4 shows non-zero differences for orders placed before the price change.

## Step 8 — Compare with the reference & write the README
Diff against `scd_pipeline.py` / [EXPLANATION.md](EXPLANATION.md). README must include the Type 1/2/3 comparison table and your date convention.

➡️ **Next:** [Assignment 1.3 (IBM HR)](../../assignments/assignment-1.3-ibm-hr-scd-QUESTIONS.md) — same pattern on employees, plus the one thing this project didn't cover: a **late-arriving correction** (inserting a version *between* existing ones).
