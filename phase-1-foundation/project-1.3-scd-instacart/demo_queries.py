"""
Demonstration queries for the SCD pipeline — the "prove it works" script.

Shows the four things every SCD implementation must be able to answer:
    1. Current state              (WHERE is_current)
    2. Point-in-time lookup       (WHERE date BETWEEN start AND end)
    3. Full version history       (all rows for one business key)
    4. Current vs. at-time-of-record  (the reason SCD Type 2 exists)
"""

from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "instacart_scd.duckdb"


def banner(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit("Database not found — run scd_pipeline.py first.")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        # Pick a product that actually changed, so the demos are meaningful:
        # a business key with more than one Type-2 version.
        changed_pid = con.execute("""
            SELECT product_id
            FROM dim_product_type2
            GROUP BY product_id
            HAVING COUNT(*) > 1
            ORDER BY product_id
            LIMIT 1
        """).fetchone()[0]
        print(f"Using product_id={changed_pid} (it has multiple versions) for the demos.")

        # 1. CURRENT STATE ---------------------------------------------------
        banner("1. Current state — the latest version of every product (is_current)")
        print(con.execute("""
            SELECT product_id, product_name, department, unit_price,
                   effective_start_date, effective_end_date
            FROM dim_product_type2
            WHERE is_current AND product_id <= 5
            ORDER BY product_id
        """).fetchdf().to_string(index=False))

        # 2. POINT-IN-TIME LOOKUP -------------------------------------------
        banner("2. Point-in-time — what did this product look like on 2023-01-15?")
        print(con.execute(f"""
            SELECT product_id, department, unit_price,
                   effective_start_date, effective_end_date
            FROM dim_product_type2
            WHERE product_id = {changed_pid}
              AND DATE '2023-01-15' BETWEEN effective_start_date AND effective_end_date
        """).fetchdf().to_string(index=False))

        # 3. FULL VERSION HISTORY -------------------------------------------
        banner(f"3. Full history — every version of product {changed_pid}")
        print(con.execute(f"""
            SELECT product_key, department, unit_price,
                   effective_start_date, effective_end_date, is_current
            FROM dim_product_type2
            WHERE product_id = {changed_pid}
            ORDER BY effective_start_date
        """).fetchdf().to_string(index=False))

        # 4. CURRENT vs. AT-TIME-OF-RECORD ----------------------------------
        # THE payoff query: for orders of a changed product, compare the price
        # we CHARGED (point-in-time correct) against the CURRENT price. If the
        # two columns differ, a naive "join to current version" report would
        # have silently mis-stated historical revenue.
        #
        # Pick a product whose PRICE (not just department) changed, so the
        # difference column is actually non-zero and the point lands.
        priced_pid = con.execute("""
            SELECT product_id
            FROM dim_product_type2
            GROUP BY product_id
            HAVING COUNT(DISTINCT unit_price) > 1
            ORDER BY product_id
            LIMIT 1
        """).fetchone()[0]
        banner(f"4. Current vs. at-time-of-record price for orders of product {priced_pid}")
        print(con.execute(f"""
            WITH current_price AS (
                SELECT unit_price
                FROM dim_product_type2
                WHERE product_id = {priced_pid} AND is_current
            )
            SELECT
                f.order_id,
                f.order_date,
                d.unit_price                       AS price_at_order_time,
                cp.unit_price                      AS current_price,
                ROUND(cp.unit_price - d.unit_price, 2) AS difference_if_naive_join
            FROM fact_orders f
            JOIN dim_product_type2 d ON f.product_key = d.product_key
            CROSS JOIN current_price cp
            WHERE d.product_id = {priced_pid}
            ORDER BY f.order_date
            LIMIT 10
        """).fetchdf().to_string(index=False))

        # Bonus: Type 3 shows only current + previous department.
        banner("Bonus — SCD Type 3 (current + previous department only)")
        print(con.execute("""
            SELECT product_id, current_department, previous_department
            FROM dim_product_type3
            WHERE previous_department IS NOT NULL
            ORDER BY product_id
            LIMIT 5
        """).fetchdf().to_string(index=False))
    finally:
        con.close()


if __name__ == "__main__":
    main()
