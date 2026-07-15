# Project 2.4 — Data Quality Framework with Google Play Store

> **Guided Project** from Phase 2 of the DE Playbook.
> Concepts: declarative expectations, a reusable check framework, severity tiers (hard-fail / soft / quarantine), distributional/volume checks, quality reports.

📖 **Line-by-line walkthrough: [EXPLANATION.md](EXPLANATION.md).**

## What this project builds

A **dataset-agnostic** data-quality framework — `DataQualityCheck` (a declarative expectation) + `DataQualityRunner` (runs them, produces results, quarantines bad rows) — plus 12 Play Store expectations spanning all six quality categories, an HTML + CSV report, and a **CI-style gate** that exits non-zero when an `ERROR`-severity check fails.

```
DataQualityCheck(name, column, rule, severity)   <- declarative expectation
DataQualityRunner.add_check(...).run(df)          -> results + quarantine mask
                                                       |
                          ERROR -> raise (block)   WARN -> log   QUARANTINE -> reject rows
```

## How to run

```bash
python generate_sample_data.py                          # clean batch + a 10%-volume bad batch
python run_quality.py                                   # gates the clean batch (exits 1 on the 19.0 bug)
python run_quality.py --batch playstore_bad_batch.csv   # trips the volume check too
pytest test_dq_framework.py -v                          # 7 framework tests
```
Reports land in `data/reports/` (HTML + CSV); cleaned Parquet and quarantined rejects in `data/clean/`.

## The 12 expectations (all six categories covered)

| Category | Check | Severity |
|---|---|---|
| Schema | `schema_has_app_name`, `rating_is_numeric` | error / quarantine |
| Completeness | `app_name_not_null`, `category_not_null` | quarantine / warn |
| Validity | `rating_in_range` (1.0–5.0), `installs_non_negative`, `price_non_negative` | error / quarantine / warn |
| Validity (accepted values) | `category_in_allowed_set`, `content_rating_valid` | quarantine / warn |
| Uniqueness | `app_id_unique` | quarantine |
| Referential | `reviews_imply_rating` | warn |
| Distributional / volume | `row_count_within_baseline` (±20%) | error |

## Design decisions

### 1. Expectations are declarative and reusable
A check is just `(name, column, rule, severity)` where `rule` is a `Callable(df) -> bool Series`. Adding a new check is one `add_check(...)` call — no new control flow. The framework knows nothing about Play Store; the domain checks live in `run_quality.py`.

### 2. Row-level rules enable quarantine
Rules return a **per-row** boolean Series (True = passes), not a single verdict. That's what lets the runner build a `quarantine_mask` and route exactly the failing rows to a rejects file while keeping the good ones — the "quarantine" quality gate, often the best default.

### 3. Three severity tiers, three responses
- **ERROR → hard fail.** `rating_in_range` and the volume check raise `DataQualityError` and the process exits 1. Severe issues (out-of-range values, a batch that's 10% of normal size) must block the pipeline.
- **WARN → soft fail.** Logged in the report, pipeline continues. For issues that are worth knowing but not worth stopping for.
- **QUARANTINE → route aside.** Failing rows go to a rejects table; clean rows proceed to Parquet.

### 4. The volume check catches what row-level rules can't
`row_count_within_baseline` flags a batch whose size differs from the rolling baseline by >20%. The "bad batch" (206 rows vs. a 2,000 baseline) trips it even though most *individual* rows are fine — this is how you catch **upstream breakage** (a partial extract, a broken join upstream) that no single-row rule would notice.

### 5. Report first, then gate
`run_quality.py` generates the HTML/CSV report with `raise_on_error=False` *before* enforcing the gate — so the artifact exists precisely when the pipeline is about to fail, which is exactly when you want to read it.

## Deliverables checklist

- [x] Custom quality framework (`dq_framework.py`)
- [x] HTML + CSV quality report (`data/reports/`)
- [x] Pipeline that fails on `error` severity (exit code 1)
- [x] Cleaned Parquet output + quarantined rejects (`data/clean/`)
- [x] Framework tests (`test_dq_framework.py`, 7 tests)
