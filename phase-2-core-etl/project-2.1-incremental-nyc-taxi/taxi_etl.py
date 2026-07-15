"""
Guided Project 2.1 — Incremental ETL with NYC Taxi.

Demonstrates the four things that separate a toy script from a production batch
pipeline:

    1. CHUNKED extraction       -> constant memory regardless of file size
    2. TRANSFORM                -> type-cast, derive features, filter outliers
    3. PARTITIONED Parquet load -> Hive-style year=/month= layout, dedup-on-write
    4. WATERMARK incremental    -> load only rows newer than last successful run

Watermark golden rule (Primer 2.1): advance the watermark ONLY AFTER a load
succeeds. Advancing first means silent data loss when a load fails.

Run:
    python generate_sample_data.py
    python taxi_etl.py                 # loads batch 1 (first run)
    python taxi_etl.py                 # re-run -> 0 rows (idempotent)
    python taxi_etl.py --source data/raw/taxi_batch_2.csv   # loads only new rows
"""

from __future__ import annotations

import argparse
import functools
import logging
import time
from pathlib import Path

import duckdb
import pandas as pd

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("taxi_etl")

BASE_DIR = Path(__file__).parent
DEFAULT_SOURCE = BASE_DIR / "data" / "raw" / "taxi_batch_1.csv"
WAREHOUSE_DIR = BASE_DIR / "data" / "warehouse"        # partitioned Parquet lands here
CONTROL_DB = BASE_DIR / "data" / "control.duckdb"      # watermark bookkeeping

CHUNK_SIZE = 500_000          # rows per chunk — the playbook's canonical value
LOOKBACK = pd.Timedelta("1h") # re-scan this far behind the watermark for late rows

# Outlier bounds (Primer 2.1): anything outside is a data error, not a real trip.
DISTANCE_RANGE = (0.05, 200.0)
FARE_RANGE = (0.01, 1000.0)
DURATION_RANGE = (0.5, 300.0)  # minutes


# --------------------------------------------------------------------------- #
# Retry decorator — transient failures (network, locks) are normal in batch ETL
# --------------------------------------------------------------------------- #

