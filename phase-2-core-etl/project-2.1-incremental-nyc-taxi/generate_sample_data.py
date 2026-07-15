"""
Generate NYC-taxi-style trip records for the incremental-ETL project.

The real dataset ("NYC TLC Trip Records" on Kaggle) is tens of millions of rows
of yellow/green cab trips. This generator produces the same *shape* — pickup /
dropoff timestamps, distances, fares — plus two things the ETL specifically
needs:

    * an `updated_at` column      -> the WATERMARK column the loader tracks
    * deliberate OUTLIERS         -> negative fares, 0-distance, 999-mile trips
                                     so the transform's filters have real work

It writes TWO batches so you can actually see incremental loading work:

    data/raw/taxi_batch_1.csv   -> updated_at in the FIRST half of the window
    data/raw/taxi_batch_2.csv   -> updated_at in the SECOND half (the "new" data)

Run taxi_etl.py once (loads batch 1), then point it at batch 2 to load only the
new rows. Re-running either is a no-op (idempotent).
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 21
random.seed(SEED)
np.random.seed(SEED)

RAW_DIR = Path(__file__).parent / "data" / "raw"

N_BATCH_1 = 40_000
N_BATCH_2 = 15_000
WINDOW_START = datetime(2023, 1, 1)
WINDOW_MID = datetime(2023, 4, 1)
WINDOW_END = datetime(2023, 7, 1)


def make_trips(n: int, updated_start: datetime, updated_end: datetime,
               id_offset: int) -> pd.DataFrame:
    """Build n trip rows whose `updated_at` falls in [updated_start, updated_end)."""
    span = (updated_end - updated_start).total_seconds()

    pickups, dropoffs, updated = [], [], []
    for _ in range(n):
        # updated_at drives the watermark; spread it across the batch window.
        upd = updated_start + timedelta(seconds=random.uniform(0, span))
        # pickup is roughly when the trip happened (near updated_at).
        pickup = upd - timedelta(minutes=random.uniform(0, 120))
        duration_min = np.random.exponential(12) + 1          # skewed, realistic
        dropoff = pickup + timedelta(minutes=duration_min)
        pickups.append(pickup)
        dropoffs.append(dropoff)
        updated.append(upd)

    df = pd.DataFrame({
        "trip_id": np.arange(id_offset, id_offset + n),        # stable business key
        "vendor_id": np.random.choice([1, 2], size=n),
        "pickup_datetime": pickups,
        "dropoff_datetime": dropoffs,
        "passenger_count": np.random.choice([1, 1, 1, 2, 3, 4, 5, 6], size=n),
        "trip_distance": np.round(np.random.exponential(2.5, size=n), 2),
        "fare_amount": np.round(np.random.exponential(11, size=n) + 2.5, 2),
        "payment_type": np.random.choice(["card", "cash"], size=n, p=[0.7, 0.3]),
        "updated_at": updated,
    })

    # --- inject deliberate OUTLIERS (~4%) the transform must filter out -----
    bad = df.sample(frac=0.04, random_state=SEED).index
    third = len(bad) // 3
    # negative / zero fares (data-entry errors)
    df.loc[bad[:third], "fare_amount"] = np.random.choice([-5.0, 0.0, -12.5],
                                                          size=third)
    # absurd distances (GPS glitches)
    df.loc[bad[third:2 * third], "trip_distance"] = np.random.choice(
        [0.0, 250.0, 999.9], size=third)
    # dropoff before pickup -> negative duration (clock issues)
    df.loc[bad[2 * third:], "dropoff_datetime"] = (
        df.loc[bad[2 * third:], "pickup_datetime"] - timedelta(hours=1))
    return df


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    batch1 = make_trips(N_BATCH_1, WINDOW_START, WINDOW_MID, id_offset=1)
    batch2 = make_trips(N_BATCH_2, WINDOW_MID, WINDOW_END,
                        id_offset=1 + N_BATCH_1)

    for name, df in [("taxi_batch_1.csv", batch1), ("taxi_batch_2.csv", batch2)]:
        path = RAW_DIR / name
        df.to_csv(path, index=False)
        print(f"wrote {name}: {len(df):,} rows | "
              f"updated_at {df['updated_at'].min()} .. {df['updated_at'].max()}")


if __name__ == "__main__":
    main()
