# Project 1.3 — Line-by-Line Explanation

This walks through **every meaningful block** of the SCD pipeline. SCD Type 2 is the single most error-prone pattern in Phase 1, so read this carefully — then you'll be ready for **Assignment 1.3 (IBM HR employee history)** on your own.

**Files covered:** `generate_sample_data.py`, `scd_pipeline.py`, `demo_queries.py`.

---

## The problem SCD solves (read this first)

A dimension attribute changes over time — a product moves department, a price rises, an employee changes role. If you **UPDATE it in place**, you lose history: a report for *last* quarter would show the product's *current* department, silently mis-attributing the past. SCD is how you keep history so that **a fact always reflects the world as it was at the time the fact happened.**

---

## Part A — `generate_sample_data.py`: manufacturing change over time

SCD only makes sense when data *changes*, so this generator produces **three monthly snapshots** of a product catalog and mutates a slice of products between each — exactly what a nightly extract from a source system delivers.

### The initial catalog (snapshot 1)
```python
def base_catalog():
    rows.append({
        "product_id": pid,      # business (natural) key — STABLE across versions
        "product_name": ...,
        "aisle": aisle_name,
        "department": ...,
        "unit_price": ...,
    })
```
`product_id` is the **business key** — it identifies the *same product* forever, across every version. Hold onto this concept; it's the anchor of the whole design.

