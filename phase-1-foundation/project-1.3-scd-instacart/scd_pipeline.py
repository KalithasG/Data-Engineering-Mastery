"""
Guided Project 1.3 — Slowly Changing Dimensions with Instacart-style data.

Implements all three classic SCD types against three monthly catalog
snapshots, then builds a fact table that joins to the point-in-time-correct
dimension version.

    dim_product_type1  — overwrite in place        (history lost)
    dim_product_type2  — new row per version       (full history; the standard)
    dim_product_type3  — previous_* column         (one prior state only)

Type 2 conventions used here (document yours and stick to them!):
    * surrogate key  : product_key  (new value per VERSION)
    * business key   : product_id   (stable across versions)
    * closed interval: effective_start_date .. effective_end_date, inclusive
    * current row    : effective_end_date = '9999-12-31' sentinel AND is_current
    * expiry rule    : old row ends the day BEFORE the new version starts
    * hybrid rule    : product_name is a Type 1 attribute (typo fixes update
                       ALL versions in place, no new version created)

Run:
    python generate_sample_data.py
    python scd_pipeline.py
"""

import logging
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "data" / "instacart_scd.duckdb"

SENTINEL = "9999-12-31"  # "no end date yet" — never NULL, so BETWEEN just works

SNAPSHOTS = [
    ("2023-01-01", RAW_DIR / "products_snapshot_2023-01-01.csv"),
    ("2023-02-01", RAW_DIR / "products_snapshot_2023-02-01.csv"),
    ("2023-03-01", RAW_DIR / "products_snapshot_2023-03-01.csv"),
]

# Attributes whose change creates a NEW VERSION (Type 2). product_name is
# deliberately excluded — it's a Type 1 attribute in our hybrid design.
TRACKED_ATTRS = ["aisle", "department", "unit_price"]


# --------------------------------------------------------------------------- #
# SCD Type 1 — overwrite (history lost)
# --------------------------------------------------------------------------- #

def scd_type1_load(con: duckdb.DuckDBPyConnection, snapshot_csv: Path) -> None:
    """Upsert the snapshot over the dimension in place.

    After 3 loads the table simply equals the latest snapshot: perfect for
    attributes where history is noise (typos), catastrophic for attributes
    where history is the point (prices, categories).
    """
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS dim_product_type1 (
            product_id INTEGER PRIMARY KEY,
            product_name VARCHAR, aisle VARCHAR,
            department VARCHAR, unit_price DOUBLE
        )
    """)
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE staging AS
        SELECT * FROM read_csv_auto('{snapshot_csv.as_posix()}')
    """)
    # Update existing rows whose content changed...
    con.execute("""
        UPDATE dim_product_type1 t
        SET product_name = s.product_name, aisle = s.aisle,
            department = s.department, unit_price = s.unit_price
        FROM staging s
        WHERE t.product_id = s.product_id
    """)
    # ...and insert rows that are brand new.
    con.execute("""
        INSERT INTO dim_product_type1
        SELECT s.* FROM staging s
        LEFT JOIN dim_product_type1 t ON s.product_id = t.product_id
        WHERE t.product_id IS NULL
    """)


# --------------------------------------------------------------------------- #
# SCD Type 2 — add new row per version (the industry standard)
# --------------------------------------------------------------------------- #

def create_type2_table(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS dim_product_type2 (
            product_key           INTEGER,   -- surrogate: unique per VERSION
            product_id            INTEGER,   -- business key: stable per product
            product_name          VARCHAR,   -- Type 1 attribute (hybrid design)
            aisle                 VARCHAR,   -- Type 2 tracked
            department            VARCHAR,   -- Type 2 tracked
            unit_price            DOUBLE,    -- Type 2 tracked
            effective_start_date  DATE,
            effective_end_date    DATE,      -- '{SENTINEL}' = still current
            is_current            BOOLEAN
        )
    """)


def scd_type2_merge(con: duckdb.DuckDBPyConnection, snapshot_csv: Path,
                    load_date: str) -> None:
    """One incremental Type 2 merge: expire changed rows, insert new versions.

    The algorithm, step by step:
      1. Stage the incoming snapshot.
      2. Hybrid Type 1 pass: fix product_name in place on ALL versions.
      3. Find business keys whose TRACKED attributes changed vs. the current
         version (comparing only tracked attrs avoids 'dimension explosion').
      4. Expire those current rows (end date = day before load, is_current=F).
      5. Insert a fresh version row for each changed key.
      6. Insert never-seen-before keys as brand-new current rows.
    """
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE staging AS
        SELECT * FROM read_csv_auto('{snapshot_csv.as_posix()}')
    """)

    # --- step 2: Type 1 attribute maintained in place across every version.
    # A typo fix must NOT create a new version — that would be noise history.
    con.execute("""
        UPDATE dim_product_type2 d
        SET product_name = s.product_name
        FROM staging s
        WHERE d.product_id = s.product_id
          AND d.product_name <> s.product_name
    """)

    # --- step 3: which products changed in a way we track?
    # IS DISTINCT FROM instead of <> so NULLs compare sanely
    # (NULL <> 'x' yields NULL, which would silently skip the row).
    con.execute("""
        CREATE OR REPLACE TEMP TABLE changed AS
        SELECT s.*
        FROM staging s
        JOIN dim_product_type2 d
          ON s.product_id = d.product_id AND d.is_current
        WHERE s.aisle      IS DISTINCT FROM d.aisle
           OR s.department IS DISTINCT FROM d.department
           OR s.unit_price IS DISTINCT FROM d.unit_price
    """)

    # --- step 4: expire the outgoing versions.
    con.execute(f"""
        UPDATE dim_product_type2 d
        SET effective_end_date = DATE '{load_date}' - INTERVAL 1 DAY,
            is_current = FALSE
        FROM changed c
        WHERE d.product_id = c.product_id AND d.is_current
    """)

    # --- step 5: insert the new versions (fresh surrogate keys).
    con.execute(f"""
        INSERT INTO dim_product_type2
        SELECT
            (SELECT COALESCE(MAX(product_key), 0) FROM dim_product_type2)
              + ROW_NUMBER() OVER (ORDER BY c.product_id)   AS product_key,
            c.product_id, c.product_name, c.aisle, c.department, c.unit_price,
            DATE '{load_date}', DATE '{SENTINEL}', TRUE
        FROM changed c
    """)

    # --- step 6: brand-new products (no version exists at all).
    con.execute(f"""
        INSERT INTO dim_product_type2
        SELECT
            (SELECT COALESCE(MAX(product_key), 0) FROM dim_product_type2)
              + ROW_NUMBER() OVER (ORDER BY s.product_id)   AS product_key,
            s.product_id, s.product_name, s.aisle, s.department, s.unit_price,
            DATE '{load_date}', DATE '{SENTINEL}', TRUE
        FROM staging s
        LEFT JOIN dim_product_type2 d ON s.product_id = d.product_id
        WHERE d.product_id IS NULL
    """)

    changed = con.execute("SELECT COUNT(*) FROM changed").fetchone()[0]
    total = con.execute("SELECT COUNT(*) FROM dim_product_type2").fetchone()[0]
    current = con.execute(
        "SELECT COUNT(*) FROM dim_product_type2 WHERE is_current").fetchone()[0]
    log.info("type2 merge %s: %3d changed versions | %d rows total, %d current",
             load_date, changed, total, current)


