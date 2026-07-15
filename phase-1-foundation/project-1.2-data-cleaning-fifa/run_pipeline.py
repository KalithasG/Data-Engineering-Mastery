"""
Run the full FIFA cleaning pipeline end-to-end:

    raw CSV -> FIFACleaner chain -> clean Parquet + quality report CSV
"""

from pathlib import Path

import pandas as pd

from fifa_cleaner import FIFACleaner

BASE_DIR = Path(__file__).parent
RAW_CSV = BASE_DIR / "data" / "raw" / "fifa_players_raw.csv"
CLEAN_PARQUET = BASE_DIR / "data" / "clean" / "fifa_players_clean.parquet"
REPORT_CSV = BASE_DIR / "data" / "clean" / "quality_report.csv"


def main() -> None:
    raw = pd.read_csv(RAW_CSV)
    print(f"raw input: {len(raw):,} rows, {len(raw.columns)} columns")

    # The whole pipeline reads as one sentence — that is the point of the
    # fluent (method-chaining) interface.
    cleaner = (FIFACleaner(raw)
               .normalize_text("nationality")
               .parse_currency("value_eur")
               .parse_currency("wage_eur")
               .parse_rating("overall")
               .parse_rating("potential")
               .parse_dates("joined_date")
               .dedupe(key="player_id")
               .handle_nulls()
               .validate())

    out = cleaner.to_parquet(CLEAN_PARQUET)
    report = cleaner.quality_report()
    report.to_csv(REPORT_CSV, index=False)

    print(f"\nclean output: {len(cleaner.df):,} rows -> {out}")
    print(f"quality report -> {REPORT_CSV}\n")
    print(report.drop(columns=["failed_samples"]).to_string(index=False))


if __name__ == "__main__":
    main()
