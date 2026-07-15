# Project 2.4 — Line-by-Line Explanation

Walks through the data-quality framework. After this you'll be ready for **Assignment 2.4 (a quality gate for an Amazon/Zomato content catalog)** on your own.

**Files covered:** `generate_sample_data.py`, `dq_framework.py`, `run_quality.py`, `test_dq_framework.py`.

---

## The idea (read first)

Ad-hoc quality checks (`assert df.rating.max() <= 5` scattered through a script) don't scale and can't be reused. A **framework** formalizes checks into declarative, reusable **expectations** with a consistent way to respond by severity. Think of a table's schema + quality rules as an **API contract** between the team producing the data and the teams consuming it.

---

## Part A — `generate_sample_data.py`

### Injecting known, countable defects
```python
df.loc[bad_rating, "rating"] = [19.0, 6.5, -1.0, 5.5, 10.0, 7.7, 8.8, 6.1]
df.loc[null_names, "app_name"] = None
df.loc[neg_installs, "installs"] = -100
df.loc[bad_cat, "category"] = "UNKNOWN_CATEGORY"
dupes = df.loc[...].copy(); df = pd.concat([df, dupes])
```
Each defect maps to a check and a quality category. The `19.0` rating is a nod to a real, famous Play Store data bug — an app rated 19 on a 5-point scale. Injecting *known counts* lets the tests assert exact numbers.

### The "bad batch" for the volume check
```python
bad = inject_defects(build_apps(200, start=10_001))   # 10% of normal volume
```
A batch that is only 10% the usual size. No single-row rule would flag it — every row might be individually valid — but it's clearly a broken extract. This exists to demonstrate the **distributional/volume** check.

---

## Part B — `dq_framework.py` (the reusable engine)

### `Severity` — the response policy as an enum
```python
class Severity(str, Enum):
    ERROR = "error"           # hard fail — block the pipeline
    WARN = "warn"             # soft fail — log and continue
    QUARANTINE = "quarantine" # route bad rows aside, keep the rest
```
Subclassing `str` makes the enum serialize cleanly into reports/CSV. These three tiers are the standard quality-gate responses from Primer 2.4.

### `DataQualityCheck` — a declarative expectation
```python
@dataclass
class DataQualityCheck:
    name: str
    column: str
    rule: Callable[[pd.DataFrame], pd.Series]   # returns True for PASSING rows
    severity: Severity = Severity.WARN
    description: str = ""
```
The whole check is just data + one function. **`rule` returns a per-row boolean Series** (True = passes). That row-level granularity is the key design choice — it's what makes quarantine possible (you know *which* rows failed, not just *that* some did).

### `DataQualityResult` — and a computed pass rate
```python
@property
def pass_rate(self):
    if self.total_count == 0:
        return 1.0
    return (self.total_count - self.failed_count) / self.total_count
```
Each result carries the failed count, total, and a sample of failing values. `pass_rate` is derived, with a guard against divide-by-zero on an empty frame.

### `DataQualityRunner.add_check` — fluent registration
```python
def add_check(self, check):
    self.checks.append(check)
    return self             # enables .add_check(...).add_check(...)
```
Returns `self`, so checks chain like the cleaners in Phase 1. (`test_add_check_is_chainable` asserts `returned is runner`.)

### `run` — the core loop
```python
quarantine_mask = pd.Series(False, index=df.index)
error_failures = []
for check in self.checks:
    passing = check.rule(df)             # True = passes
    failing = ~passing
    failed_count = int(failing.sum())
    result = DataQualityResult(..., failed_sample=df.loc[failing, check.column].head(5).tolist())
    self.results.append(result)

    if check.severity == Severity.QUARANTINE:
        quarantine_mask |= failing       # accumulate bad rows across checks
    elif check.severity == Severity.ERROR and failed_count > 0:
        error_failures.append(result)

if raise_on_error and error_failures:
    raise DataQualityError(...)
return self.results, quarantine_mask
```
Read this carefully — it's the heart of the framework:
- Every check produces a `failing` boolean mask.
- **QUARANTINE** failures are OR-ed into `quarantine_mask` (`|=`), so a row failing *any* quarantine check ends up in the rejects. This accumulation across checks is why the mask is built incrementally.
- **ERROR** failures are collected and, at the end, raise `DataQualityError` — *unless* `raise_on_error=False`.
- The **`raise_on_error` flag** is what lets `run_quality.py` generate the report first (without crashing) and *then* enforce the gate. Two calls, two purposes.

