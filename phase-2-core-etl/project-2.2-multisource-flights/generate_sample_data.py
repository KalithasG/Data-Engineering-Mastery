"""
Generate flight-delay data across THREE sources, to be joined by the ETL.

Mirrors the Kaggle "Flight Delays and Cancellations" dataset shape:

    data/raw/flights.csv    fact-like: one row per scheduled flight
    data/raw/airlines.csv   dimension: airline_code -> airline_name
    data/raw/airports.csv   dimension: airport_code -> city/state/name

Deliberate imperfections the ETL must handle:
    * some flights reference an airline/airport code NOT in the dimension
      (unmatched keys -> LEFT JOIN produces nulls to surface)
    * cancelled flights have NaN delay columns BY DESIGN (structural nulls)
    * diverted flights have NaN arrival delay
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 33
random.seed(SEED)
np.random.seed(SEED)

RAW_DIR = Path(__file__).parent / "data" / "raw"
N_FLIGHTS = 20_000

AIRLINES = {
    "AA": "American Airlines", "DL": "Delta Air Lines", "UA": "United Airlines",
    "WN": "Southwest Airlines", "B6": "JetBlue Airways", "AS": "Alaska Airlines",
    "NK": "Spirit Airlines", "F9": "Frontier Airlines",
}
AIRPORTS = {
    "ATL": ("Atlanta", "GA"), "LAX": ("Los Angeles", "CA"),
    "ORD": ("Chicago", "IL"), "DFW": ("Dallas", "TX"),
    "DEN": ("Denver", "CO"), "JFK": ("New York", "NY"),
    "SFO": ("San Francisco", "CA"), "SEA": ("Seattle", "WA"),
    "LAS": ("Las Vegas", "NV"), "MIA": ("Miami", "FL"),
}
# Codes that appear in flights but are intentionally MISSING from the dims,
# so LEFT JOINs produce nulls we have to reason about.
ORPHAN_AIRLINE = "XX"       # a defunct carrier not in airlines.csv
ORPHAN_AIRPORT = "ZZZ"      # a small airport not in airports.csv


def build_airlines() -> pd.DataFrame:
    return pd.DataFrame(
        [{"airline_code": k, "airline_name": v} for k, v in AIRLINES.items()])


def build_airports() -> pd.DataFrame:
    return pd.DataFrame(
        [{"airport_code": k, "city": c, "state": s}
         for k, (c, s) in AIRPORTS.items()])


def build_flights() -> pd.DataFrame:
    airline_codes = list(AIRLINES.keys()) + [ORPHAN_AIRLINE]
    airport_codes = list(AIRPORTS.keys()) + [ORPHAN_AIRPORT]
    base = datetime(2023, 6, 1)

    rows = []
    for i in range(N_FLIGHTS):
        dep = base + timedelta(days=random.randint(0, 29),
                               hours=random.randint(5, 23),
                               minutes=random.choice([0, 15, 30, 45]))
        sched_elapsed = random.randint(60, 360)          # scheduled minutes
        cancelled = random.random() < 0.03
        diverted = (not cancelled) and random.random() < 0.01

        dep_delay = np.round(np.random.normal(8, 30), 0)  # can be negative (early)
        arr_delay = dep_delay + np.round(np.random.normal(0, 10), 0)
        actual_elapsed = sched_elapsed + (arr_delay - dep_delay)

        rows.append({
            "flight_id": i + 1,
            "flight_date": dep.date(),
            # 3% of rows use the orphan airline code -> unmatched in dim
            "airline_code": (ORPHAN_AIRLINE if random.random() < 0.03
                             else random.choice(list(AIRLINES.keys()))),
            "origin": random.choice(airport_codes),
            "destination": random.choice(airport_codes),
            "scheduled_departure": dep,
            "scheduled_elapsed_min": sched_elapsed,
            # Cancelled flights never departed -> delay columns are NaN.
            "departure_delay_min": np.nan if cancelled else dep_delay,
            # Cancelled OR diverted -> no arrival delay.
            "arrival_delay_min": (np.nan if (cancelled or diverted) else arr_delay),
            "actual_elapsed_min": (np.nan if cancelled else actual_elapsed),
            "cancelled": int(cancelled),
            "diverted": int(diverted),
        })
    return pd.DataFrame(rows)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in [("airlines.csv", build_airlines()),
                     ("airports.csv", build_airports()),
                     ("flights.csv", build_flights())]:
        path = RAW_DIR / name
        df.to_csv(path, index=False)
        print(f"wrote {name}: {len(df):,} rows")

    flights = pd.read_csv(RAW_DIR / "flights.csv")
    print(f"  cancelled: {flights['cancelled'].sum()} | "
          f"diverted: {flights['diverted'].sum()} | "
          f"orphan-airline rows: {(flights['airline_code'] == ORPHAN_AIRLINE).sum()}")


if __name__ == "__main__":
    main()