def retry(attempts: int = 3, backoff: float = 0.5):
    """Retry a function with exponential backoff. Re-raises after the last try."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delay = backoff
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:                       # noqa: BLE001
                    if attempt == attempts:
                        log.error("%s failed after %d attempts: %s",
                                  fn.__name__, attempts, exc)
                        raise
                    log.warning("%s attempt %d failed (%s); retrying in %.1fs",
                                fn.__name__, attempt, exc, delay)
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator


class TaxiETL:
    """Chunked, watermark-driven incremental loader for taxi trips."""

    def __init__(self, source_name: str):
        # The watermark is tracked PER SOURCE so multiple feeds don't clobber
        # each other's progress.
        self.source_name = source_name
        WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
        CONTROL_DB.parent.mkdir(parents=True, exist_ok=True)
        self._init_control_table()

    # ---- watermark control table ------------------------------------------ #

    def _init_control_table(self) -> None:
        con = duckdb.connect(str(CONTROL_DB))
        con.execute("""
            CREATE TABLE IF NOT EXISTS etl_watermark (
                source_name  VARCHAR PRIMARY KEY,
                watermark    TIMESTAMP,
                updated_at   TIMESTAMP
            )
        """)
        con.close()

    def get_watermark(self) -> pd.Timestamp:
        """Last successfully-loaded `updated_at`. Epoch 0 means 'never loaded'."""
        con = duckdb.connect(str(CONTROL_DB), read_only=True)
        row = con.execute(
            "SELECT watermark FROM etl_watermark WHERE source_name = ?",
            [self.source_name]).fetchone()
        con.close()
        return pd.Timestamp(row[0]) if row else pd.Timestamp("1970-01-01")

    def set_watermark(self, value: pd.Timestamp) -> None:
        """Advance the watermark. Called ONLY after a successful load."""
        con = duckdb.connect(str(CONTROL_DB))
        con.execute("""
            INSERT INTO etl_watermark (source_name, watermark, updated_at)
            VALUES (?, ?, now())
            ON CONFLICT (source_name)
            DO UPDATE SET watermark = excluded.watermark, updated_at = now()
        """, [self.source_name, value.to_pydatetime()])
        con.close()

    # ---- extract ---------------------------------------------------------- #

    def extract(self, source_path: Path):
        """Yield chunks of at most CHUNK_SIZE rows.

        Reading in chunks keeps memory flat whether the file is 40k rows or
        40 million — you never hold the whole file at once.
        """
        for chunk in pd.read_csv(source_path, chunksize=CHUNK_SIZE,
                                 parse_dates=["pickup_datetime",
                                              "dropoff_datetime", "updated_at"]):
            yield chunk

    # ---- transform -------------------------------------------------------- #

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Type-cast, derive features, and filter outliers. Returns clean rows."""
        df = df.copy()

        # Derived features (Primer 2.1). Duration in minutes drives an outlier
        # filter AND is a useful analytical column.
        df["trip_duration_min"] = (
            (df["dropoff_datetime"] - df["pickup_datetime"])
            .dt.total_seconds() / 60.0
        )
        df["year"] = df["pickup_datetime"].dt.year
        df["month"] = df["pickup_datetime"].dt.month
        df["hour"] = df["pickup_datetime"].dt.hour
        df["day_of_week"] = df["pickup_datetime"].dt.dayofweek

        before = len(df)
        # Outlier filter: keep only physically plausible trips. Each bound maps
        # to a real failure mode (negative fare, GPS glitch, clock skew).
        df = df[
            df["trip_distance"].between(*DISTANCE_RANGE)
            & df["fare_amount"].between(*FARE_RANGE)
            & df["trip_duration_min"].between(*DURATION_RANGE)
        ]
        log.info("transform: dropped %d/%d outlier rows (%.1f%%)",
                 before - len(df), before,
                 100 * (before - len(df)) / before if before else 0)
        return df

    # ---- load (partitioned, idempotent) ----------------------------------- #

    @retry(attempts=3)
    def _write_partition(self, year: int, month: int,
                         df: pd.DataFrame) -> int:
        """Write ONE (year, month) partition idempotently.

        Idempotency via dedup-on-write: read whatever is already in the
        partition, concat the new rows, drop duplicates on trip_id, rewrite.
        This is the "partition overwrite" idempotency technique (Primer 2.3) —
        re-loading the same rows can never create duplicates.
        """
        part_dir = WAREHOUSE_DIR / f"year={year}" / f"month={month:02d}"
        part_dir.mkdir(parents=True, exist_ok=True)
        part_file = part_dir / "data.parquet"

        if part_file.exists():
            existing = pd.read_parquet(part_file)
            combined = pd.concat([existing, df], ignore_index=True)
        else:
            combined = df
        combined = combined.drop_duplicates(subset=["trip_id"], keep="last")
        combined.to_parquet(part_file, index=False)
        return len(combined)

    def load(self, df: pd.DataFrame) -> int:
        """Route rows to their (year, month) partitions. Returns rows written."""
        written = 0
        for (year, month), part in df.groupby(["year", "month"]):
            total = self._write_partition(int(year), int(month), part)
            written += len(part)
            log.info("  partition year=%d/month=%02d: +%d rows (partition now %d)",
                     year, month, len(part), total)
        return written

    # ---- orchestration ---------------------------------------------------- #

    def incremental_load(self, source_path: Path) -> int:
        """Full incremental run: watermark filter -> transform -> load -> advance.

        Ordering is deliberate and load-bearing:
          1. read the current watermark
          2. keep only rows with updated_at > (watermark - lookback)
          3. transform + load them
          4. ONLY NOW advance the watermark to the max updated_at loaded
        If step 3 throws, step 4 never runs, so the next run safely reprocesses.
        """
        watermark = self.get_watermark()
        cutoff = watermark - LOOKBACK        # lookback catches late-arriving rows
        log.info("source=%s | watermark=%s | cutoff (with lookback)=%s",
                 source_path.name, watermark, cutoff)

        total_loaded, max_seen = 0, watermark
        for chunk in self.extract(source_path):
            new_rows = chunk[chunk["updated_at"] > cutoff]
            if new_rows.empty:
                continue
            max_seen = max(max_seen, new_rows["updated_at"].max())
            clean = self.transform(new_rows)
            total_loaded += self.load(clean)

        if total_loaded > 0:
            # Advance ONLY after every partition wrote successfully.
            self.set_watermark(max_seen)
            log.info("loaded %d rows; watermark advanced to %s",
                     total_loaded, max_seen)
        else:
            log.info("no new rows since watermark — nothing to do (idempotent)")
        return total_loaded


def main() -> None:
    parser = argparse.ArgumentParser(description="Incremental NYC taxi ETL")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE),
                        help="CSV to load (default: batch 1)")
    parser.add_argument("--source-name", default="nyc_taxi_trips",
                        help="Logical feed name the watermark is tracked under")
    args = parser.parse_args()

    etl = TaxiETL(source_name=args.source_name)
    etl.incremental_load(Path(args.source))


if __name__ == "__main__":
    main()
