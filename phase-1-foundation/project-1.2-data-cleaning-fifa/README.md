# Project 1.2 — Data Cleaning Pipeline with FIFA

> **Guided Project** from Phase 1 of the DE Playbook.
> Concepts: the 6 data-quality dimensions, systematic parsers, method chaining, MCAR/MAR/MNAR, idempotency, audit trails, quality gates.

🎫 **Learning by doing? Start with [SCENARIO.md](SCENARIO.md), build via [BUILD_GUIDE.md](BUILD_GUIDE.md), then study [EXPLANATION.md](EXPLANATION.md) line by line.**

## What this project builds

A chainable, class-based cleaner (`FIFACleaner`) that turns a deliberately messy FIFA-style player CSV into a validated, typed Parquet file — with a quality-report artifact and a unit-test suite that *proves* the pipeline is idempotent.

```python
cleaner = (FIFACleaner(raw_df)
           .normalize_text("nationality")   # consistency
           .parse_currency("value_eur")     # validity: "€105.5M" -> 105500000.0
           .parse_currency("wage_eur")
           .parse_rating("overall")         # validity: "90+2" -> 92
           .parse_rating("potential")
           .parse_dates("joined_date")      # validity: 3 formats, explicit list
           .dedupe(key="player_id")         # uniqueness
           .handle_nulls()                  # completeness (per-column strategy)
           .validate())                     # hard quality gates (assertions)
```

## How to run

```bash
python generate_sample_data.py      # writes data/raw/fifa_players_raw.csv (with realistic dirt)
python run_pipeline.py              # cleans -> data/clean/*.parquet + quality_report.csv
pytest test_fifa_cleaner.py -v      # 23 tests incl. the idempotency proof
```

## The dirt in the raw data (and which quality dimension each violates)

| Issue | Example | Quality dimension | Fix |
|---|---|---|---|
| Currency strings | `€105.5M`, `€500K` | Validity | one shared regex parser |
| Composite ratings | `90+2`, `78-1` | Validity | rating parser resolves modifier |
| 3 mixed date formats | `2019-07-01`, `7/1/2019`, `1 Jul 2019` | Validity + Consistency | explicit format list, hits logged per format |
| Whitespace/casing noise | `  BRAZIL ` vs `Brazil` | Consistency | strip + title-case |
| Exact duplicate rows | same `player_id` twice | Uniqueness | deterministic dedupe on business key |
| Null `club` | free agents | Completeness (valid state!) | labelled `Free Agent`, **not** treated as an error |
| Null `value_eur` | missing market value | Completeness (MAR) | position-group median + `value_eur_imputed` flag |

## Design decisions

1. **One parser per mess pattern, never hand fixes.** Dirt is systematic, so the fix must be systematic. `parse_currency_value` and `parse_rating_value` are pure static methods — trivially unit-testable.
2. **Failures are logged, never hidden.** Unparseable values become `None` and are counted + sampled into the audit trail. A parser that raises kills the pipeline on one bad row; a parser that silently guesses corrupts data.
3. **Nulls get a per-column business decision.** `club=None` means *free agent* — a valid state we label, not an error we fill (the "when NOT to clean" rule). `value_eur=None` is diagnosed as **MAR** (missingness relates to observable attributes → conditional imputation by position group), and every imputed row carries an explicit `value_eur_imputed` flag.
4. **Idempotency is designed in, then proven.** Every parser passes through already-clean values; dedupe is deterministic; the imputation flag ORs rather than overwrites. `test_pipeline_is_idempotent` feeds the pipeline's output back into itself and asserts frame equality. (That test caught a real bug during development: a re-run used to wipe the imputed flags.)
5. **Validation is a hard gate.** `validate()` uses assertions, not warnings — bad data must not flow downstream.
6. **The quality report is an artifact** (CSV/dataframe with step, dimension, rows affected, failure samples), not print statements — it can be stored, diffed between runs, and alerted on.

## Deliverables checklist

- [x] `FIFACleaner` class with fluent chaining (`fifa_cleaner.py`)
- [x] Data-quality report artifact (`data/clean/quality_report.csv`)
- [x] Unit tests incl. idempotency proof (`test_fifa_cleaner.py`, 23 tests)
- [x] Clean Parquet output (`data/clean/fifa_players_clean.parquet`)