### Mutating into the next snapshot
```python
def mutate(snapshot, n_new_start):
    # 1) 5% of products move aisle+department  (re-categorisation)
    # 2) 8% get a price change
    # 3) 2% get a name typo-fix
    # 4) 5 brand-new products appear
```
Four kinds of change, each testing a different part of the SCD logic:
- **Re-categorisation & price change** → these are *tracked* attributes; each must create a **new Type 2 version**.
- **Typo fix** → this is a *Type 1* attribute; it must update in place with **no new version** (a cosmetic fix isn't worth a history row).
- **New products** → must be **inserted** as fresh current rows.

Understanding *why these four cases exist* is understanding the whole merge algorithm.

### Orders reference the business key
```python
orders = build_orders(max_product_id=N_PRODUCTS)
```
Orders are spread across Jan–Mar and reference `product_id`. The fact table will later join each order to the *version valid on the order date* — that join is the payoff.

---

## Part B — `scd_pipeline.py`: the three SCD types

### Conventions, declared up front (do this in every SCD project)
```python
SENTINEL = "9999-12-31"          # "no end date yet" — never NULL
TRACKED_ATTRS = ["aisle", "department", "unit_price"]
```
- `SENTINEL` is used as the `effective_end_date` of current rows. Using a far-future date **instead of NULL** means the point-in-time `BETWEEN` join works without any `COALESCE` — a NULL end date would make `date BETWEEN start AND NULL` evaluate to NULL (falsy) and silently drop matches.
- `TRACKED_ATTRS` lists *only* the columns whose change creates a new version. `product_name` is deliberately **excluded** — it's our Type 1 attribute.

---

### SCD Type 1 — overwrite (history lost)
```python
def scd_type1_load(con, snapshot_csv):
    # UPDATE existing rows in place...
    UPDATE dim_product_type1 t
    SET product_name = s.product_name, aisle = s.aisle, ...
    FROM staging s WHERE t.product_id = s.product_id
    # ...INSERT brand-new rows
    INSERT INTO dim_product_type1
    SELECT s.* FROM staging s LEFT JOIN dim_product_type1 t ...
    WHERE t.product_id IS NULL
```
This is a plain **upsert**. After loading all three snapshots, `dim_product_type1` simply equals the *latest* snapshot — every prior value is gone. That's perfect for typos (who cares about the history of a spelling mistake?) and catastrophic for prices (you can no longer answer "what did this cost in January?").

---

### SCD Type 2 — the industry standard (study this closely)

The table schema encodes the whole idea:
```python
product_key           INTEGER,   -- surrogate: UNIQUE PER VERSION
product_id            INTEGER,   -- business key: stable per product
product_name          VARCHAR,   -- Type 1 attribute (hybrid design)
aisle / department / unit_price,  -- Type 2 tracked
effective_start_date  DATE,
effective_end_date    DATE,      -- '9999-12-31' = still current
is_current            BOOLEAN
```
Two keys, and this is the crux: **`product_key` changes with every version; `product_id` stays the same.** A product with 3 versions has 3 rows, 3 different `product_key`s, 1 shared `product_id`.

The merge, step by step:

**Step 2 — hybrid Type 1 pass (name fixes update all versions in place):**
```python
UPDATE dim_product_type2 d
SET product_name = s.product_name
FROM staging s
WHERE d.product_id = s.product_id AND d.product_name <> s.product_name
```
A typo fix overwrites `product_name` on **every** version of that product and creates **no** new row. This is what "hybrid SCD" means — Type 1 and Type 2 behavior *in the same table*, per attribute.

**Step 3 — detect tracked changes:**
```python
CREATE TEMP TABLE changed AS
SELECT s.*
FROM staging s
JOIN dim_product_type2 d ON s.product_id = d.product_id AND d.is_current
WHERE s.aisle      IS DISTINCT FROM d.aisle
   OR s.department IS DISTINCT FROM d.department
   OR s.unit_price IS DISTINCT FROM d.unit_price
```
We compare the incoming row to the **current** version, on **only the tracked attributes**. Two critical details:
- **`IS DISTINCT FROM`, not `<>`** — plain `<>` returns NULL when either side is NULL, and `WHERE NULL` skips the row. `IS DISTINCT FROM` treats NULL as a comparable value, so NULL→value transitions are caught. Using `<>` here is a classic silent SCD bug.
- **Only tracked attributes** — comparing *every* column (e.g. a `last_updated` timestamp) would create a new version on every load even when nothing meaningful changed. That's **"dimension explosion,"** and excluding noisy fields is how you prevent it.

**Step 4 — expire the outgoing versions:**
```python
UPDATE dim_product_type2 d
SET effective_end_date = DATE '{load_date}' - INTERVAL 1 DAY,
    is_current = FALSE
FROM changed c
WHERE d.product_id = c.product_id AND d.is_current
```
The old current row gets closed off: its `effective_end_date` becomes **the day before** the new version starts, and `is_current` flips to FALSE. Using *load_date − 1 day* guarantees **no overlap** between consecutive versions — which is what keeps the point-in-time join exactly 1:1.

**Step 5 — insert the new versions:**
```python
INSERT INTO dim_product_type2
SELECT
    (SELECT COALESCE(MAX(product_key), 0) FROM dim_product_type2)
      + ROW_NUMBER() OVER (ORDER BY c.product_id)  AS product_key,
    c.product_id, ..., DATE '{load_date}', DATE '{SENTINEL}', TRUE
FROM changed c
```
Each changed product gets a **brand-new surrogate key** (`MAX(key) + ROW_NUMBER()` guarantees uniqueness), starts on the load date, ends at the sentinel, and is marked current.

**Step 6 — brand-new products:**
```python
INSERT INTO dim_product_type2
SELECT ... FROM staging s
LEFT JOIN dim_product_type2 d ON s.product_id = d.product_id
WHERE d.product_id IS NULL
```
Products never seen before (no version exists at all) are inserted as fresh current rows.

The log line at the end reports changed/total/current counts — the numbers you'd sanity-check in production (e.g. after snapshot 2: `50 changed | 455 total, 405 current`).

---

### SCD Type 3 — previous-value column
```python
UPDATE dim_product_type3 t
SET previous_department = t.current_department,
    current_department  = s.department, ...
WHERE t.product_id = s.product_id
  AND t.current_department IS DISTINCT FROM s.department
```
Only `current_department` + `previous_department` are kept. When the department changes, the current value shifts into `previous`, and the new value becomes current. **Limitation to internalize:** a *second* change overwrites `previous_department` — Type 3 can only ever answer "what was it *immediately* before?" That's why it's rare.

---

### The fact table — the whole point of SCD Type 2
```python
CREATE TABLE fact_orders AS
SELECT o.order_id, o.order_date, o.quantity,
       d.product_key,
       o.quantity * d.unit_price AS line_revenue
FROM read_csv_auto('orders.csv') o
JOIN dim_product_type2 d
  ON  o.product_id = d.product_id
  AND o.order_date BETWEEN d.effective_start_date AND d.effective_end_date
```
**These two ON-clause lines are the most important lines in the entire project:**
```sql
ON  o.product_id = d.product_id                                        -- which product
AND o.order_date BETWEEN d.effective_start_date AND d.effective_end_date -- which VERSION
```
The join matches each order to the version that was **valid on the order date**, so `line_revenue` uses the price **charged at order time**, not today's price.

- Joining on **`is_current`** instead → stamps today's price onto historical orders. *Wrong.*
- Joining on **business key alone** → matches *all* versions, multiplying every order row. *Wrong.*

The date-range predicate is the only correct option. **Forgetting it is the #1 SCD bug** (Primer 1.3).

```python
assert facts == raw, f"point-in-time join produced {facts} rows from {raw} orders"
```
A hard gate proving the join is exactly 1:1. Fewer rows → a **gap** in the date ranges (some date matches no version). More rows → **overlapping** versions (a date matches two). Both mean the effective-date math is broken. This single assertion validates the entire Type 2 implementation.

---

### Orchestration
```python
if DB_PATH.exists():
    DB_PATH.unlink()          # rebuild from scratch each run (clean demo)
create_type2_table(con)
for load_date, csv in SNAPSHOTS:
    scd_type1_load(con, csv)
    scd_type2_merge(con, csv, load_date)
    scd_type3_load(con, csv)
build_fact_orders(con)
```
The snapshots are loaded **in date order** — that ordering is essential, because each Type 2 merge compares against the *current* state produced by the previous one.

---

## Part C — `demo_queries.py`: proving point-in-time correctness

The script picks a product that actually has multiple versions, then demonstrates the four canonical SCD queries.

**1. Current state:**
```sql
WHERE is_current
```
The `is_current` flag gives you "latest version of everything" without any date logic — the common case, kept fast.

**2. Point-in-time:**
```sql
WHERE product_id = 1
  AND DATE '2023-01-15' BETWEEN effective_start_date AND effective_end_date
```
Returns the *one* version valid on Jan 15. In the demo, product 1 shows department `snacks` here — even though its *current* department is `dairy eggs`. That's history preserved.

**3. Full history:** all versions of one `product_id` ordered by start date — you can literally see the timeline and the sentinel `9999-12-31` on the current row.

**4. Current vs. at-time-of-record (the payoff):**
```sql
SELECT f.order_id, f.order_date,
       d.unit_price   AS price_at_order_time,
       cp.unit_price  AS current_price,
       cp.unit_price - d.unit_price AS difference_if_naive_join
FROM fact_orders f
JOIN dim_product_type2 d ON f.product_key = d.product_key
CROSS JOIN current_price cp
WHERE d.product_id = <a product whose price changed>
```
For product 16, January orders show `price_at_order_time = 10.48` while `current_price = 11.08`. A report that naively joined facts to the current version would **overstate January revenue by 0.60 per unit**. This column *is* the business case for SCD Type 2 — put a number on the bug it prevents.

---

## Your Assignment 1.3 checklist, mapped to what you just learned

| Assignment requirement | Where this project taught it |
|---|---|
| Simulate 3 load batches, mutate ~15% between them | `generate_sample_data.py` `mutate()` |
| Type 2 dim: surrogate key, business key, effective dates, `is_current` | `create_type2_table` + `scd_type2_merge` |
| Merge logic: new version only when tracked attr changes; Type 1 vs 2 per attribute | steps 2–6, `TRACKED_ATTRS`, hybrid name handling |
| Fact joins to point-in-time-correct row; prove current vs at-time | `build_fact_orders` date-range join + demo query 4 |
| Document effective_end_date convention (null vs sentinel) | `SENTINEL = '9999-12-31'`, closed interval |
| Handle a late-arriving correction | *(your new bit — see below)* |

**The one thing this guided project doesn't do, that your assignment requires: late-arriving corrections.** That's when you learn *today* that an employee's department actually changed *two months ago*. You must insert a version *between* two existing ones and **re-split the surrounding date ranges** so no gap or overlap appears (or the 1:1 assertion fails). The `effective_end_date = load_date - 1 day` logic is your starting point — you'll adapt it to slot a version into the middle of the timeline. Now go build it for IBM HR.
