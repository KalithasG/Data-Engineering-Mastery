# Project 1.1 — Line-by-Line Explanation

This document walks through **every meaningful block** of Project 1.1 so you understand not just *what* the code does but *why* each choice was made. Once you've read this, you'll be equipped to do **Assignment 1.1 (Global Superstore star schema)** on your own.

**Files covered:** `generate_sample_data.py`, `build_star_schema.py`, `analytical_queries.sql`, `run_queries.py`.

---

## Part A — `generate_sample_data.py`

You only need this because we don't ship the real Kaggle CSVs. It fabricates data with the *exact same shape and dirt* as real Olist, so the loader behaves identically on synthetic or real data. In the assignment you'll download the real Global Superstore CSV instead — but understanding how the dirt is constructed here helps you recognize it there.

### Seeding for reproducibility
```python
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
```
Fixing the seed makes the generated data **identical every run**. This matters for two reasons: (1) your analytical query results don't change between runs, and (2) it lets you test the loader's *idempotency* — run it twice, get the same tables.

### `fake_id(prefix, n)`
```python
return hashlib.md5(f"{prefix}-{n}".encode()).hexdigest()
```
Real Olist IDs are 32-character hex strings. We reproduce that by MD5-hashing a seed string. **Why it matters for you:** these are *natural keys* — long, ugly, and exactly the kind of key you should NOT use as a join key in a warehouse. That's the whole motivation for surrogate keys later.

### The deliberate dirt
Two imperfections are injected on purpose:
```python
# products with missing category (~2%)
df.loc[missing, "product_category_name"] = None
```
This forces the loader to handle a **late-arriving / unknown dimension member**. If every product had a category, you'd never learn the pattern.

```python
"order_delivered_customer_date": delivered if status == "delivered" else None,
```
Only *delivered* orders have a delivery timestamp. This is a **structural null** — "not applicable," not "missing data." Recognizing the difference is a Phase 1 learning goal (see Primer 1.2 and 2.2).

### Cardinality is built in
```python
n_items = np.random.choice([1, 2, 3, 4, 5], p=[0.88, 0.07, 0.03, 0.01, 0.01])
```
Most orders have 1 item, a few have up to 5. This creates the **one-order-to-many-items** relationship — the exact cardinality that makes "grain" a real decision in the fact table.

---

## Part B — `build_star_schema.py` (the heart of the project)

