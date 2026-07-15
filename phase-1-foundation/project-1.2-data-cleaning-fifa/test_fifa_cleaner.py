"""
Unit tests for FIFACleaner.

Run with:  pytest test_fifa_cleaner.py -v

The most important test here is idempotency: running the full pipeline on
already-clean data must change NOTHING. That property is what makes a
pipeline safe to retry — the theme that carries through the whole playbook.
"""

import pandas as pd
import pytest

from fifa_cleaner import FIFACleaner


# --------------------------------------------------------------------- #
# Parser unit tests — pure functions, exhaustively testable
# --------------------------------------------------------------------- #

@pytest.mark.parametrize("raw,expected", [
    ("€105.5M", 105_500_000.0),
    ("€500K", 500_000.0),
    ("€0", 0.0),
    ("€1.2M", 1_200_000.0),
    ("2.5M", 2_500_000.0),      # missing € symbol still parses
    (750_000.0, 750_000.0),     # already numeric passes through (idempotency)
    ("garbage", None),          # unparseable -> None, never an exception
    (None, None),
])
def test_parse_currency_value(raw, expected):
    assert FIFACleaner.parse_currency_value(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("90+2", 92),
    ("78-1", 77),
    ("85", 85),
    (85, 85),                   # already an int passes through (idempotency)
    ("not a rating", None),
    (None, None),
])
def test_parse_rating_value(raw, expected):
    assert FIFACleaner.parse_rating_value(raw) == expected


# --------------------------------------------------------------------- #
# Pipeline behaviour tests on a small fixture
# --------------------------------------------------------------------- #

@pytest.fixture
def dirty_df() -> pd.DataFrame:
    df = pd.DataFrame({
        "player_id": [1, 2, 3, 2],           # id 2 duplicated
        "short_name": ["A", "B", "C", "B"],
        "age": [25, 30, 21, 30],
        "nationality": ["  BRAZIL ", "France", "spain", "France"],
        "club": ["FC X", None, "FC Y", None],  # None = free agent
        "position": ["ST", "GK", "CM", "GK"],
        "overall": ["90+2", "78-1", "85", "78-1"],
        "potential": ["93", "80", "88+1", "80"],
        "value_eur": ["€105.5M", "€500K", None, "€500K"],
        "wage_eur": ["€230K", "€90K", "€45K", "€90K"],
        "joined_date": ["2019-07-01", "7/1/2019", "1 Jul 2019", "7/1/2019"],
        "height_cm": [180, 191, 175, 191],
        "weight_kg": [75, 85, 68, 85],
    })
    return df


def run_full_pipeline(df: pd.DataFrame) -> FIFACleaner:
    return (FIFACleaner(df)
            .normalize_text("nationality")
            .parse_currency("value_eur")
            .parse_currency("wage_eur")
            .parse_rating("overall")
            .parse_rating("potential")
            .parse_dates("joined_date")
            .dedupe(key="player_id")
            .handle_nulls()
            .validate())


def test_currency_column_parsed(dirty_df):
    cleaned = run_full_pipeline(dirty_df).df
    assert cleaned.loc[cleaned["player_id"] == 1, "value_eur"].iloc[0] == 105_500_000.0
    assert cleaned.loc[cleaned["player_id"] == 2, "value_eur"].iloc[0] == 500_000.0


def test_composite_ratings_resolved(dirty_df):
    cleaned = run_full_pipeline(dirty_df).df
    assert cleaned.loc[cleaned["player_id"] == 1, "overall"].iloc[0] == 92
    assert cleaned.loc[cleaned["player_id"] == 2, "overall"].iloc[0] == 77


def test_mixed_date_formats_all_parse(dirty_df):
    cleaned = run_full_pipeline(dirty_df).df
    # Three different textual formats must all resolve to the SAME date.
    assert (cleaned["joined_date"] == pd.Timestamp("2019-07-01")).all()


def test_dedupe_removes_duplicate_business_key(dirty_df):
    cleaned = run_full_pipeline(dirty_df).df
    assert len(cleaned) == 3
    assert cleaned["player_id"].is_unique


def test_free_agent_null_is_labelled_not_dropped(dirty_df):
    cleaned = run_full_pipeline(dirty_df).df
    assert (cleaned.loc[cleaned["player_id"] == 2, "club"] == "Free Agent").all()


def test_imputed_values_are_flagged(dirty_df):
    cleaned = run_full_pipeline(dirty_df).df
    flagged = cleaned.loc[cleaned["player_id"] == 3]
    assert flagged["value_eur_imputed"].iloc[0]          # was null, so flagged
    assert flagged["value_eur"].notna().iloc[0]          # and filled
    assert not cleaned.loc[cleaned["player_id"] == 1, "value_eur_imputed"].iloc[0]


def test_original_dataframe_never_mutated(dirty_df):
    snapshot = dirty_df.copy()
    run_full_pipeline(dirty_df)
    pd.testing.assert_frame_equal(dirty_df, snapshot)


def test_quality_report_records_every_step(dirty_df):
    cleaner = run_full_pipeline(dirty_df)
    report = cleaner.quality_report()
    assert len(report) == 9          # one audit row per pipeline step
    assert (report["rows_affected"] >= 0).all()


# --------------------------------------------------------------------- #
# THE test: idempotency
# --------------------------------------------------------------------- #

def test_pipeline_is_idempotent(dirty_df):
    """Cleaning already-clean data must be a no-op.

    Run the pipeline once, then feed its OUTPUT back through the SAME
    pipeline. If any values differ, some step is not idempotent and the
    pipeline is unsafe to retry.
    """
    once = run_full_pipeline(dirty_df).df.reset_index(drop=True)
    twice = run_full_pipeline(once).df.reset_index(drop=True)
    pd.testing.assert_frame_equal(once, twice)
