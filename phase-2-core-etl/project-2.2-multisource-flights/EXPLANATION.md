# Project 2.2 — Line-by-Line Explanation

Walks through the multi-source flight ETL. After this you'll be ready for **Assignment 2.2 (Craigslist used cars, multi-source merge with conflicting data)** on your own.

**Files covered:** `generate_sample_data.py`, `flight_etl.py`, `analytical_queries.sql`, `run_queries.py`.

---

## The two big ideas (read first)

1. **Every join has a cardinality.** Before you write `merge`, you must know: is this one-to-one, one-to-many, or many-to-many? Guessing is how you silently double-count. After every join, reconcile the row count against what you expected.
2. **NULL is not a value; it's the absence of one.** `NULL = NULL` is not true, it's *unknown*. Aggregates skip nulls, null join keys never match, and a null can mean three completely different things — each needing a different fix.

---

## Part A — `generate_sample_data.py`

### Three sources, one fact + two dimensions
```python
("airlines.csv", build_airlines())   # airline_code -> airline_name   (dimension)
("airports.csv", build_airports())   # airport_code -> city, state    (dimension)
("flights.csv", build_flights())     # one row per flight             (fact-like)
```
This is a mini star schema arriving as **separate files** — your job is to join them.

### Deliberate unmatched keys
```python
ORPHAN_AIRLINE = "XX"      # in flights.csv, NOT in airlines.csv
ORPHAN_AIRPORT = "ZZZ"     # in flights.csv, NOT in airports.csv
```
3% of flights use `XX`, and `ZZZ` is a valid origin/destination choice. These produce **join-induced nulls** — the LEFT join finds no matching dimension row. Without them you'd never learn to handle join-induced nulls.

### Structural nulls by construction
```python
"departure_delay_min": np.nan if cancelled else dep_delay,
"arrival_delay_min":  np.nan if (cancelled or diverted) else arr_delay,
```
A cancelled flight *never departed*, so it has no delay — the NaN is **structural** ("not applicable"), not "missing data." A diverted flight has a departure but no normal arrival. Recognizing that these NaNs are *correct* is the "when NOT to clean" lesson from Phase 1, applied to joins.

---

## Part B — `flight_etl.py`

### `extract` — three DataFrames
```python
flights = pd.read_csv(..., parse_dates=["scheduled_departure"])
airlines = pd.read_csv(...)
airports = pd.read_csv(...)
```
Straightforward. `parse_dates` casts the timestamp at read time.

### `transform` — join 1, with a cardinality assertion
```python
n_flights = len(flights)
merged = flights.merge(airlines, on="airline_code", how="left")
assert len(merged) == n_flights, "airline join changed row count (fan-out!)"
```
- **`how="left"`** keeps every flight even when the airline code is unmatched. INNER would drop the 581 `XX` flights silently.
- **The assertion is the discipline.** Expected cardinality is many-flights-to-one-airline, so the row count *must* be unchanged. If `airlines.csv` accidentally had two rows for `AA`, the merge would fan out to `n_flights + extra` and the assertion fires. **This one line catches the single most common multi-source bug.** (Assignment 2.2 requires exactly this: "use COUNT(*) before/after each join; reconcile surprises.")

### Joins 2 and 3 — renaming to avoid column collisions
```python
merged = merged.merge(
    airports.rename(columns={"airport_code": "origin",
                             "city": "origin_city", "state": "origin_state"}),
    on="origin", how="left")
```
The airports dimension is joined **twice** — once as origin, once as destination — so its columns are renamed each time (`origin_city` vs `dest_city`). Without renaming you'd get `city_x` / `city_y` collisions. Each join re-asserts the row count.

### The null strategy — three distinct branches

**(a) Structural nulls → sentinel + keep the flag:**
```python
for col in ["departure_delay_min", "arrival_delay_min", "actual_elapsed_min"]:
    merged[col] = merged[col].fillna(DELAY_SENTINEL)   # -999
merged["is_cancelled"] = merged["cancelled"].astype(bool)
```
Cancelled-flight delays become `-999`. **Why a sentinel and not 0?** Because 0 is a *real* value (an on-time flight has 0 delay) — using 0 would corrupt the average. `-999` is unmistakably "not applicable." And we keep `is_cancelled` so any consumer can filter the sentinel out. (The queries do exactly that: `WHERE departure_delay_min <> -999`.)