### The raw layer
```python
RAW_TABLES = {
    "raw_customers": "olist_customers_dataset.csv",
    ...
}
```
Every CSV is loaded into a `raw_*` table with `read_csv_auto`, untouched. This is a **mini Bronze layer** (you'll formalize this in Phase 3). The principle: *land data exactly as received before transforming it*, so you always have a clean copy to reprocess from.

```python
con.execute(f"""
    CREATE OR REPLACE TABLE {table} AS
    SELECT * FROM read_csv_auto('{path.as_posix()}')
""")
```
`CREATE OR REPLACE` makes the load **idempotent** — re-running rebuilds the table from scratch instead of appending duplicates. `read_csv_auto` infers types and headers.

### Profiling BEFORE modeling
```python
def profile_raw(con):
```
This function is not optional busywork — **profiling is how you discover the true grain and cardinality** before you commit to a schema. It answers three questions:

1. **Is `customer_id` unique?**
   ```python
   SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM raw_customers
   ```
   If this is 0, `customer_id` is a valid key for one row per customer. If it were non-zero, joining on it would fan out.

2. **What's the order-status distribution?** Tells you the delivery-date nulls are structural (only ~90% delivered).

3. **What's the items-per-order distribution?**
   ```python
   SELECT n_items, COUNT(*) FROM (
       SELECT order_id, COUNT(*) AS n_items FROM raw_order_items GROUP BY 1
   ) GROUP BY 1
   ```
   This *proves* the one-to-many relationship you must respect when choosing the fact grain. **In the assignment, run a query like this before you design anything.**

### `dim_date` — build it first, build it from scratch
```python
WITH bounds AS (
    SELECT MIN(order_purchase_timestamp)::DATE AS start_date,
           MAX(order_purchase_timestamp)::DATE AS end_date
    FROM raw_orders
),
days AS (
    SELECT UNNEST(generate_series(start_date, end_date, INTERVAL 1 DAY))::DATE AS d
    FROM bounds
)
```
- `bounds` finds the date range actually present in the data.
- `generate_series(...)` produces one row per calendar day in that range; `UNNEST` turns the array into rows.

```python
CAST(STRFTIME(d, '%Y%m%d') AS INTEGER) AS date_key,
```
The surrogate key is a `yyyymmdd` integer (e.g. `20170115`). **Date dimensions are the ONE accepted exception** to the "surrogate keys must be meaningless" rule — a readable integer date key is a long-standing Kimball convention because it's human-debuggable and sorts correctly.

```python
EXTRACT(dow FROM d) IN (0, 6) AS is_weekend
```
Pre-computing attributes like `is_weekend`, `quarter`, `month_name` means every "sales by weekend/quarter" query is a **single join with no date math**. This is why the date dimension is called "the highest-leverage dimension" — you build it once, and it powers dozens of queries.

**Assignment tie-in:** Assignment 1.1 explicitly requires `day_of_week`, `is_weekend`, `fiscal_quarter`, `is_holiday`. `fiscal_quarter` differs from calendar quarter (many companies start their fiscal year in Feb/Jul); `is_holiday` needs a holiday list or a library like `holidays`. This function is your template.

### `dim_customer` — surrogate keys
```python
ROW_NUMBER() OVER (ORDER BY customer_id) AS customer_key,
customer_id                              AS customer_natural_key,
```
- `customer_key` is a clean integer, generated by `ROW_NUMBER()` over a deterministic ordering. This is the **surrogate key** and becomes the dimension's PK.
- The ugly hash `customer_id` is preserved as `customer_natural_key` for traceability back to the source, but it is *never* used as a join key.

**Why surrogate keys?** Natural keys change when source systems migrate; integers join faster; and — critically — surrogate keys are what make SCD Type 2 possible (Project 1.3), because you need a key that changes per *version* while the business key stays stable.

### `dim_product` — the unknown member
```python
SELECT ROW_NUMBER() OVER (ORDER BY product_id) AS product_key,
       ...
       COALESCE(product_category_name, 'unknown') AS product_category,
       ...
FROM raw_products
UNION ALL
SELECT -1, 'UNKNOWN', 'unknown', NULL, NULL, NULL, NULL, NULL
```
Two things happen here:
1. `COALESCE(..., 'unknown')` handles products whose category was null in the source.
2. The `UNION ALL SELECT -1, ...` appends a special **unknown-member row** with surrogate key `-1`.

**The unknown member is your insurance against late-arriving dimensions.** If a fact references a product that isn't in `dim_product` yet, the fact join routes it to key `-1` instead of dropping the row. Without this, an INNER JOIN would *silently delete* facts — the classic "why did my revenue shrink?" bug.

### `fact_order_items` — grain declared in the docstring
```python
"""
GRAIN: one row = one item line within one order.
"""
```
**This comment is written before any SQL.** Declaring the grain first is the single most important discipline in dimensional modeling. Grain = "what does one row represent?" Here: one item within one order. An order with 3 items → 3 fact rows.

```python
oi.order_id,
oi.order_item_id,
```
These are **degenerate dimensions** — identifiers kept on the fact row itself because they have no descriptive attributes worth a separate table. A `dim_order` would contain nothing but keys.

```python
COALESCE(dc.customer_key, -1) AS customer_key,
COALESCE(dp.product_key,  -1) AS product_key,
COALESCE(ds.seller_key,   -1) AS seller_key,
```
Every natural key from the raw data is **swapped for the dimension's surrogate key** via a LEFT JOIN. `COALESCE(..., -1)` sends any unmatched fact to the unknown member.

```python
CAST(STRFTIME(o.order_purchase_timestamp, '%Y%m%d') AS INTEGER) AS order_date_key,
```
The order timestamp is converted to the same `yyyymmdd` integer used by `dim_date`, so they join.

```python
oi.price,
oi.freight_value,
oi.price + oi.freight_value AS total_item_value,
```
These are the **additive measures** — numbers you can safely SUM across any dimension. They live at the declared grain (per item), which is what makes them additive.

```python
FROM raw_order_items oi
JOIN raw_orders o        ON oi.order_id = o.order_id
LEFT JOIN dim_customer dc ON o.customer_id = dc.customer_natural_key
LEFT JOIN dim_product  dp ON oi.product_id = dp.product_natural_key
LEFT JOIN dim_seller   ds ON oi.seller_id  = ds.seller_natural_key
```
- The `JOIN` to `raw_orders` is an INNER join because every item *must* belong to an order (enforced by construction).
- The joins to dimensions are `LEFT` joins so unmatched facts survive (→ unknown member). **This LEFT-vs-INNER choice is deliberate and is exactly what Assignment 2.2 asks you to reason about.**

### `validate()` — hard quality gates
```python
assert fact_rows == raw_rows, "a join fanned out or dropped rows"
```
The fact must have exactly as many rows as `raw_order_items`. If it has **more**, a join fanned out (a dimension had duplicate keys). If **fewer**, a join dropped rows. Either way, the schema is wrong and the pipeline halts loudly rather than shipping bad numbers.

```python
orphans = ... WHERE p.product_key IS NULL
assert orphans == 0
```
Referential integrity check: every fact must point at a real dimension row. Because of the unknown member, this should always pass — the assertion proves it.

---

## Part C — `analytical_queries.sql`

Each query is separated by a `-- name: <label>` marker (parsed by `run_queries.py`). **Every query is exactly one join hop** from fact to the dimension(s) it needs — that's the payoff of a star schema.

### Q2 — the non-additive measure
```sql
ROUND(SUM(f.freight_value) / SUM(f.price), 3) AS freight_ratio
```
Freight *ratio* is **non-additive**: you cannot average or sum ratios. You must recompute it from the two underlying additive measures (`SUM(freight)/SUM(price)`) at *every* aggregation level. Averaging per-row ratios would weight a R$10 order the same as a R$10,000 one.

**Assignment tie-in:** Assignment 1.1 requires you to "identify one semi-additive or non-additive measure and explain correct aggregation." This query is your worked example of a non-additive one.

### Q6 — nulls in aggregates
```sql
ROUND(AVG(f.delivery_days), 1) AS avg_delivery_days,
COUNT(f.delivery_days)         AS delivered_items
```
`delivery_days` is NULL for undelivered orders. **`AVG` silently ignores NULLs**, which is exactly right here — we want the average over *delivered* items only. `COUNT(column)` counts non-nulls, so it tells you how many items that average is based on. (Contrast `COUNT(*)`, which would count all rows including undelivered.)

### Q8 — aggregating to a coarser grain safely
```sql
WITH order_grain AS (
    SELECT order_id, COUNT(*) AS items_in_order, SUM(price) AS order_revenue
    FROM fact_order_items GROUP BY order_id
)
```
To answer an *order-level* question from an *item-grain* fact, you first roll the fact up to order grain in a CTE, then summarize. This is the safe pattern — never try to answer order-level questions by eyeballing item rows.

### Q9 — window function for growth
```sql
LAG(revenue) OVER (ORDER BY year, quarter)
```
`LAG` fetches the previous quarter's revenue on the same row, so you compute quarter-over-quarter growth **without a self-join**. You'll go deep on window functions in Phase 3.

### Q10 — the fan trap, avoided by omission
Notice `raw_payments` and `raw_reviews` were loaded but **never joined into the fact**. Payments are *order*-grain (one row per order). If you joined payments onto the item-grain fact, each payment value would be multiplied by the number of items in the order — a **fan trap** that silently inflates totals. The correct fix (a separate order-grain fact) is Assignment 1.1 territory.

---

## Part D — `run_queries.py`
```python
pattern = re.compile(r"--\s*name:\s*(\w+)\n(.*?);", re.DOTALL)
```
Splits the `.sql` file into `(name, query)` pairs on the `-- name:` markers, then runs each and prints the result as a dataframe. `read_only=True` on the connection guarantees the query script can never accidentally mutate the warehouse.

---

## Your Assignment 1.1 checklist, mapped to what you just learned

| Assignment requirement | Where this project taught it |
|---|---|
| State the grain before any DDL | `fact_order_items` docstring |
| ≥4 dimensions, justify each | `dim_customer/product/seller/date` |
| Surrogate keys everywhere | `ROW_NUMBER()` pattern in every dim |
| Build `dim_date` from scratch | `build_dim_date()` (add `fiscal_quarter`, `is_holiday`) |
| One semi/non-additive measure | Q2 freight ratio |
| 8 one-hop analytical queries | `analytical_queries.sql` |
| Describe a fan-trap scenario | Q10 note + design decision #8 in README |

Now go build it for Global Superstore — same patterns, new dataset, no hand-holding.
