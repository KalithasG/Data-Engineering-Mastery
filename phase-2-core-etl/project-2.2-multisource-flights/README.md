# Project 2.2 — Multi-Table ETL with Flight Delays

> **Guided Project** from Phase 2 of the DE Playbook.
> Concepts: multi-source joins, join cardinality, INNER vs LEFT, NULL semantics, per-column null strategy, bulk DB load via SQLAlchemy.

📖 **Line-by-line walkthrough: [EXPLANATION.md](EXPLANATION.md).**

## What this project builds

Joins **three sources** — `flights` (fact-like) + `airlines` + `airports` (dimensions) — into one enriched `fact_flights` table, applies an **explicit per-column null strategy**, and bulk-loads the result into a SQL database via SQLAlchemy with indexes and 5 analytical queries.

## How to run

```bash
python generate_sample_data.py     # 3 sources with intentional unmatched keys + NaN delays
python flight_etl.py               # join + null handling + bulk load to SQLite
python run_queries.py              # reconciliation + 5 analytical queries
```

## Database note (SQLite vs Postgres)

This runs on **SQLite via SQLAlchemy** so it needs zero infrastructure. The SQLAlchemy API is identical to Postgres — to switch, change **one line** in `flight_etl.py`:
```python
# SQLite (default, zero-infra):
engine = create_engine(f"sqlite:///{DB_PATH}")
# Postgres (the playbook's target) — just swap the URL:
engine = create_engine("postgresql+psycopg2://de_user:de_pass@localhost:5432/de_warehouse")
```
`to_sql(chunksize=..., method="multi")`, index creation, and every query work unchanged.

## Design decisions

### 1. State cardinality before every join, then reconcile
Each join is **many flights : one dimension row**, so a LEFT join must leave the flight row count **unchanged**. The code `assert len(merged) == n_flights` after every join — if a dimension had a duplicate key, the join would fan out and the assertion trips immediately. `run_queries.py` prints a final reconciliation (`fact=20,000 vs raw=20,000 → OK`).

### 2. LEFT join, not INNER — and why it matters
Flights are the source of truth; we must keep **every** flight even if its airline/airport code is missing from the dimension. An INNER join would **silently drop** the 581 orphan-airline flights and 1,847 orphan-airport flights — the classic "why did my row count shrink?" bug. LEFT join keeps them, with nulls we then handle deliberately.

### 3. Three kinds of null, three strategies
| Null type | Example columns | Strategy | Why |
|---|---|---|---|
| **Structural** | `departure_delay_min` on cancelled flights | sentinel `-999` **+ keep `is_cancelled` flag** | a cancelled flight has no delay; the flag stops anyone averaging the sentinel as data |
| **Join-induced** | `airline_name`, `origin_city` on unmatched keys | `'UNKNOWN'` **+ `*_missing` flag** | a coverage gap worth surfacing in QA, not hiding |
| **Guarded derived** | `elapsed_variance_min` | computed only where `actual_elapsed <> sentinel` | never do math on a sentinel |

The sentinel is deliberately excluded from every average in `analytical_queries.sql` (`WHERE departure_delay_min <> -999`), so it can never pollute a metric.

### 4. Bulk load, then index
`to_sql(chunksize=5000, method="multi")` batches inserts (many rows per statement). Indexes are created **after** the load, never before — index maintenance during a bulk insert would slow it down. Indexes go on the columns queries filter/group by (`airline_code`, `origin`, `flight_date`).

## Deliverables checklist

- [x] Multi-source join pipeline (`flight_etl.py`)
- [x] Null-handling documentation per column (table above + inline comments)
- [x] SQL schema with indexes (SQLite; Postgres = one-line swap)
- [x] 5 analytical queries (`analytical_queries.sql`) + reconciliation
