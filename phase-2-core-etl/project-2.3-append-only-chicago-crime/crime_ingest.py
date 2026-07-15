"""
Guided Project 2.3 — Append-Only Pipeline with Chicago Crime.

An append-only ingest that is **provably idempotent** via record hashing:

    * generate_record_hash()  -> MD5 fingerprint of the business-relevant fields
    * append_only_load()      -> insert ONLY records whose hash isn't present yet
    * ingested_at             -> audit timestamp on every stored row
    * ingest_audit table      -> separate, IMMUTABLE log of every batch run

Because consecutive source batches overlap, a naive INSERT would double-count.
Hashing makes re-ingesting the same records a guaranteed no-op — the core of
"exactly-once processing on top of at-least-once delivery" (Primer 2.3).

Run:
    python generate_sample_data.py
    python crime_ingest.py                       # loads batch 1
    python crime_ingest.py                        # re-run -> 0 new (idempotent)
    python crime_ingest.py --batch crime_batch_2.csv   # only truly-new records
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("crime_ingest")

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "data" / "crime.duckdb"

# The fields that define record identity. Two rows with the same values here
# are "the same crime" — even if delivered in two different batches.
HASH_FIELDS = ["ID", "Date", "Primary Type"]


def generate_record_hash(row: pd.Series) -> str:
    """MD5 fingerprint of the business key fields.

    Concatenate the identifying fields with a separator and hash. Using a
    separator ('|') prevents collisions like ('12','34') vs ('1','234').
    """
    key = "|".join(str(row[f]) for f in HASH_FIELDS)
    return hashlib.md5(key.encode()).hexdigest()


class CrimeIngest:
    """Append-only, hash-deduplicated ingest with an immutable audit log."""

    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        con = duckdb.connect(str(DB_PATH))
        # The fact table: append-only. record_hash is the dedup key.
        con.execute("""
            CREATE TABLE IF NOT EXISTS crimes (
                record_hash   VARCHAR PRIMARY KEY,
                ID            BIGINT,
                Date          VARCHAR,
                primary_type  VARCHAR,
                description   VARCHAR,
                arrest        BOOLEAN,
                district      INTEGER,
                latitude      DOUBLE,
                longitude     DOUBLE,
                ingested_at   TIMESTAMP
            )
        """)
        # The audit log: separate, IMMUTABLE, append-only. Never updated.
        con.execute("""
            CREATE TABLE IF NOT EXISTS ingest_audit (
                audit_id       BIGINT,
                batch_name     VARCHAR,
                ingested_at    TIMESTAMP,
                rows_in_batch  INTEGER,
                rows_inserted  INTEGER,
                rows_skipped   INTEGER,
                status         VARCHAR
            )
        """)
        con.close()

    def append_only_load(self, batch_path: Path) -> dict:
        """Load a batch, inserting only records whose hash isn't already stored.

        Steps:
          1. read the batch and compute a record_hash per row
          2. dedup WITHIN the batch (a batch can contain its own dupes)
          3. anti-join against existing hashes -> keep only truly-new records
          4. append the new records with an ingested_at timestamp
          5. write an audit-log row describing exactly what happened
        """
        batch = pd.read_csv(batch_path)
        rows_in_batch = len(batch)
        batch["record_hash"] = batch.apply(generate_record_hash, axis=1)

        # (2) A single batch may repeat a record; keep one copy.
        batch = batch.drop_duplicates(subset=["record_hash"], keep="first")

        con = duckdb.connect(str(DB_PATH))
        try:
            existing = set(r[0] for r in
                           con.execute("SELECT record_hash FROM crimes").fetchall())
            # (3) anti-join: only hashes we've never seen.
            new = batch[~batch["record_hash"].isin(existing)].copy()
            new["ingested_at"] = datetime.now()

            if not new.empty:
                # (4) append-only insert. Column order matches the table DDL.
                insert_df = new.rename(columns={
                    "Primary Type": "primary_type", "Description": "description",
                    "Arrest": "arrest", "District": "district",
                    "Latitude": "latitude", "Longitude": "longitude",
                })[["record_hash", "ID", "Date", "primary_type", "description",
                    "arrest", "district", "latitude", "longitude", "ingested_at"]]
                con.register("insert_df", insert_df)
                con.execute("INSERT INTO crimes SELECT * FROM insert_df")

            rows_inserted = len(new)
            rows_skipped = len(batch) - rows_inserted
            self._write_audit(con, batch_path.name, rows_in_batch,
                              rows_inserted, rows_skipped, "SUCCESS")
        finally:
            con.close()

        log.info("batch %-18s in=%d inserted=%d skipped(dupe)=%d",
                 batch_path.name, rows_in_batch, rows_inserted, rows_skipped)
        return {"batch": batch_path.name, "rows_in_batch": rows_in_batch,
                "rows_inserted": rows_inserted, "rows_skipped": rows_skipped}

    def _write_audit(self, con, batch_name, rows_in, inserted, skipped, status):
        """Append one immutable audit row. Never UPDATE or DELETE this table."""
        next_id = con.execute(
            "SELECT COALESCE(MAX(audit_id), 0) + 1 FROM ingest_audit").fetchone()[0]
        con.execute("""
            INSERT INTO ingest_audit VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [next_id, batch_name, datetime.now(), rows_in, inserted, skipped, status])

    def stats(self) -> None:
        con = duckdb.connect(str(DB_PATH), read_only=True)
        total = con.execute("SELECT COUNT(*) FROM crimes").fetchone()[0]
        audit = con.execute(
            "SELECT COUNT(*), SUM(rows_inserted) FROM ingest_audit").fetchone()
        log.info("crimes table: %d unique records | %d audit-log entries "
                 "(total inserted across runs: %s)", total, audit[0], audit[1])
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Append-only crime ingest")
    parser.add_argument("--batch", default="crime_batch_1.csv",
                        help="CSV filename in data/raw/ to ingest")
    args = parser.parse_args()

    ingest = CrimeIngest()
    ingest.append_only_load(RAW_DIR / args.batch)
    ingest.stats()


if __name__ == "__main__":
    main()