### `to_html` — the report as a self-contained artifact
```python
def row_class(r):
    if r["passed"]: return "pass"
    return {"error": "fail-error", "warn": "fail-warn", "quarantine": "fail-quarantine"}[r["severity"]]
```
Builds a standalone HTML file with severity-colored rows and a pass/fail summary. It's a real artifact you can attach to a run, email, or diff — not ephemeral print output. (Primer 2.4 and Assignment 2.4 both require a report artifact.)

---

## Part C — `run_quality.py` (the Play Store application)

### 12 checks across all six categories
```python
.add_check(DataQualityCheck("rating_in_range", "rating",
    lambda df: pd.to_numeric(df["rating"], errors="coerce").between(1.0, 5.0),
    Severity.ERROR, "..."))
```
Note `pd.to_numeric(..., errors="coerce")` inside the rule — it defends against a non-numeric rating sneaking in (coerced to NaN, which then fails `between`). Each check is one `add_check` call; the six categories (schema, completeness, validity, uniqueness, referential, distributional) are all represented, which is exactly Assignment 2.4's ">=12 expectations spanning all 6 categories."

### The volume check
```python
.add_check(DataQualityCheck("row_count_within_baseline", "app_id",
    lambda df: pd.Series(
        abs(len(df) - expected_baseline) <= VOLUME_TOLERANCE * expected_baseline,
        index=df.index),
    Severity.ERROR, "..."))
```
This rule doesn't look at row *content* — it looks at `len(df)` vs. a baseline and broadcasts a single verdict to every row. The bad batch (206 rows vs. 2,000 baseline, >20% off) fails it wholesale. This is the distributional check that catches upstream breakage invisible to row-level rules.

### Report-first, then gate
```python
results, quarantine_mask = runner.run(df, raise_on_error=False)   # build artifact
runner.to_html(...); runner.results_dataframe().to_csv(...)
rejects = df[quarantine_mask]; good = df[~quarantine_mask]        # quarantine split
good.to_parquet(...)
try:
    runner.run(df, raise_on_error=True)                           # enforce gate
except DataQualityError as exc:
    return 1                                                      # non-zero -> CI fails
```
The first `run` (no raise) produces the report and the quarantine split. The second `run` (raising) enforces the gate as a **process exit code** — this is what lets the check block a CI/CD pipeline. Returning 1 on failure is the whole point: a failing quality gate should *stop the deploy*.

---

## Part D — `test_dq_framework.py`

Tests exercise the framework mechanics independently of Play Store: failure counting + pass rate, ERROR raising, `raise_on_error=False` suppression, quarantine-mask accumulation across multiple checks, WARN not raising, and `add_check` chaining. Testing the framework separately from the domain checks is good practice — the engine and the expectations evolve independently.

---

## Your Assignment 2.4 checklist, mapped to what you just learned

| Assignment requirement | Where this project taught it |
|---|---|
| ≥12 expectations across all 6 categories | the `build_runner` check list + README table |
| One distributional/volume expectation + prove it catches a bad batch | `row_count_within_baseline` + the 10%-volume `playstore_bad_batch` |
| Three-tier response (hard-fail / soft / quarantine), justified | `Severity` enum + per-check assignment |
| HTML/Markdown report per run (counts + sample failing rows) | `to_html` + `results_dataframe` |
| One-page "data contract" doc | see below |

**The data-contract doc** (Assignment 2.4's last requirement): a data contract is this framework's checks written up as a *promise to consumers*. As the producing team you'd commit to, e.g.: "`app_id` is unique and non-null; `rating` is numeric in [1.0, 5.0]; `category` is one of {…}; row count stays within ±20% of the 30-day rolling median." And you'd explicitly **not** guarantee: "`price` accuracy for third-party listings" or "reviews backfilled within the hour." The severity tiers map directly to contract strength — ERROR checks are hard guarantees (a breach blocks publication), WARN checks are best-effort. Treat the schema like an API contract between teams, validated in CI *before* data is published. Now go build the gate for Amazon/Zomato.
