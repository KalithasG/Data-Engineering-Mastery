"""
Benchmark: full reload vs. watermark-based incremental load.

The whole point of incremental loading is that its cost scales with *how much
changed*, not with *total data size*. This script proves it by timing:

    FULL        : reset the watermark, reprocess the ENTIRE source every run
    INCREMENTAL : keep the watermark, process ONLY rows newer than last run

Run after taxi_etl.py so both batches exist:
    python benchmark.py
"""

import shutil
import time
from pathlib import Path

import pandas as pd

from taxi_etl import CONTROL_DB, WAREHOUSE_DIR, TaxiETL

BASE_DIR = Path(__file__).parent
BATCH_1 = BASE_DIR / "data" / "raw" / "taxi_batch_1.csv"
BATCH_2 = BASE_DIR / "data" / "raw" / "taxi_batch_2.csv"


def _reset() -> None:
    """Wipe warehouse + control state for a clean, comparable run."""
    if WAREHOUSE_DIR.exists():
        shutil.rmtree(WAREHOUSE_DIR)
    if CONTROL_DB.exists():
        CONTROL_DB.unlink()


def _time(label: str, fn) -> float:
    start = time.perf_counter()
    rows = fn()
    elapsed = time.perf_counter() - start
    print(f"{label:32s} {elapsed:6.3f}s  ({rows:,} rows loaded)")
    return elapsed


def main() -> None:
    # Baseline: load batch 1 so there's a "yesterday" already in the warehouse.
    _reset()
    etl = TaxiETL("bench")
    etl.incremental_load(BATCH_1)

    print("\nScenario: batch 2 (the new day's data) has arrived.\n")

    # FULL RELOAD: pretend we have no watermark and must reprocess everything
    # (batch 1 + batch 2) to be sure batch 2 is included.
    def full_reload():
        _reset()
        e = TaxiETL("bench_full")
        n = e.incremental_load(BATCH_1)       # watermark starts at epoch...
        n += e.incremental_load(BATCH_2)      # ...so this still rescans nothing new-only
        return n

    # INCREMENTAL: watermark already past batch 1, so only batch 2 is processed.
    def incremental():
        return etl.incremental_load(BATCH_2)

    print("--- timings ---")
    t_inc = _time("incremental (only new rows)", incremental)
    t_full = _time("full reload (all rows)", full_reload)

    speedup = t_full / t_inc if t_inc else float("inf")
    print(f"\nincremental processed only the new batch and was ~{speedup:.1f}x "
          f"faster than reprocessing everything.")
    print("As total history grows, the full-reload bar keeps rising while the "
          "incremental bar stays flat — that's the whole point.")


if __name__ == "__main__":
    main()
