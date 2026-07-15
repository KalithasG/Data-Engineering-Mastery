"""
Guided Project 1.1 — Star Schema with Olist E-Commerce.

Profiles the 8 raw CSVs, then builds a dimensional model in DuckDB:

    fact_order_items                 <- GRAIN: one row per item within an order
    ├── dim_customer   (who bought)
    ├── dim_product    (what was bought)
    ├── dim_seller     (who sold it)
    └── dim_date       (when — the highest-leverage dimension)

Run:
    python generate_sample_data.py   # or drop the real Kaggle CSVs in data/raw/
    python build_star_schema.py
"""

import logging
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "data" / "olist.duckdb"

RAW_TABLES = {
    "raw_customers": "olist_customers_dataset.csv",
    "raw_orders": "olist_orders_dataset.csv",
    "raw_order_items": "olist_order_items_dataset.csv",
    "raw_products": "olist_products_dataset.csv",
    "raw_sellers": "olist_sellers_dataset.csv",
    "raw_payments": "olist_order_payments_dataset.csv",
    "raw_reviews": "olist_order_reviews_dataset.csv",
    "raw_geolocation": "olist_geolocation_dataset.csv",
}


def load_raw(con: duckdb.DuckDBPyConnection) -> None:
    """Land each CSV as an untouched raw_* table (our mini Bronze layer)."""
    for table, filename in RAW_TABLES.items():
        path = RAW_DIR / filename
        con.execute(f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT * FROM read_csv_auto('{path.as_posix()}')
        """)
        rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        log.info("loaded %-18s %8s rows", table, f"{rows:,}")


def profile_raw(con: duckdb.DuckDBPyConnection) -> None:
    """Basic profiling: row counts, key uniqueness, null rates on key columns.

    Profiling BEFORE modeling is what tells you the true grain and cardinality
    of each table — guessing these is how fan traps happen.
    """
    log.info("--- profiling ---")

    # Is customer_id unique in raw_customers? (yes: 1 row per order-customer)
    dupes = con.execute("""
        SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM raw_customers
    """).fetchone()[0]
    log.info("raw_customers duplicate customer_ids: %d", dupes)

    # Orders per status — tells us delivered_customer_date nulls are structural.
    for status, cnt in con.execute("""
        SELECT order_status, COUNT(*) FROM raw_orders
        GROUP BY 1 ORDER BY 2 DESC
    """).fetchall():
        log.info("order_status %-12s %6s", status, f"{cnt:,}")

    # Null category products — these become the 'unknown' dimension member.
    null_cat = con.execute("""
        SELECT COUNT(*) FROM raw_products WHERE product_category_name IS NULL
    """).fetchone()[0]
    log.info("products with NULL category: %d", null_cat)

    # Cardinality check before the fact build: items per order distribution.
    log.info("items-per-order distribution: %s", con.execute("""
        SELECT n_items, COUNT(*) FROM (
            SELECT order_id, COUNT(*) AS n_items FROM raw_order_items GROUP BY 1
        ) GROUP BY 1 ORDER BY 1
    """).fetchall())


def build_dim_date(con: duckdb.DuckDBPyConnection) -> None:
    """dim_date: one row per calendar day covering the order date range.

    Always build a date dimension — it is the highest-leverage dimension in
    any warehouse (every 'by month/quarter/weekday' question joins to it).
    """
    con.execute("""
        CREATE OR REPLACE TABLE dim_date AS
        WITH bounds AS (
            SELECT
                MIN(order_purchase_timestamp)::DATE AS start_date,
                MAX(order_purchase_timestamp)::DATE AS end_date
            FROM raw_orders
        ),
        days AS (
            SELECT UNNEST(generate_series(start_date, end_date, INTERVAL 1 DAY))::DATE AS d
            FROM bounds
        )
        SELECT
            -- Smart surrogate key: yyyymmdd integer. Date dims are the one
            -- accepted exception to "surrogate keys must be meaningless".
            CAST(STRFTIME(d, '%Y%m%d') AS INTEGER) AS date_key,
            d                                      AS full_date,
            EXTRACT(year    FROM d)                AS year,
            EXTRACT(quarter FROM d)                AS quarter,
            EXTRACT(month   FROM d)                AS month,
            STRFTIME(d, '%B')                      AS month_name,
            EXTRACT(day     FROM d)                AS day_of_month,
            EXTRACT(dow     FROM d)                AS day_of_week,   -- 0=Sunday
            STRFTIME(d, '%A')                      AS day_name,
            EXTRACT(dow FROM d) IN (0, 6)          AS is_weekend
        FROM days
    """)


def build_dim_customer(con: duckdb.DuckDBPyConnection) -> None:
    """dim_customer: one row per customer_id (order-level customer record)."""
    con.execute("""
        CREATE OR REPLACE TABLE dim_customer AS
        SELECT
            -- Surrogate key: sequence over a deterministic ordering. Never
            -- expose the natural key as the PK — source systems change.
            ROW_NUMBER() OVER (ORDER BY customer_id) AS customer_key,
            customer_id                              AS customer_natural_key,
            customer_unique_id,
            customer_zip_code_prefix,
            customer_city,
            customer_state
        FROM raw_customers
    """)


def build_dim_product(con: duckdb.DuckDBPyConnection) -> None:
    """dim_product with an 'unknown member' row (surrogate key -1).

    The unknown member is how we survive late-arriving dimensions: a fact
    row whose product is missing still joins to *something*, so it is never
    silently dropped by an inner join.
    """
    con.execute("""
        CREATE OR REPLACE TABLE dim_product AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY product_id)          AS product_key,
            product_id                                       AS product_natural_key,
            COALESCE(product_category_name, 'unknown')       AS product_category,
            product_weight_g,
            product_length_cm,
            product_height_cm,
            product_width_cm,
            product_photos_qty
        FROM raw_products

        UNION ALL

        SELECT -1, 'UNKNOWN', 'unknown', NULL, NULL, NULL, NULL, NULL
    """)


def build_dim_seller(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE OR REPLACE TABLE dim_seller AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY seller_id) AS seller_key,
            seller_id                              AS seller_natural_key,
            seller_zip_code_prefix,
            seller_city,
            seller_state
        FROM raw_sellers

        UNION ALL

        SELECT -1, 'UNKNOWN', NULL, NULL, NULL
    """)


