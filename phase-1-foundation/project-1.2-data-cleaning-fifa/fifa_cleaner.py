"""
Guided Project 1.2 — FIFACleaner: a chainable, auditable, idempotent
data-cleaning pipeline.

Design rules (from Concept Primer 1.2):
    * Declarative & chainable — every method returns self, so a pipeline reads
      as a sentence:  cleaner.parse_currency().parse_ratings().dedupe()...
    * Idempotent      — running any step twice equals running it once.
    * Audited         — every step logs what it changed into a quality report;
      nothing is silently dropped.
    * Each step states WHICH of the 6 data-quality dimensions it addresses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# Formats tried in order when parsing joined_date. Explicit list — never let
# a "smart" parser guess silently.
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d %b %Y"]

CURRENCY_RE = re.compile(r"^€?\s*([\d.]+)\s*([MK]?)$", re.IGNORECASE)
RATING_RE = re.compile(r"^(\d+)\s*([+-]\s*\d+)?$")


@dataclass
class CleaningStep:
    """One audit-log entry: what a step did and how many rows it touched."""
    step: str
    quality_dimension: str
    rows_affected: int
    detail: str = ""
    failed_samples: list = field(default_factory=list)


class FIFACleaner:
    """Chainable cleaner for the FIFA player dataset.

    Usage:
        cleaner = (FIFACleaner(raw_df)
                   .normalize_text("nationality")
                   .parse_currency("value_eur")
                   .parse_currency("wage_eur")
                   .parse_rating("overall")
                   .parse_rating("potential")
                   .parse_dates("joined_date")
                   .dedupe(key="player_id")
                   .handle_nulls()
                   .validate())
        cleaner.to_parquet("data/clean/fifa_players.parquet")
        print(cleaner.quality_report())
    """

    def __init__(self, df: pd.DataFrame):
        # Copy so the caller's raw dataframe is never mutated — raw data is
        # sacred (the same principle as an immutable Bronze layer).
        self.df = df.copy()
        self.audit: list[CleaningStep] = []
        self._input_rows = len(df)

    # ------------------------------------------------------------------ #
    # Parsers (static so they're unit-testable in isolation)
    # ------------------------------------------------------------------ #

    @staticmethod
    def parse_currency_value(raw) -> float | None:
        """'€105.5M' -> 105_500_000.0 ; '€500K' -> 500_000.0 ; '€0' -> 0.0

        Returns None for unparseable input instead of raising — the caller
        decides what to do with failures (log them, never hide them).
        """
        if raw is None or (isinstance(raw, float) and np.isnan(raw)):
            return None
        if isinstance(raw, (int, float)):
            return float(raw)  # already numeric: makes the step idempotent
        match = CURRENCY_RE.match(str(raw).strip())
        if not match:
            return None
        number = float(match.group(1))
        suffix = match.group(2).upper()
        multiplier = {"M": 1_000_000, "K": 1_000, "": 1}[suffix]
        return number * multiplier

    @staticmethod
    def parse_rating_value(raw) -> int | None:
        """'90+2' -> 92 ; '78-1' -> 77 ; '85' -> 85 ; garbage -> None."""
        if raw is None or (isinstance(raw, float) and np.isnan(raw)):
            return None
        if isinstance(raw, (int, np.integer)):
            return int(raw)  # already parsed: idempotent re-run is a no-op
        match = RATING_RE.match(str(raw).strip())
        if not match:
            return None
        base = int(match.group(1))
        modifier = int(match.group(2).replace(" ", "")) if match.group(2) else 0
        return base + modifier

    # ------------------------------------------------------------------ #
    # Chainable pipeline steps — each returns self
    # ------------------------------------------------------------------ #

    def normalize_text(self, column: str) -> "FIFACleaner":
        """Strip whitespace and title-case a text column.

        Quality dimension: CONSISTENCY — '  BRAZIL ' and 'Brazil' must be the
        same value or every GROUP BY on this column double-counts.
        """
        before = self.df[column].copy()
        self.df[column] = self.df[column].str.strip().str.title()
        changed = int((before != self.df[column]).sum())
        self.audit.append(CleaningStep(
            step=f"normalize_text({column})",
            quality_dimension="consistency",
            rows_affected=changed,
            detail="strip + title-case",
        ))
        return self

    def parse_currency(self, column: str) -> "FIFACleaner":
        """Convert currency strings to floats using one shared parser.

        Quality dimension: VALIDITY — the column must be numeric to be usable.
        One parser for every currency column: never fix values by hand.
        """
        parsed = self.df[column].map(self.parse_currency_value)
        # Failures = raw was non-null but the parser returned None.
        failed_mask = self.df[column].notna() & parsed.isna()
        self.audit.append(CleaningStep(
            step=f"parse_currency({column})",
            quality_dimension="validity",
            rows_affected=int(self.df[column].notna().sum()),
            detail=f"{int(failed_mask.sum())} unparseable values",
            failed_samples=self.df.loc[failed_mask, column].head(5).tolist(),
        ))
        self.df[column] = parsed
        return self

    def parse_rating(self, column: str) -> "FIFACleaner":
        """Resolve composite ratings like '90+2' into a single integer.

        Quality dimension: VALIDITY.
        """
        parsed = self.df[column].map(self.parse_rating_value)
        failed_mask = self.df[column].notna() & parsed.isna()
        self.audit.append(CleaningStep(
            step=f"parse_rating({column})",
            quality_dimension="validity",
            rows_affected=int(self.df[column].notna().sum()),
            detail=f"{int(failed_mask.sum())} unparseable values",
            failed_samples=self.df.loc[failed_mask, column].head(5).tolist(),
        ))
        self.df[column] = parsed.astype("Int64")
        return self

    def parse_dates(self, column: str) -> "FIFACleaner":
        """Parse mixed-format dates with an explicit format list.

        Quality dimension: VALIDITY + CONSISTENCY.
        Tries each known format on the not-yet-parsed remainder and logs the
        hit count per format — so when a NEW format shows up upstream, the
        failure count tells you immediately.
        """
        if pd.api.types.is_datetime64_any_dtype(self.df[column]):
            # Already datetimes (e.g. second run) — idempotent no-op.
            self.audit.append(CleaningStep(
                step=f"parse_dates({column})", quality_dimension="validity",
                rows_affected=0, detail="already datetime — skipped"))
            return self

        result = pd.Series(pd.NaT, index=self.df.index, dtype="datetime64[ns]")
        hits_per_format = {}
        for fmt in DATE_FORMATS:
            unparsed = result.isna()
            attempt = pd.to_datetime(self.df.loc[unparsed, column],
                                     format=fmt, errors="coerce")
            hits_per_format[fmt] = int(attempt.notna().sum())
            result.loc[unparsed] = attempt

        failed_mask = self.df[column].notna() & result.isna()
        self.audit.append(CleaningStep(
            step=f"parse_dates({column})",
            quality_dimension="validity",
            rows_affected=int(result.notna().sum()),
            detail=f"hits per format: {hits_per_format}; "
                   f"{int(failed_mask.sum())} failed all formats",
            failed_samples=self.df.loc[failed_mask, column].head(5).tolist(),
        ))
        self.df[column] = result
        return self

    def dedupe(self, key: str) -> "FIFACleaner":
        """Drop duplicate rows sharing the same business key.

        Quality dimension: UNIQUENESS.
        keep='first' is deterministic, which keeps the step idempotent — a
        second run finds zero duplicates and removes nothing.
        """
        before = len(self.df)
        self.df = self.df.drop_duplicates(subset=[key], keep="first")
        removed = before - len(self.df)
        self.audit.append(CleaningStep(
            step=f"dedupe({key})",
            quality_dimension="uniqueness",
            rows_affected=removed,
            detail=f"{removed} duplicate rows removed",
        ))
        return self

    def handle_nulls(self) -> "FIFACleaner":
        """Column-by-column null strategy — a business decision per column.

        Quality dimension: COMPLETENESS.
          * club     : NULL means FREE AGENT — a valid state, NOT an error.
                       Filled with the explicit label 'Free Agent'
                       ("when NOT to clean": don't destroy signal).
          * value_eur: source-missing (MAR — missingness likely relates to
                       observable attributes like obscure players). Imputed
                       with the MEDIAN of the player's position group, and
                       flagged in value_eur_imputed so consumers can exclude
                       imputed rows.
        """
        club_nulls = int(self.df["club"].isna().sum())
        self.df["club"] = self.df["club"].fillna("Free Agent")

        value_nulls_mask = self.df["value_eur"].isna()
        # Flag BEFORE filling — and OR into any existing flag rather than
        # overwrite it. On a re-run the values are already filled (mask all
        # False), so overwriting would erase the flags set on the first run
        # and silently break idempotency.
        if "value_eur_imputed" in self.df.columns:
            self.df["value_eur_imputed"] = self.df["value_eur_imputed"] | value_nulls_mask
        else:
            self.df["value_eur_imputed"] = value_nulls_mask
        position_median = self.df.groupby("position")["value_eur"].transform("median")
        # Fall back to the global median for positions where EVERY value is
        # null (group median would itself be NaN and leave the null in place).
        self.df["value_eur"] = (self.df["value_eur"]
                                .fillna(position_median)
                                .fillna(self.df["value_eur"].median()))

        self.audit.append(CleaningStep(
            step="handle_nulls",
            quality_dimension="completeness",
            rows_affected=club_nulls + int(value_nulls_mask.sum()),
            detail=(f"club: {club_nulls} nulls -> 'Free Agent' (valid state); "
                    f"value_eur: {int(value_nulls_mask.sum())} nulls -> "
                    f"position-group median, flagged in value_eur_imputed"),
        ))
        return self

    def validate(self) -> "FIFACleaner":
        """Hard quality gates — raise if the cleaned data violates invariants.

        Quality dimension: VALIDITY + UNIQUENESS + ACCURACY (range checks are
        the closest cheap proxy for accuracy).
        Assertions, not warnings: bad data must not flow downstream.
        """
        assert self.df["player_id"].is_unique, "player_id must be unique after dedupe"
        assert self.df["overall"].between(1, 99).all(), "overall out of 1-99 range"
        assert self.df["potential"].between(1, 99).all(), "potential out of 1-99 range"
        assert self.df["value_eur"].notna().all(), "value_eur still has nulls after imputation"
        assert (self.df["value_eur"] >= 0).all(), "negative market value"
        assert self.df["age"].between(15, 50).all(), "age outside plausible range"
        assert pd.api.types.is_datetime64_any_dtype(self.df["joined_date"]), \
            "joined_date not parsed to datetime"
        self.audit.append(CleaningStep(
            step="validate", quality_dimension="validity/uniqueness/accuracy",
            rows_affected=len(self.df), detail="all 6 assertions passed"))
        return self

    # ------------------------------------------------------------------ #
    # Outputs
    # ------------------------------------------------------------------ #

    def quality_report(self) -> pd.DataFrame:
        """The audit trail as a dataframe — an artifact, not print statements."""
        return pd.DataFrame([{
            "step": s.step,
            "quality_dimension": s.quality_dimension,
            "rows_affected": s.rows_affected,
            "detail": s.detail,
            "failed_samples": s.failed_samples,
        } for s in self.audit])

    def to_parquet(self, path: str | Path) -> Path:
        """Write the cleaned data to Parquet (typed, compressed, columnar)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_parquet(path, index=False)
        return path
