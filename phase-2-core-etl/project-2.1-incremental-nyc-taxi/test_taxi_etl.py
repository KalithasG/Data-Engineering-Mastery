"""
Tests for the incremental taxi ETL.

The two properties that matter for a production batch pipeline:
    1. IDEMPOTENCY  — re-running never creates duplicates (safe to retry).
    2. WATERMARK SAFETY — a crash mid-load must NOT advance the watermark,
       so the next run reprocesses the failed batch instead of skipping it.

Run:  pytest test_taxi_etl.py -v
"""

import shutil
from pathlib import Path

import duckdb
import pandas as pd
import pytest

import taxi_etl
from taxi_etl import TaxiETL


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Point the ETL at a throwaway warehouse + control DB per test."""
    warehouse = tmp_path / "warehouse"
    control = tmp_path / "control.duckdb"
    monkeypatch.setattr(taxi_etl, "WAREHOUSE_DIR", warehouse)
    monkeypatch.setattr(taxi_etl, "CONTROL_DB", control)
    return tmp_path


def _make_source(path: Path, n: int, start: str, id_offset: int = 1) -> Path:
    """Write a tiny valid taxi CSV with updated_at spread over one day."""
    ts = pd.date_range(start, periods=n, freq="min")
    df = pd.DataFrame({
        "trip_id": range(id_offset, id_offset + n),
        "vendor_id": 1,
        "pickup_datetime": ts,
        "dropoff_datetime": ts + pd.Timedelta("10min"),
        "passenger_count": 1,
        "trip_distance": 3.0,
        "fare_amount": 12.5,
        "payment_type": "card",
        "updated_at": ts,
    })
    df.to_csv(path, index=False)
    return path


def _warehouse_count(warehouse: Path) -> int:
    files = list(warehouse.rglob("*.parquet"))
    if not files:
        return 0
    return duckdb.sql(
        f"SELECT COUNT(*) FROM read_parquet('{warehouse}/**/*.parquet')"
    ).fetchone()[0]


def _duplicate_count(warehouse: Path) -> int:
    return duckdb.sql(
        f"SELECT COUNT(*) - COUNT(DISTINCT trip_id) "
        f"FROM read_parquet('{warehouse}/**/*.parquet')"
    ).fetchone()[0]


def test_first_load_writes_all_rows(isolated_env):
    src = _make_source(isolated_env / "s.csv", 100, "2023-01-01")
    etl = TaxiETL("t")
    loaded = etl.incremental_load(src)
    assert loaded == 100
    assert _warehouse_count(taxi_etl.WAREHOUSE_DIR) == 100


def test_rerun_creates_no_duplicates(isolated_env):
    """THE idempotency test: loading the same source twice = no duplicates."""
    src = _make_source(isolated_env / "s.csv", 100, "2023-01-01")
    etl = TaxiETL("t")
    etl.incremental_load(src)
    count_after_first = _warehouse_count(taxi_etl.WAREHOUSE_DIR)

    etl.incremental_load(src)                      # re-run identical input
    count_after_second = _warehouse_count(taxi_etl.WAREHOUSE_DIR)

    # The lookback window may re-scan a few rows, but dedup-on-write means the
    # warehouse total is unchanged and there are zero duplicate trip_ids.
    assert count_after_second == count_after_first
    assert _duplicate_count(taxi_etl.WAREHOUSE_DIR) == 0


def test_new_rows_load_incrementally(isolated_env):
    src1 = _make_source(isolated_env / "s1.csv", 50, "2023-01-01", id_offset=1)
    src2 = _make_source(isolated_env / "s2.csv", 30, "2023-02-01", id_offset=51)
    etl = TaxiETL("t")
    etl.incremental_load(src1)
    loaded2 = etl.incremental_load(src2)
    assert loaded2 == 30
    assert _warehouse_count(taxi_etl.WAREHOUSE_DIR) == 80


def test_watermark_not_advanced_on_load_failure(isolated_env, monkeypatch):
    """If load() throws, the watermark must stay put so we can retry safely."""
    src = _make_source(isolated_env / "s.csv", 50, "2023-01-01")
    etl = TaxiETL("t")
    watermark_before = etl.get_watermark()

    # Simulate a crash inside load() (e.g. disk full, DB down).
    def boom(_df):
        raise RuntimeError("simulated disk failure mid-load")
    monkeypatch.setattr(etl, "load", boom)

    with pytest.raises(RuntimeError):
        etl.incremental_load(src)

    # Watermark unchanged -> next run reprocesses this batch, no data lost.
    assert etl.get_watermark() == watermark_before
    assert _warehouse_count(taxi_etl.WAREHOUSE_DIR) == 0


def test_outliers_are_filtered(isolated_env):
    src = isolated_env / "dirty.csv"
    ts = pd.date_range("2023-01-01", periods=4, freq="min")
    pd.DataFrame({
        "trip_id": [1, 2, 3, 4],
        "vendor_id": 1,
        "pickup_datetime": ts,
        "dropoff_datetime": ts + pd.Timedelta("10min"),
        "passenger_count": 1,
        "trip_distance": [3.0, 999.9, 3.0, 3.0],      # row 2: absurd distance
        "fare_amount": [12.5, 12.5, -5.0, 12.5],       # row 3: negative fare
        "payment_type": "card",
        "updated_at": ts,
    }).to_csv(src, index=False)

    etl = TaxiETL("t")
    loaded = etl.incremental_load(src)
    assert loaded == 2          # only the two clean rows survive
