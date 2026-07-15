"""
Generate Chicago-crime-style records delivered as OVERLAPPING daily batches.

Mirrors the Kaggle "Chicago Crime" dataset columns (ID, Date, Primary Type,
Description, Arrest, District, ...). The key characteristic for an append-only
pipeline is that **consecutive batches overlap** — the source re-sends recent
records — so the loader MUST deduplicate or it will double-count.

Writes three batches with deliberate overlap:
    data/raw/crime_batch_1.csv   records 1..N
    data/raw/crime_batch_2.csv   overlaps last ~20% of batch 1 + new records
    data/raw/crime_batch_3.csv   overlaps last ~20% of batch 2 + new records

Loading all three should yield the UNION (deduplicated), not the sum.
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 44
random.seed(SEED)
np.random.seed(SEED)

RAW_DIR = Path(__file__).parent / "data" / "raw"

PRIMARY_TYPES = ["THEFT", "BATTERY", "CRIMINAL DAMAGE", "ASSAULT", "BURGLARY",
                 "NARCOTICS", "ROBBERY", "MOTOR VEHICLE THEFT", "DECEPTIVE PRACTICE"]
DESCRIPTIONS = ["OVER $500", "SIMPLE", "TO PROPERTY", "FORCIBLE ENTRY",
                "POCKET-PICKING", "AUTOMOBILE", "FROM BUILDING"]


def build_master(max_id: int) -> pd.DataFrame:
    """Build ONE canonical record per ID.

    Every field is a deterministic function of the ID (via a per-ID seeded
    RNG), so a record delivered in two overlapping batches is BYTE-IDENTICAL.
    That's what makes overlapping batches true duplicates — exactly what the
    real source does when it re-sends recent records.
    """
    base = datetime(2023, 8, 1, 0, 0, 0)
    rows = []
    for rid in range(1, max_id + 1):
        rng = random.Random(rid)               # identity keyed on ID, not position
        dt = base + timedelta(hours=rid * 2, minutes=rng.randint(0, 59))
        rows.append({
            "ID": rid,                                    # source primary key
            "Date": dt.strftime("%m/%d/%Y %I:%M:%S %p"),  # Chicago's exact format
            "Primary Type": rng.choice(PRIMARY_TYPES),
            "Description": rng.choice(DESCRIPTIONS),
            "Arrest": rng.choice([True, False]),
            "District": rng.randint(1, 25),
            "Latitude": round(41.6 + rng.random() * 0.4, 6),
            "Longitude": round(-87.9 + rng.random() * 0.4, 6),
        })
    return pd.DataFrame(rows)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    master = build_master(2600)
    # Slice overlapping batches from the SAME master so overlapping ids are
    # identical rows (identical record_hash), not merely same-id-different-data.
    b1 = master[master["ID"].between(1, 1000)]        # ids 1..1000
    b2 = master[master["ID"].between(801, 1800)]      # overlaps 801..1000
    b3 = master[master["ID"].between(1601, 2600)]     # overlaps 1601..1800

    for name, df in [("crime_batch_1.csv", b1),
                     ("crime_batch_2.csv", b2),
                     ("crime_batch_3.csv", b3)]:
        (RAW_DIR / name).write_text(df.to_csv(index=False))
        print(f"wrote {name}: {len(df):,} rows | ID {df['ID'].min()}..{df['ID'].max()}")

    total_unique = pd.concat([b1, b2, b3])["ID"].nunique()
    total_rows = len(b1) + len(b2) + len(b3)
    print(f"\ncombined: {total_rows:,} rows across batches, "
          f"but only {total_unique:,} UNIQUE ids "
          f"({total_rows - total_unique:,} overlapping duplicates to dedup)")


if __name__ == "__main__":
    main()