# --------------------------------------------------------------------------- #
# SCD Type 3 — previous-value column (one prior state only)
# --------------------------------------------------------------------------- #

def scd_type3_load(con: duckdb.DuckDBPyConnection, snapshot_csv: Path) -> None:
    """Track only current + previous department in two columns.

    Cheap and simple, but a second re-categorisation OVERWRITES the previous
    value — you can only ever answer "what was it right before this?".
    """
    con.execute("""
        CREATE TABLE IF NOT EXISTS dim_product_type3 (
            product_id INTEGER PRIMARY KEY,
            product_name VARCHAR,
            current_department VARCHAR,
            previous_department VARCHAR
        )
    """)
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE staging AS
        SELECT * FROM read_csv_auto('{snapshot_csv.as_posix()}')
    """)
    # Shift current -> previous only when the department actually changed.
    con.execute("""
        UPDATE dim_product_type3 t
        SET previous_department = t.current_department,
            current_department  = s.department,
            product_name        = s.product_name
        FROM staging s
        WHERE t.product_id = s.product_id
          AND t.current_department IS DISTINCT FROM s.department
    """)
    con.execute("""
        INSERT INTO dim_product_type3
        SELECT s.product_id, s.product_name, s.department, NULL
        FROM staging s
        LEFT JOIN dim_product_type3 t ON s.product_id = t.product_id
        WHERE t.product_id IS NULL
    """)


# --------------------------------------------------------------------------- #
# Fact table with point-in-time-correct dimension join
# --------------------------------------------------------------------------- #

def build_fact_orders(con: duckdb.DuckDBPyConnection) -> None:
    """Join each order to the dimension VERSION valid on the order date.

    THE most important line in this project is the join condition:

        ON  o.product_id = d.product_id
        AND o.order_date BETWEEN d.effective_start_date AND d.effective_end_date

    Joining on business key alone (or on is_current) stamps today's
    attributes onto historical facts — the #1 SCD bug.
    """
    con.execute("""
        CREATE OR REPLACE TABLE fact_orders AS
        SELECT
            o.order_id,
            o.order_date,
            o.quantity,
            d.product_key,                     -- version-specific surrogate key
            o.quantity * d.unit_price AS line_revenue   -- price AT ORDER TIME
        FROM read_csv_auto('{path}') o
        JOIN dim_product_type2 d
          ON  o.product_id = d.product_id
          AND o.order_date BETWEEN d.effective_start_date AND d.effective_end_date
    """.replace("{path}", (RAW_DIR / "orders.csv").as_posix()))

    facts = con.execute("SELECT COUNT(*) FROM fact_orders").fetchone()[0]
    raw = con.execute(f"""
        SELECT COUNT(*) FROM read_csv_auto('{(RAW_DIR / "orders.csv").as_posix()}')
    """).fetchone()[0]
    # Quality gate: the point-in-time join must be 1:1 — every order matches
    # exactly one version. Fewer rows = a gap in the date ranges; more rows =
    # overlapping versions. Both mean the SCD logic is broken.
    assert facts == raw, f"point-in-time join produced {facts} rows from {raw} orders"
    log.info("fact_orders built: %s rows, all matched exactly one dimension version",
             f"{facts:,}")


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()  # rebuild from scratch each run (full demo)

    con = duckdb.connect(str(DB_PATH))
    try:
        create_type2_table(con)
        for load_date, csv in SNAPSHOTS:
            log.info("=== loading snapshot %s ===", load_date)
            scd_type1_load(con, csv)
            scd_type2_merge(con, csv, load_date)
            scd_type3_load(con, csv)
        build_fact_orders(con)
        log.info("done — explore with: python demo_queries.py")
    finally:
        con.close()


if __name__ == "__main__":
    main()
