"""
Tests for the data-quality framework.

Verifies the framework mechanics (checks fire, severities behave) independently
of the Play Store dataset.

Run:  pytest test_dq_framework.py -v
"""

import pandas as pd
import pytest

from dq_framework import (DataQualityCheck, DataQualityError,
                          DataQualityRunner, Severity)


@pytest.fixture
def df():
    return pd.DataFrame({
        "app_id": [1, 2, 3, 3],          # id 3 duplicated
        "name": ["A", "B", None, "D"],   # one null
        "rating": [4.5, 19.0, 3.0, 2.0], # one out of range (19.0)
    })


def test_check_counts_failures(df):
    runner = DataQualityRunner().add_check(DataQualityCheck(
        "rating_in_range", "rating",
        lambda d: d["rating"].between(1.0, 5.0), Severity.WARN))
    results, _ = runner.run(df)
    assert results[0].failed_count == 1
    assert not results[0].passed
    assert results[0].pass_rate == 0.75


def test_error_severity_raises(df):
    runner = DataQualityRunner().add_check(DataQualityCheck(
        "rating_in_range", "rating",
        lambda d: d["rating"].between(1.0, 5.0), Severity.ERROR))
    with pytest.raises(DataQualityError):
        runner.run(df, raise_on_error=True)


def test_error_can_be_suppressed_for_reporting(df):
    """raise_on_error=False lets the report render instead of crashing."""
    runner = DataQualityRunner().add_check(DataQualityCheck(
        "rating_in_range", "rating",
        lambda d: d["rating"].between(1.0, 5.0), Severity.ERROR))
    results, _ = runner.run(df, raise_on_error=False)
    assert results[0].failed_count == 1        # no exception raised


def test_quarantine_mask_collects_failing_rows(df):
    runner = (DataQualityRunner()
              .add_check(DataQualityCheck(
                  "name_not_null", "name",
                  lambda d: d["name"].notna(), Severity.QUARANTINE))
              .add_check(DataQualityCheck(
                  "app_id_unique", "app_id",
                  lambda d: ~d.duplicated(subset=["app_id"], keep="first"),
                  Severity.QUARANTINE)))
    _, quarantine_mask = runner.run(df)
    # Row 2 (None name) and row 3 (duplicate id) should be quarantined.
    assert quarantine_mask.tolist() == [False, False, True, True]


def test_passing_check_reports_pass(df):
    runner = DataQualityRunner().add_check(DataQualityCheck(
        "app_id_positive", "app_id",
        lambda d: d["app_id"] > 0, Severity.ERROR))
    results, _ = runner.run(df)
    assert results[0].passed
    assert results[0].failed_count == 0


def test_warn_does_not_raise(df):
    """A WARN failure logs but must not block the pipeline."""
    runner = DataQualityRunner().add_check(DataQualityCheck(
        "name_not_null", "name",
        lambda d: d["name"].notna(), Severity.WARN))
    results, _ = runner.run(df, raise_on_error=True)   # should NOT raise
    assert results[0].failed_count == 1


def test_add_check_is_chainable(df):
    runner = DataQualityRunner()
    returned = runner.add_check(DataQualityCheck(
        "x", "app_id", lambda d: d["app_id"] > 0, Severity.WARN))
    assert returned is runner                # returns self for fluent chaining