**(b) Join-induced nulls → label + flag:**
```python
merged["airline_missing"] = merged["airline_name"].isna()   # flag BEFORE filling
merged["airline_name"] = merged["airline_name"].fillna("UNKNOWN")
```
An unmatched key is a **data-coverage gap** — worth *surfacing*, not hiding. We record a boolean flag *before* filling, then label the value `'UNKNOWN'`. Query Q4 (`coverage_gaps`) turns these flags into a QA metric. This is the opposite of a silent `COALESCE` buried in query logic.

**(c) Null-guarded derived metric:**
```python
real = merged["actual_elapsed_min"] != DELAY_SENTINEL
merged["elapsed_variance_min"] = np.where(
    real, merged["actual_elapsed_min"] - merged["scheduled_elapsed_min"],
    DELAY_SENTINEL)
```
`np.where(condition, if_true, if_false)` computes the variance **only** where `actual_elapsed` is a real value; sentinel rows stay sentinel. Never do arithmetic on a sentinel — `-999 - 120` would produce a garbage "variance" that pollutes downstream aggregates.

### `load` — bulk insert then index
```python
df.to_sql("fact_flights", engine, if_exists="replace", index=False,
          chunksize=5_000, method="multi")
```
- **`chunksize=5000`** batches the insert — the DB analogue of chunked extraction, keeping memory and transaction size bounded.
- **`method="multi"`** packs many rows into each `INSERT` statement (far fewer round-trips than row-by-row).
- **`if_exists="replace"`** makes the whole load idempotent (re-running rebuilds the table cleanly).
```python
with engine.begin() as conn:
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_airline ON fact_flights(airline_code)"))
```
Indexes are created **after** the bulk load. Indexing during a load forces the DB to maintain the index on every insert — slower. Load first, index after. Indexes go on the columns the queries filter and group by. `engine.begin()` wraps them in a transaction.

---

## Part C — `analytical_queries.sql` & `run_queries.py`

### The sentinel is excluded from every metric
```sql
WHERE departure_delay_min <> -999
```
Every average over a delay column filters out the structural sentinel first. This is the payoff of choosing `-999` over `0` — a single `WHERE` cleanly removes non-applicable rows.

### Q4 surfaces the coverage gap as a number
```sql
SELECT SUM(airline_missing) AS unmatched_airline,
       SUM(origin_missing)  AS unmatched_origin, ...
```
The join-induced-null flags become a QA metric: "1,847 rows reference an airport we don't have." That's information for the upstream team, not something to bury.

### Reconciliation in `run_queries.py`
```python
print(f"reconciliation: fact_flights={fact_rows} vs raw flights={raw_rows} "
      f"-> {'OK (1:1, no fan-out)' if fact_rows == raw_rows else 'MISMATCH!'}")
```
A final proof that the three joins neither dropped nor multiplied rows.

---

## Your Assignment 2.2 checklist, mapped to what you just learned

| Assignment requirement | Where this project taught it |
|---|---|
| State expected cardinality + row-count range before each join | `n_flights` + `assert len(merged) == n_flights` |
| COUNT(*) before/after each join; reconcile surprises | the per-join asserts + reconciliation print |
| Classify ≥5 columns' nulls (structural / source-missing / join-induced) | the three-branch null strategy + the README table |
| Explicit conflict-resolution rule + `_data_quality_flag` | `*_missing` flags (extend to a conflict rule for cars) |
| One query wrong under INNER vs correct under LEFT, with row diff | see below |

**The INNER-vs-LEFT query** (Assignment 2.2's last requirement): count flights by airline with an INNER join vs a LEFT join. INNER silently omits the 581 `XX` flights (total 19,419); LEFT keeps them under `UNKNOWN` (total 20,000). Showing that 581-row difference *is* the deliverable — it's the concrete cost of choosing the wrong join. For the cars dataset you'll invent a conflict-resolution rule (e.g. "when price differs between two sources, most-recently-updated wins") and add a `_data_quality_flag` where sources disagree. Now go build it.
