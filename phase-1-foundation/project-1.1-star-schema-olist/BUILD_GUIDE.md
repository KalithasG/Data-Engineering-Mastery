# 🛠️ Build Guide — Project 1.1: Star Schema with Olist

> Step-by-step guidance to build this **yourself**. Do each step before peeking at the reference (`build_star_schema.py`, explained in [EXPLANATION.md](EXPLANATION.md)). Each step has a **Checkpoint** — don't move on until it passes.

**Prereqs:** `pip install -r ../../requirements.txt` · read [SCENARIO.md](SCENARIO.md) first.

---

## Step 0 — Get the data
**Do:** Run `python generate_sample_data.py` (synthetic, for testing) — or place the real Kaggle Olist CSVs in `data/raw/`.
**Checkpoint:** `data/raw/` contains 8 CSVs; `olist_order_items_dataset.csv` has more rows than `olist_orders_dataset.csv`.

## Step 1 — Land the raw layer
**Do:** In a new script, connect to DuckDB (`duckdb.connect("data/olist.duckdb")`) and load each CSV *unchanged* into a `raw_*` table with `CREATE OR REPLACE TABLE raw_x AS SELECT * FROM read_csv_auto('...')`.
**Why:** Land data exactly as received before transforming — your insurance copy. `CREATE OR REPLACE` makes re-runs idempotent.
**Checkpoint:** `SELECT COUNT(*)` on each raw table matches the CSV row counts printed by the generator.

## Step 2 — Profile before you model
**Do:** Answer with SQL, and log the answers:
1. Is `customer_id` unique in raw_customers? (`COUNT(*) - COUNT(DISTINCT customer_id)`)
2. Distribution of `order_status` — which statuses have NULL delivery dates?
3. How many products have NULL `product_category_name`?
4. Items-per-order distribution (`GROUP BY order_id` then `GROUP BY` the counts).
**Why:** #4 proves the one-to-many cardinality that forces your grain decision; #3 tells you an unknown member is needed.
**Checkpoint:** You can state, in one sentence each: the true grain of `raw_order_items`, and why delivery-date NULLs are *structural*.

## Step 3 — Build `dim_date` first
**Do:** Find `MIN`/`MAX` of `order_purchase_timestamp`, generate one row per calendar day between them (`generate_series` + `UNNEST`), and add: `date_key` as a `yyyymmdd` integer, year, quarter, month, month_name, day_of_month, day_of_week, day_name, `is_weekend`.
**Hint:** `CAST(STRFTIME(d, '%Y%m%d') AS INTEGER)` for the key — date dims are the one accepted exception to "surrogate keys must be meaningless."
**Checkpoint:** Row count = number of days in the range; `SELECT * WHERE is_weekend LIMIT 5` shows only Sat/Sun.

## Step 4 — Build the dimensions with surrogate keys
**Do:** For customers, products, sellers: `ROW_NUMBER() OVER (ORDER BY <natural key>) AS x_key`, keep the hex ID as `x_natural_key`, keep the descriptive columns flat (star, not snowflake).
**Do also:** In `dim_product`, `COALESCE(category, 'unknown')`, and `UNION ALL` an **unknown-member row with key `-1`** (same for `dim_seller`).
**Checkpoint:** Each dim has a unique integer key; `SELECT * FROM dim_product WHERE product_key = -1` returns exactly one row.

## Step 5 — Declare the grain, then build the fact
**Do:** Write the grain as a comment **first**: `-- GRAIN: one row = one item line within one order.` Then build `fact_order_items`:
- start `FROM raw_order_items`, inner-join `raw_orders` (every item has an order)
- **LEFT** join each dimension on the natural key, select `COALESCE(dim.key, -1)`
- keep `order_id`/`order_item_id` as degenerate dimensions
- measures: `price`, `freight_value`, `price + freight_value AS total_item_value`
- derive `order_date_key` (yyyymmdd int) and `delivery_days` (`DATE_DIFF`; NULL when undelivered)
**Why LEFT + COALESCE(-1):** an unmatched fact routes to the unknown member instead of vanishing.
**Checkpoint:** `COUNT(*)` of the fact **exactly equals** `COUNT(*)` of `raw_order_items`.

## Step 6 — Validate with hard gates
**Do:** Add assertions that raise on failure: (a) fact rows == raw item rows (no fan-out/drop); (b) zero facts whose `product_key` has no match in `dim_product`.
**Checkpoint:** Script completes; deliberately break it (join dims with INNER instead of LEFT after deleting a product) and watch the assertion fire — then restore.

## Step 7 — Write the 10 analytical queries
**Do:** Each exactly one join hop. Must include: revenue by state · freight **ratio** by category (`SUM(freight)/SUM(price)` — never AVG of ratios) · monthly revenue · weekend vs weekday · top categories · delivery days by state (note `AVG` skips NULLs — correct here) · seller-state revenue · items-per-order via an order-grain CTE · QoQ growth with `LAG()` · cancelled value by month.
**Checkpoint:** All 10 return sensible rows; the freight-ratio query recomputes the ratio from sums, not an average.

## Step 8 — Compare with the reference & write the README
**Do:** Diff your approach against `build_star_schema.py` + [EXPLANATION.md](EXPLANATION.md). Write your README: grain, star-vs-snowflake, surrogate keys, unknown member, and the payments **fan trap** (why payments stayed out of the fact).
**Done when:** every SCENARIO deliverable is checked off.

➡️ **Next:** prove the skill transfers — [Assignment 1.1 (Global Superstore)](../../assignments/assignment-1.1-global-superstore-QUESTIONS.md), no guide, real Kaggle data.
