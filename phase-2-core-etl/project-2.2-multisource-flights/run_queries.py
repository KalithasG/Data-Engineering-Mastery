"""
Run the 5 analytical queries in analytical_queries.sql against the SQLite
warehouse and print each result. Also prints a row-count reconciliation so you
can see the joins didn't drop or fan out rows.
"""

import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "flights.db"
SQL_PATH = BASE_DIR / "analytical_queries.sql"


def parse_queries(sql_text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"--\s*name:\s*(\w+)\n(.*?);", re.DOTALL)
    return [(m.group(1), m.group(2).strip()) for m in pattern.finditer(sql_text)]


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit("Database not found — run flight_etl.py first.")

    engine = create_engine(f"sqlite:///{DB_PATH}")

    # Row-count reconciliation: fact rows should equal source flight rows.
    with engine.connect() as conn:
        fact_rows = conn.execute(text("SELECT COUNT(*) FROM fact_flights")).scalar()
    raw_rows = len(pd.read_csv(BASE_DIR / "data" / "raw" / "flights.csv"))
    print(f"reconciliation: fact_flights={fact_rows:,} vs raw flights={raw_rows:,} "
          f"-> {'OK (1:1, no fan-out)' if fact_rows == raw_rows else 'MISMATCH!'}")

    for name, query in parse_queries(SQL_PATH.read_text()):
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        print(pd.read_sql_query(query, engine).to_string(index=False))


if __name__ == "__main__":
    main()
