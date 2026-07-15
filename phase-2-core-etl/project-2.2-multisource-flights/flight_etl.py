"""
Guided Project 2.2 — Multi-Table ETL with Flight Delays.

Joins three sources (flights + airlines + airports) into one enriched fact
table, handles nulls with an explicit *per-column* strategy, and bulk-loads
the result into a SQL database via SQLAlchemy.

Two rules this project drills (Primer 2.2):
    1. Before ANY join, state the expected cardinality and reconcile the row
       count after. INNER vs LEFT is a decision, not a default.
    2. NULL is not a value. Classify every null as structural, source-missing,
       or join-induced, and handle each differently.

Database: SQLite via SQLAlchemy (zero-infra, runs anywhere). To use Postgres
instead, change ONE line — the connection string:
    engine = create_engine("postgresql+psycopg2://de_user:de_pass@localhost:5432/de_warehouse")
Everything else (to_sql, indexes, queries) is identical.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("flight_etl")

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "data" / "flights.db"

# Sentinel for structural nulls in delay columns: a cancelled flight has no
# real delay, and -1 is unmistakably "not applicable" (no real delay is -1 min
# in a way that collides — negative means 'early', but never exactly this
# sentinel's role). We ALSO keep the boolean flags so consumers never confuse
# the sentinel with a real value.
DELAY_SENTINEL = -999


def extract() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the three raw sources."""
    flights = pd.read_csv(RAW_DIR / "flights.csv", parse_dates=["scheduled_departure"])
    airlines = pd.read_csv(RAW_DIR / "airlines.csv")
    airports = pd.read_csv(RAW_DIR / "airports.csv")
    log.info("extracted flights=%d airlines=%d airports=%d",
             len(flights), len(airlines), len(airports))
    return flights, airlines, airports


def transform(flights: pd.DataFrame, airlines: pd.DataFrame,
              airports: pd.DataFrame) -> pd.DataFrame:
    """Join the three sources and apply a per-column null strategy."""
    n_flights = len(flights)

    # --- JOIN 1: flights -> airlines -----------------------------------------
    # EXPECTED CARDINALITY: many flights : one airline. A LEFT join must NOT
    # change the flight row count. We assert that to catch a fan-out bug.
    merged = flights.merge(airlines, on="airline_code", how="left")
    assert len(merged) == n_flights, "airline join changed row count (fan-out!)"

    # --- JOIN 2: + origin airport --------------------------------------------
    merged = merged.merge(
        airports.rename(columns={"airport_code": "origin",
                                 "city": "origin_city",
                                 "state": "origin_state"}),
        on="origin", how="left")
    assert len(merged) == n_flights, "origin join changed row count"

    # --- JOIN 3: + destination airport ---------------------------------------
    merged = merged.merge(
        airports.rename(columns={"airport_code": "destination",
                                 "city": "dest_city",
                                 "state": "dest_state"}),
        on="destination", how="left")
    assert len(merged) == n_flights, "destination join changed row count"

    log.info("after 3 LEFT joins: %d rows (unchanged — no fan-out)", len(merged))

    # --- NULL STRATEGY, per column (the core of this project) ----------------

    # (a) STRUCTURAL nulls: cancelled flights have no delay by design.
    #     Fill with a sentinel AND keep the boolean flag so no one averages
    #     the sentinel as if it were a real delay.
    for col in ["departure_delay_min", "arrival_delay_min", "actual_elapsed_min"]:
        merged[col] = merged[col].fillna(DELAY_SENTINEL)

    # (b) Convenient boolean flags (already 0/1 in source) as real booleans.
    merged["is_cancelled"] = merged["cancelled"].astype(bool)
    merged["is_diverted"] = merged["diverted"].astype(bool)

    # (c) JOIN-INDUCED nulls: an unmatched airline/airport code. This is a
    #     data-coverage GAP worth surfacing, not silently hiding. Label it
    #     'UNKNOWN' and flag it so it shows up in quality reports.
    merged["airline_missing"] = merged["airline_name"].isna()
    merged["origin_missing"] = merged["origin_city"].isna()
    merged["dest_missing"] = merged["dest_city"].isna()
    merged["airline_name"] = merged["airline_name"].fillna("UNKNOWN")
    merged["origin_city"] = merged["origin_city"].fillna("UNKNOWN")
    merged["origin_state"] = merged["origin_state"].fillna("??")
    merged["dest_city"] = merged["dest_city"].fillna("UNKNOWN")
    merged["dest_state"] = merged["dest_state"].fillna("??")

    # (d) A null-GUARDED derived metric: only compute the schedule variance
    #     where actual elapsed is a REAL value (not the sentinel).
    real = merged["actual_elapsed_min"] != DELAY_SENTINEL
    merged["elapsed_variance_min"] = np.where(
        real, merged["actual_elapsed_min"] - merged["scheduled_elapsed_min"],
        DELAY_SENTINEL)

    log.info("null coverage: airline_missing=%d origin_missing=%d dest_missing=%d",
             merged["airline_missing"].sum(),
             merged["origin_missing"].sum(),
             merged["dest_missing"].sum())

    keep = [
        "flight_id", "flight_date", "airline_code", "airline_name",
        "origin", "origin_city", "origin_state",
        "destination", "dest_city", "dest_state",
        "scheduled_departure", "scheduled_elapsed_min", "actual_elapsed_min",
        "departure_delay_min", "arrival_delay_min", "elapsed_variance_min",
        "is_cancelled", "is_diverted",
        "airline_missing", "origin_missing", "dest_missing",
    ]
    return merged[keep]


def load(df: pd.DataFrame) -> None:
    """Bulk-load into SQL via SQLAlchemy, then add indexes for query speed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{DB_PATH}")

    # chunksize keeps each INSERT batch bounded (the SQLite/Postgres analogue
    # of chunked extraction). method="multi" packs many rows per INSERT stmt.
    df.to_sql("fact_flights", engine, if_exists="replace", index=False,
              chunksize=5_000, method="multi")
    log.info("loaded %d rows into fact_flights", len(df))

    # Indexes on the columns queries filter/group by. In a warehouse you index
    # AFTER the bulk load, never before (index maintenance would slow the load).
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_airline ON fact_flights(airline_code)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_origin ON fact_flights(origin)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_date ON fact_flights(flight_date)"))
    log.info("created indexes on airline_code, origin, flight_date")


def main() -> None:
    flights, airlines, airports = extract()
    fact = transform(flights, airlines, airports)
    load(fact)
    log.info("done — run: python run_queries.py")


if __name__ == "__main__":
    main()
