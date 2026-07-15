"""
Run every query in analytical_queries.sql against the built star schema and
print the results as formatted tables.

Queries are separated by `-- name: <query_name>` marker comments so each one
can be labelled in the output.
"""

import re
from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "olist.duckdb"
SQL_PATH = BASE_DIR / "analytical_queries.sql"


def parse_queries(sql_text: str) -> list[tuple[str, str]]:
    """Split the .sql file into (name, query) pairs using -- name: markers."""
    pattern = re.compile(r"--\s*name:\s*(\w+)\n(.*?);", re.DOTALL)
    return [(m.group(1), m.group(2).strip()) for m in pattern.finditer(sql_text)]


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit("Database not found — run build_star_schema.py first.")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        for name, query in parse_queries(SQL_PATH.read_text()):
            print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
            print(con.execute(query).fetchdf().to_string(index=False))
    finally:
        con.close()


if __name__ == "__main__":
    main()
