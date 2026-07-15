# Project 1.3 — Slowly Changing Dimensions with Instacart

> **Guided Project** from Phase 1 of the DE Playbook.
> Concepts: SCD Type 1/2/3, merge/upsert logic, effective dates, `is_current`, point-in-time joins, hybrid SCD.

📖 **Want the line-by-line walkthrough? Read [EXPLANATION.md](EXPLANATION.md).**

## What this project builds

Takes **three monthly snapshots** of an Instacart-style product catalog (where a slice of products change aisle, department, and price between snapshots) and tracks that history three different ways — then builds a fact table that joins each order to the dimension version that was valid **on the order date**.

```
dim_product_type1   overwrite in place        -> history LOST (latest snapshot only)
dim_product_type2   new row per version       -> full history (the industry standard)
dim_product_type3   previous_* column         -> one prior state only
fact_orders         joined to point-in-time-correct Type 2 version
```

## How to run

```bash
python generate_sample_data.py   # writes 3 monthly snapshots + orders.csv
python scd_pipeline.py           # builds all 3 SCD tables + fact_orders (with gates)
python demo_queries.py           # proves point-in-time correctness
```

## The four things SCD must answer (from `demo_queries.py`)

1. **Current state** — `WHERE is_current` → the latest version of every product.
2. **Point-in-time** — `WHERE '2023-01-15' BETWEEN effective_start_date AND effective_end_date` → what the product looked like on a past date.
3. **Full history** — all rows for one `product_id`, showing each version's date range.
4. **Current vs. at-time-of-record** — the payoff: January orders of product 16 were charged **10.48**, but the current price is **11.08**. Joining facts to the *current* version would overstate that month's revenue by 0.60/unit. Type 2 gets it right.

## SCD type comparison

| | Type 1 (overwrite) | Type 2 (new row) | Type 3 (prev column) |
|---|---|---|---|
| History kept | None | Full | One prior value |
| Table growth | None | One row per change | None |
| Query complexity | Trivial | Needs date-range join | Simple |
| Use when | Typo fixes, no analytical value in history | Prices, categories — anything reports slice by over time | You only ever need "current vs. immediately previous" |
| In this project | `product_name` (Type 1 within the Type 2 table) | `aisle`, `department`, `unit_price` | `department` history |

## Design decisions

### Type 2 conventions (document yours and never deviate)
- **Surrogate key** `product_key` — a *new* value per version. **Business key** `product_id` — stable across versions.
- **Effective dates**: closed interval `effective_start_date .. effective_end_date`, inclusive on both ends. Current rows use the sentinel `9999-12-31`, **never NULL** — so `BETWEEN` "just works" without `COALESCE`.
- **Expiry rule**: when a new version arrives on date D, the old version's `effective_end_date` is set to **D − 1 day** (no overlapping ranges → the point-in-time join stays exactly 1:1).

### Hybrid SCD (Type 1 *and* Type 2 in one table)
`product_name` is treated as a **Type 1 attribute**: a typo fix updates the name on *all* versions in place and does **not** create a new version. Only `aisle`, `department`, `unit_price` (the `TRACKED_ATTRS`) trigger a new Type 2 row. Tracking everything would cause "dimension explosion" — a fresh version every time a cosmetic field wobbles.

### The #1 SCD bug, avoided
The fact-to-dimension join is on **business key + date-range**, not on `is_current`:
```sql
ON o.product_id = d.product_id
AND o.order_date BETWEEN d.effective_start_date AND d.effective_end_date
```
Joining on `is_current` (or business key alone) would stamp *today's* attributes onto *historical* facts. `scd_pipeline.py` asserts the join is 1:1 (fact rows == order rows) as a hard quality gate — a gap in the date ranges or overlapping versions would trip it immediately.

### `IS DISTINCT FROM`, not `<>`
Change detection uses `IS DISTINCT FROM` so that NULL-vs-value comparisons behave (plain `<>` returns NULL for a NULL operand, which would silently skip changed rows).

## Deliverables checklist

- [x] SCD Type 1 / 2 / 3 implementations (`scd_pipeline.py`)
- [x] Point-in-time query examples (`demo_queries.py`)
- [x] Full history per product
- [x] README comparing when to use each type (this file)
