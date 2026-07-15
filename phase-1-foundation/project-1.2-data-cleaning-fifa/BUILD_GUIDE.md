# 🛠️ Build Guide — Project 1.2: Data Cleaning Pipeline with FIFA

> Step-by-step guidance to build this **yourself** before peeking at the reference (`fifa_cleaner.py`, explained in [EXPLANATION.md](EXPLANATION.md)).

**Prereqs:** requirements installed · read [SCENARIO.md](SCENARIO.md) first.

---

## Step 0 — Get the data & eyeball the dirt
**Do:** `python generate_sample_data.py`, then open the CSV and *find* each mess pattern: `€105.5M`, `90+2`, three date formats, `  BRAZIL `, duplicated player_ids, null clubs/values.
**Checkpoint:** For each pattern, name the quality dimension it violates (validity? consistency? uniqueness? completeness?).

## Step 1 — Write the parsers as pure functions FIRST
**Do:** Before any class, write two standalone functions and unit-test them:
- `parse_currency_value("€105.5M") -> 105_500_000.0` (also `500K`, `€0`, already-numeric passthrough, garbage → `None`)
- `parse_rating_value("90+2") -> 92` (also `78-1`, plain `"85"`, already-int passthrough, garbage → `None`)
**Hints:** one regex each; a `{"M": 1e6, "K": 1e3, "": 1}` multiplier map; **return `None` on failure — never raise** (the caller logs failures; one bad row must not kill a batch).
**Checkpoint:** `pytest` passes a parametrized test with ≥6 cases per parser, including the passthrough cases (they're what makes re-runs idempotent).

## Step 2 — Build the class skeleton
**Do:** `class FIFACleaner:` whose `__init__(self, df)` stores **`df.copy()`** (never mutate the caller's raw data) plus an empty `self.audit` list. Add a `CleaningStep` dataclass: step name, quality_dimension, rows_affected, detail, failed_samples.
**Checkpoint:** A test proves the original dataframe is byte-identical after running your (empty) pipeline.

## Step 3 — Add chainable steps, one at a time — each `return self`
Order matters less than each step being idempotent and audited. Implement, in any order:
1. **`normalize_text(col)`** — strip + title-case (consistency). Log how many values changed.
2. **`parse_currency(col)`** / **`parse_rating(col)`** — map your Step-1 parsers over the column; count rows where raw was non-null but parse returned `None` (failures) and store 5 samples in the audit.
3. **`parse_dates(col)`** — loop an **explicit format list** (`%Y-%m-%d`, `%m/%d/%Y`, `%d %b %Y`), each format attempted only on still-unparsed rows; record hits-per-format. Guard: if the column is already datetime, no-op (idempotency).
4. **`dedupe(key)`** — `drop_duplicates(subset=[key], keep="first")` (deterministic ⇒ idempotent).
**Checkpoint:** `FIFACleaner(df).normalize_text("nationality").parse_currency("value_eur")...` chains and returns the cleaner.

## Step 4 — Nulls: make a *decision per column*
**Do:**
- `club` NULL = free agent (**valid state**) → fill with the label `"Free Agent"`, never drop.
- `value_eur` NULL = MAR → impute the **median of the player's position group** (`groupby("position").transform("median")`), with a global-median fallback, and set a `value_eur_imputed` flag **before** filling.
**Trap (a real bug from this build):** on a second run the mask is all-False — if you *assign* the flag you erase run-1's flags. **OR it into any existing flag** instead.
**Checkpoint:** Imputed rows are flagged; free agents labelled; nothing silently dropped.

## Step 5 — `validate()` as hard gates
**Do:** Assertions (raise, don't warn): unique `player_id` · `overall`/`potential` in 1–99 · no null / negative `value_eur` · `joined_date` is datetime dtype.
**Checkpoint:** Corrupt one value manually → pipeline dies loudly; restore → passes.

## Step 6 — The report artifact + Parquet
**Do:** `quality_report()` returns the audit list as a DataFrame (step, dimension, rows_affected, failed_samples); write it to CSV. `to_parquet()` writes the cleaned data.
**Checkpoint:** After a run you have `clean/*.parquet` + `clean/quality_report.csv`, and the report shows hits-per-date-format and dedupe counts.

## Step 7 — THE test: idempotency
**Do:** `once = pipeline(dirty).df` then `twice = pipeline(once).df` and `pd.testing.assert_frame_equal(once, twice)`.
**Checkpoint:** It passes. If it doesn't, some step isn't idempotent — usually the imputation flag (Step 4 trap) or a parser without passthrough (Step 1).

## Step 8 — Compare with the reference
Diff against `fifa_cleaner.py` / [EXPLANATION.md](EXPLANATION.md); note anything the reference audits that you don't.

➡️ **Next:** [Assignment 1.2 (Netflix)](../../assignments/assignment-1.2-netflix-QUESTIONS.md) — same skills, real Kaggle data, plus the new twist (`duration` means minutes for movies but seasons for shows).
