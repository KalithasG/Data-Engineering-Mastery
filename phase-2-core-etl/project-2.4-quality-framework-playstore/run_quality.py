"""
Apply the data-quality framework to the Play Store dataset.

Defines the domain checks, runs them, quarantines failing rows, writes an HTML
+ CSV report, and emits cleaned Parquet. Exits non-zero if an ERROR-severity
check fails — so this can gate a CI pipeline.

Run:
    python generate_sample_data.py
    python run_quality.py                                   # clean batch
    python run_quality.py --batch playstore_bad_batch.csv   # trips volume check
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from dq_framework import (DataQualityCheck, DataQualityError,
                          DataQualityRunner, Severity)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("run_quality")

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"
OUT_DIR = BASE_DIR / "data" / "reports"
CLEAN_DIR = BASE_DIR / "data" / "clean"

ALLOWED_CATEGORIES = {"GAME", "TOOLS", "BUSINESS", "LIFESTYLE", "FINANCE",
                      "HEALTH_AND_FITNESS", "PHOTOGRAPHY", "SOCIAL", "PRODUCTIVITY"}

# Rolling baseline row count (what a "normal" batch looks like). A real pipeline
# would read this from history; hardcoded here for the demo.
EXPECTED_ROW_BASELINE = 2_000
VOLUME_TOLERANCE = 0.20        # allow +/-20% before flagging


def build_runner(expected_baseline: int) -> DataQualityRunner:
    """Register 12 expectations spanning all six quality categories."""
    runner = DataQualityRunner()
    (runner
     # --- SCHEMA -----------------------------------------------------------
     .add_check(DataQualityCheck(
         "schema_has_app_name", "app_name",
         lambda df: pd.Series("app_name" in df.columns, index=df.index),
         Severity.ERROR, "app_name column must exist"))
     .add_check(DataQualityCheck(
         "rating_is_numeric", "rating",
         lambda df: pd.to_numeric(df["rating"], errors="coerce").notna(),
         Severity.QUARANTINE, "rating must parse as a number"))
     # --- COMPLETENESS -----------------------------------------------------
     .add_check(DataQualityCheck(
         "app_name_not_null", "app_name",
         lambda df: df["app_name"].notna(),
         Severity.QUARANTINE, "every app must have a name"))
     .add_check(DataQualityCheck(
         "category_not_null", "category",
         lambda df: df["category"].notna(),
         Severity.WARN, "category should be present"))
     # --- VALIDITY ---------------------------------------------------------
     .add_check(DataQualityCheck(
         "rating_in_range", "rating",
         lambda df: pd.to_numeric(df["rating"], errors="coerce").between(1.0, 5.0),
         Severity.ERROR, "rating must be within 1.0-5.0 (catches the 19.0 bug)"))
     .add_check(DataQualityCheck(
         "installs_non_negative", "installs",
         lambda df: pd.to_numeric(df["installs"], errors="coerce").fillna(-1) >= 0,
         Severity.QUARANTINE, "installs cannot be negative"))
     .add_check(DataQualityCheck(
         "price_non_negative", "price",
         lambda df: pd.to_numeric(df["price"], errors="coerce").fillna(-1) >= 0,
         Severity.WARN, "price cannot be negative"))
     # --- VALIDITY / accepted values ---------------------------------------
     .add_check(DataQualityCheck(
         "category_in_allowed_set", "category",
         lambda df: df["category"].isin(ALLOWED_CATEGORIES),
         Severity.QUARANTINE, "category must be one of the known set"))
     .add_check(DataQualityCheck(
         "content_rating_valid", "content_rating",
         lambda df: df["content_rating"].isin(
             {"Everyone", "Teen", "Mature 17+", "Everyone 10+"}),
         Severity.WARN, "content_rating must be a known label"))
     # --- UNIQUENESS -------------------------------------------------------
     .add_check(DataQualityCheck(
         "app_id_unique", "app_id",
         lambda df: ~df.duplicated(subset=["app_id"], keep="first"),
         Severity.QUARANTINE, "app_id must be unique"))
     # --- REFERENTIAL (proxy: reviews require a rating) --------------------
     .add_check(DataQualityCheck(
         "reviews_imply_rating", "rating",
         lambda df: ~((pd.to_numeric(df["reviews"], errors="coerce").fillna(0) > 0)
                      & df["rating"].isna()),
         Severity.WARN, "an app with reviews should have a rating"))
     # --- DISTRIBUTIONAL / VOLUME -----------------------------------------
     .add_check(DataQualityCheck(
         "row_count_within_baseline", "app_id",
         lambda df: pd.Series(
             abs(len(df) - expected_baseline) <= VOLUME_TOLERANCE * expected_baseline,
             index=df.index),
         Severity.ERROR,
         f"row count must be within +/-{VOLUME_TOLERANCE:.0%} of {expected_baseline}"))
     )
    return runner


def main() -> int:
    parser = argparse.ArgumentParser(description="Play Store data quality gate")
    parser.add_argument("--batch", default="playstore_clean_batch.csv")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(RAW_DIR / args.batch)
    log.info("loaded %s: %d rows", args.batch, len(df))

    runner = build_runner(EXPECTED_ROW_BASELINE)

    # Always generate the report first (raise_on_error=False) so the artifact
    # exists even when the pipeline is about to hard-fail — you want the report
    # precisely when something broke.
    results, quarantine_mask = runner.run(df, raise_on_error=False)

    report_html = OUT_DIR / f"quality_report_{Path(args.batch).stem}.html"
    report_csv = OUT_DIR / f"quality_report_{Path(args.batch).stem}.csv"
    runner.to_html(report_html, title=f"Play Store Quality — {args.batch}")
    runner.results_dataframe().to_csv(report_csv, index=False)
    log.info("report written: %s and %s", report_html.name, report_csv.name)

    # Quarantine: split rejects from good rows.
    rejects = df[quarantine_mask]
    good = df[~quarantine_mask]
    if not rejects.empty:
        rejects.to_csv(CLEAN_DIR / f"rejects_{Path(args.batch).stem}.csv", index=False)
    good.to_parquet(CLEAN_DIR / f"clean_{Path(args.batch).stem}.parquet", index=False)
    log.info("quarantined %d rows; wrote %d clean rows to Parquet",
             len(rejects), len(good))

    # Print the results table.
    print("\n" + runner.results_dataframe()
          .drop(columns=["failed_sample"]).to_string(index=False))

    # Hard-fail gate: re-run with raising to enforce ERROR severity as an exit code.
    try:
        runner.run(df, raise_on_error=True)
    except DataQualityError as exc:
        log.error("PIPELINE BLOCKED: %s", exc)
        return 1
    log.info("all ERROR-severity checks passed — pipeline may proceed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
