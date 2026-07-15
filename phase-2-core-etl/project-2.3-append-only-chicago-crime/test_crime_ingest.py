"""
Tests for the append-only crime ingest.

The properties that matter:
    1. IDEMPOTENCY   — ingesting the same batch twice inserts 0 the second time.
    2. AT-LEAST-ONCE — feeding the same batch 3 times leaves final state correct.
    3. DEDUP ON OVERLAP — overlapping batches yield the UNION, not the sum.
    4. AUDIT LOG     — every run appends exactly one immutable audit row.

Run:  pytest test_crime_ingest.py -v
"""

from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest

import crime_ingest
from crime_ingest import CrimeIngest, generate_record_hash


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(crime_ingest, "DB_PATH", tmp_path / "crime.duckdb")
    monkeypatch.setattr(crime_ingest, "RAW_DIR", tmp_path / "raw")
    (tmp_path / "raw").mkdir()
    return tmp_path


def _write_batch(raw_dir: Path, name: str, start_id: int, n: int) -> Path:
    # Content is a function of the stable ID (not batch position), so a record
    # appearing in two batches is byte-identical -> same record_hash.
    rows = [{
        "ID": rid,
        "Date": f"08/01/2023 {(rid % 12) + 1:02d}:00:00 AM",
        "Primary Type": "THEFT",
        "Description": "OVER $500",
        "Arrest": bool(rid % 2),
        "District": 1 + (rid % 25),
        "Latitude": 41.8, "Longitude": -87.6,
    } for rid in range(start_id, start_id + n)]
    path = raw_dir / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _crime_count(db_path: Path) -> int:
    con = duckdb.connect(str(db_path), read_only=True)
    n = con.execute("SELECT COUNT(*) FROM crimes").fetchone()[0]
    con.close()
    return n


def test_record_hash_is_deterministic():
    row = pd.Series({"ID": 42, "Date": "08/01/2023 01:00:00 AM",
                     "Primary Type": "THEFT"})
    assert generate_record_hash(row) == generate_record_hash(row)


def test_record_hash_changes_with_content():
    a = pd.Series({"ID": 1, "Date": "d", "Primary Type": "THEFT"})
    b = pd.Series({"ID": 1, "Date": "d", "Primary Type": "BATTERY"})
    assert generate_record_hash(a) != generate_record_hash(b)


def test_first_load_inserts_all(isolated_db):
    batch = _write_batch(crime_ingest.RAW_DIR, "b1.csv", 1, 100)
    result = CrimeIngest().append_only_load(batch)
    assert result["rows_inserted"] == 100
    assert _crime_count(crime_ingest.DB_PATH) == 100


def test_rerun_inserts_zero(isolated_db):
    """THE idempotency test: same batch twice -> second run inserts nothing."""
    batch = _write_batch(crime_ingest.RAW_DIR, "b1.csv", 1, 100)
    ingest = CrimeIngest()
    ingest.append_only_load(batch)
    result2 = ingest.append_only_load(batch)
    assert result2["rows_inserted"] == 0
    assert result2["rows_skipped"] == 100
    assert _crime_count(crime_ingest.DB_PATH) == 100        # unchanged


def test_at_least_once_delivery_three_times(isolated_db):
    """Feed the same batch 3 times; final state must be exactly one copy."""
    batch = _write_batch(crime_ingest.RAW_DIR, "b1.csv", 1, 50)
    ingest = CrimeIngest()
    for _ in range(3):
        ingest.append_only_load(batch)
    assert _crime_count(crime_ingest.DB_PATH) == 50


def test_overlapping_batches_yield_union(isolated_db):
    """Batch 2 overlaps batch 1 -> total is the UNION, not the sum."""
    b1 = _write_batch(crime_ingest.RAW_DIR, "b1.csv", 1, 100)      # ids 1..100
    b2 = _write_batch(crime_ingest.RAW_DIR, "b2.csv", 81, 100)     # ids 81..180 (20 overlap)
    ingest = CrimeIngest()
    ingest.append_only_load(b1)
    ingest.append_only_load(b2)
    # Union of 1..100 and 81..180 = 1..180 = 180 unique records.
    assert _crime_count(crime_ingest.DB_PATH) == 180


def test_audit_log_is_append_only(isolated_db):
    batch = _write_batch(crime_ingest.RAW_DIR, "b1.csv", 1, 10)
    ingest = CrimeIngest()
    ingest.append_only_load(batch)
    ingest.append_only_load(batch)      # second run: 0 inserted, but still audited

    con = duckdb.connect(str(crime_ingest.DB_PATH), read_only=True)
    audit = con.execute(
        "SELECT rows_inserted, rows_skipped, status FROM ingest_audit ORDER BY audit_id"
    ).fetchall()
    con.close()

    assert len(audit) == 2                       # one row per run, never overwritten
    assert audit[0] == (10, 0, "SUCCESS")        # first run inserted all
    assert audit[1] == (0, 10, "SUCCESS")        # second run skipped all (dupes)
