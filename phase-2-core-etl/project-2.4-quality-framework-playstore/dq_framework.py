"""
Guided Project 2.4 — a reusable Data Quality Framework.

Turns ad-hoc quality checks into declarative, reusable EXPECTATIONS with
severity-based responses (Primer 2.4):

    @dataclass DataQualityCheck(name, column, rule: Callable, severity)
    DataQualityRunner.add_check(...).run(df)  ->  DataQualityResult per check

Severity drives the response:
    ERROR       -> HARD FAIL: raise, block the pipeline (PK broken, out of range)
    WARN        -> SOFT FAIL: log + continue (slightly elevated null rate)
    QUARANTINE  -> route failing ROWS to a rejects table, keep the good ones

This module is dataset-agnostic — the Play Store checks live in run_quality.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import pandas as pd


class Severity(str, Enum):
    ERROR = "error"           # hard fail — block the pipeline
    WARN = "warn"             # soft fail — log and continue
    QUARANTINE = "quarantine" # route bad rows aside, keep the rest


@dataclass
class DataQualityCheck:
    """A single declarative expectation.

    rule: a Callable(df) -> boolean Series that is True for rows that PASS.
          Row-level rules let us quarantine exactly the failing rows.
    """
    name: str
    column: str
    rule: Callable[[pd.DataFrame], pd.Series]
    severity: Severity = Severity.WARN
    description: str = ""


@dataclass
class DataQualityResult:
    name: str
    column: str
    severity: Severity
    passed: bool
    failed_count: int
    total_count: int
    failed_sample: list = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total_count == 0:
            return 1.0
        return (self.total_count - self.failed_count) / self.total_count


class DataQualityError(Exception):
    """Raised when an ERROR-severity check fails — hard-fails the pipeline."""


class DataQualityRunner:
    """Collect checks, run them, and produce results + a quarantine mask."""

    def __init__(self):
        self.checks: list[DataQualityCheck] = []
        self.results: list[DataQualityResult] = []

    def add_check(self, check: DataQualityCheck) -> "DataQualityRunner":
        """Register a check. Returns self for fluent chaining."""
        self.checks.append(check)
        return self

    def run(self, df: pd.DataFrame, raise_on_error: bool = True
            ) -> tuple[list[DataQualityResult], pd.Series]:
        """Run every check against df.

        Returns (results, quarantine_mask) where quarantine_mask is True for
        rows that failed at least one QUARANTINE-severity check. Rows failing
        an ERROR check trigger a raise (unless raise_on_error=False, used by
        the HTML report to show the failure rather than crash).
        """
        self.results = []
        quarantine_mask = pd.Series(False, index=df.index)
        error_failures = []

        for check in self.checks:
            passing = check.rule(df)                    # True = row passes
            failing = ~passing
            failed_count = int(failing.sum())
            result = DataQualityResult(
                name=check.name, column=check.column, severity=check.severity,
                passed=(failed_count == 0), failed_count=failed_count,
                total_count=len(df),
                failed_sample=df.loc[failing, check.column].head(5).tolist(),
            )
            self.results.append(result)

            if check.severity == Severity.QUARANTINE:
                quarantine_mask |= failing              # collect bad rows aside
            elif check.severity == Severity.ERROR and failed_count > 0:
                error_failures.append(result)

        if raise_on_error and error_failures:
            names = ", ".join(f"{r.name} ({r.failed_count} rows)"
                              for r in error_failures)
            raise DataQualityError(f"ERROR-severity checks failed: {names}")

        return self.results, quarantine_mask

    # ---- reporting -------------------------------------------------------- #

    def results_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "check": r.name, "column": r.column, "severity": r.severity.value,
            "passed": r.passed, "failed_count": r.failed_count,
            "pass_rate": round(r.pass_rate, 4),
            "failed_sample": r.failed_sample,
        } for r in self.results])

    def to_html(self, path, title: str = "Data Quality Report") -> None:
        """Write a self-contained HTML report (an artifact, not print output)."""
        df = self.results_dataframe()
        n_pass = int(df["passed"].sum())
        n_fail = len(df) - n_pass

        def row_class(r):
            if r["passed"]:
                return "pass"
            return {"error": "fail-error", "warn": "fail-warn",
                    "quarantine": "fail-quarantine"}[r["severity"]]

        rows_html = "\n".join(
            f'<tr class="{row_class(r)}">'
            f'<td>{r["check"]}</td><td>{r["column"]}</td>'
            f'<td>{r["severity"]}</td><td>{"PASS" if r["passed"] else "FAIL"}</td>'
            f'<td>{r["failed_count"]}</td><td>{r["pass_rate"]:.2%}</td>'
            f'<td>{r["failed_sample"]}</td></tr>'
            for _, r in df.iterrows())

        html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title><style>
body{{font-family:system-ui,sans-serif;margin:2rem;color:#1a1a1a}}
h1{{margin-bottom:.2rem}} .summary{{margin:1rem 0;font-size:1.1rem}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:.5rem .7rem;text-align:left;font-size:.9rem}}
th{{background:#f4f4f4}}
.pass td:nth-child(4){{color:#137333;font-weight:600}}
.fail-error td:nth-child(4){{color:#c5221f;font-weight:700}}
.fail-warn td:nth-child(4){{color:#b06000;font-weight:600}}
.fail-quarantine td:nth-child(4){{color:#8430ce;font-weight:600}}
.badge{{padding:.15rem .5rem;border-radius:4px;color:#fff}}
</style></head><body>
<h1>{title}</h1>
<div class="summary">{n_pass} passed &middot; <b>{n_fail} failed</b> &middot; {len(df)} checks total</div>
<table><thead><tr><th>Check</th><th>Column</th><th>Severity</th>
<th>Result</th><th>Failed rows</th><th>Pass rate</th><th>Sample failures</th>
</tr></thead><tbody>{rows_html}</tbody></table>
</body></html>"""
        path = str(path)
        with open(path, "w") as fh:
            fh.write(html)