def build_fact_order_items(con: duckdb.DuckDBPyConnection) -> None:
    """
    GRAIN (declared before any SQL, per Kimball):
        one row = one item line within one order.
    An order with 3 items produces 3 fact rows. All measures (price,
    freight_value) are additive at this grain.

    Every raw natural key is swapped for the dimension's surrogate key via a
    LEFT JOIN + COALESCE(-1) so unmatched facts hit the unknown member
    instead of vanishing.
    """
    con.execute("""
        CREATE OR REPLACE TABLE fact_order_items AS
        SELECT
            -- Degenerate dimensions: order identifiers kept on the fact row
            -- (they have no descriptive attributes worth a dimension table).
            oi.order_id,
            oi.order_item_id,

            -- Foreign keys to dimensions (surrogate keys, never natural keys)
            COALESCE(dc.customer_key, -1)                              AS customer_key,
            COALESCE(dp.product_key,  -1)                              AS product_key,
            COALESCE(ds.seller_key,   -1)                              AS seller_key,
            CAST(STRFTIME(o.order_purchase_timestamp, '%Y%m%d') AS INTEGER) AS order_date_key,

            -- Contextual attributes at fact grain
            o.order_status,

            -- Additive measures
            oi.price,
            oi.freight_value,
            oi.price + oi.freight_value                                AS total_item_value,

            -- Delivery lag in days: NULL for undelivered orders (structural)
            DATE_DIFF('day',
                      o.order_purchase_timestamp,
                      o.order_delivered_customer_date)                 AS delivery_days
        FROM raw_order_items oi
        JOIN raw_orders o        ON oi.order_id = o.order_id
        LEFT JOIN dim_customer dc ON o.customer_id  = dc.customer_natural_key
        LEFT JOIN dim_product  dp ON oi.product_id  = dp.product_natural_key
        LEFT JOIN dim_seller   ds ON oi.seller_id   = ds.seller_natural_key
    """)


def validate(con: duckdb.DuckDBPyConnection) -> None:
    """Post-build quality gates. Hard-fail (raise) on referential breakage."""
    fact_rows = con.execute("SELECT COUNT(*) FROM fact_order_items").fetchone()[0]
    raw_rows = con.execute("SELECT COUNT(*) FROM raw_order_items").fetchone()[0]
    assert fact_rows == raw_rows, (
        f"Fact row count {fact_rows} != raw items {raw_rows} — a join fanned out or dropped rows"
    )

    orphans = con.execute("""
        SELECT COUNT(*) FROM fact_order_items f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        WHERE p.product_key IS NULL
    """).fetchone()[0]
    assert orphans == 0, f"{orphans} fact rows have no matching dim_product row"

    unknown_hits = con.execute(
        "SELECT COUNT(*) FROM fact_order_items WHERE product_key = -1"
    ).fetchone()[0]
    log.info("validation passed: %s fact rows, %d routed to unknown product member",
             f"{fact_rows:,}", unknown_hits)


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    try:
        load_raw(con)
        profile_raw(con)
        build_dim_date(con)
        build_dim_customer(con)
        build_dim_product(con)
        build_dim_seller(con)
        build_fact_order_items(con)
        validate(con)
        log.info("star schema built at %s", DB_PATH)
    finally:
        con.close()


if __name__ == "__main__":
    main()
