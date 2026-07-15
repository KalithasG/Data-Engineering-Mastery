# Project 1.2 — Line-by-Line Explanation

This walks through **every meaningful block** of the FIFA cleaning pipeline so you understand the *why* behind each choice. After reading it you'll be ready for **Assignment 1.2 (Netflix catalog cleaner)** on your own.

**Files covered:** `generate_sample_data.py`, `fifa_cleaner.py`, `run_pipeline.py`, `test_fifa_cleaner.py`.

---

## Part A — `generate_sample_data.py`: manufacturing realistic dirt

The whole point of this generator is to reproduce the *systematic* ways real data is dirty. Real dirt is never random — it's dirty in explainable, patterned ways, and that's what makes it fixable with one parser instead of by hand.

### Currency strings
```python
def currency_string(v):
    if v >= 1_000_000: return f"€{v / 1_000_000:.1f}M"
    if v >= 1_000:     return f"€{v / 1_000:.0f}K"
    return f"€{v:.0f}"
```
Produces `€105.5M`, `€500K`, `€0` — FIFA's real export format. A human reads these easily; a `SUM()` chokes on them. This is a **validity** problem: the column is text when it needs to be numeric.

### Composite ratings
```python
def composite_rating(base):
    if roll < 0.30: return f"{base}+{random.randint(1, 3)}"   # "90+2"
    if roll < 0.35: return f"{base}-{random.randint(1, 2)}"   # "78-1"
    return str(base)                                          # "85"
```
`90+2` means "base 90, +2 modifier = 92." A **composite string masquerading as a scalar** — you must parse and evaluate it, not just cast it.

### Three date formats in one column
```python
if fmt < 0.5:  return f"{y}-{m:02d}-{d:02d}"   # ISO 2019-07-01
if fmt < 0.8:  return f"{m}/{d}/{y}"           # US 7/1/2019
return f"{d} {month_abbr} {y}"                 # 1 Jul 2019
```
The single nastiest real-world pattern: **the same column holds multiple formats** because data was merged from different systems. `7/1/2019` is especially dangerous — is it Jan 7 or Jul 1? You must parse with an *explicit, ordered format list*, never a "smart" auto-parser that guesses inconsistently row-to-row.

### Injected duplicates
```python
dupes = df.sample(frac=0.03, random_state=SEED)
df = pd.concat([df, dupes], ignore_index=True)
df = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
```
3% of rows are exact duplicates, then shuffled so they're **not adjacent** (realistic — you can't just compare neighboring rows). This is a **uniqueness** problem.

> **Note:** during development the `validate()` gate caught a real bug here — `potential` could exceed 99 when a high base rating got a `+3` modifier. The generator was fixed to cap the base. **That's the quality gate doing its job:** it refused to let out-of-range data through, exactly as designed.

---

## Part B — `fifa_cleaner.py`: the chainable cleaner

### The `CleaningStep` audit record
```python
@dataclass
class CleaningStep:
    step: str
    quality_dimension: str
    rows_affected: int
    detail: str = ""
    failed_samples: list = field(default_factory=list)
```
Every pipeline step appends one of these to an audit list. This is what turns "I cleaned the data" into an **auditable artifact** — you can show exactly what each step changed, how many rows it touched, and samples of what failed. Production cleaning is never "trust me"; it's "here's the report."

### The constructor: never mutate raw
```python
def __init__(self, df):
    self.df = df.copy()      # <-- the critical line
    self.audit = []
    self._input_rows = len(df)
```
`df.copy()` means the caller's original dataframe is **never modified**. Raw data is sacred — the same principle as an immutable Bronze layer. There's even a test that proves it (`test_original_dataframe_never_mutated`).

### The parsers are static and pure
```python
@staticmethod
def parse_currency_value(raw):
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)          # already numeric -> idempotent
    match = CURRENCY_RE.match(str(raw).strip())
    if not match:
        return None                # unparseable -> None, never raises
    number = float(match.group(1))
    suffix = match.group(2).upper()
    multiplier = {"M": 1_000_000, "K": 1_000, "": 1}[suffix]
    return number * multiplier
```
Four deliberate design points, each worth internalizing:
1. **Static method** → testable in complete isolation, no object needed. See the `@pytest.mark.parametrize` tests.
2. **Already-numeric passthrough** (`isinstance(raw, (int, float))`) → this is what makes the step **idempotent**. Run it twice: the second run sees floats and returns them unchanged.
3. **Returns `None` on failure, never raises** → one bad row can't crash a pipeline processing millions of good rows. The *caller* decides what to do with failures.
4. **One parser, everywhere** → both `value_eur` and `wage_eur` use this same function. You never fix currency by hand.

`parse_rating_value` follows the identical shape for `90+2 → 92`.

### Each step returns `self` — the fluent interface
```python
def normalize_text(self, column):
    before = self.df[column].copy()
    self.df[column] = self.df[column].str.strip().str.title()
    changed = int((before != self.df[column]).sum())
    self.audit.append(CleaningStep(
        step=f"normalize_text({column})",
        quality_dimension="consistency",
        rows_affected=changed,
        detail="strip + title-case",
    ))
    return self          # <-- enables .normalize_text(...).parse_currency(...)
```
Returning `self` is what lets the whole pipeline read as one sentence. Note the step also records **which of the 6 quality dimensions** it addresses — here, **consistency** (`  BRAZIL ` and `Brazil` must collapse to one value or every `GROUP BY nationality` double-counts).

### `parse_dates` — explicit formats, logged per format
```python
result = pd.Series(pd.NaT, index=self.df.index, dtype="datetime64[ns]")
hits_per_format = {}
for fmt in DATE_FORMATS:                       # ["%Y-%m-%d", "%m/%d/%Y", "%d %b %Y"]
    unparsed = result.isna()
    attempt = pd.to_datetime(self.df.loc[unparsed, column], format=fmt, errors="coerce")
    hits_per_format[fmt] = int(attempt.notna().sum())
    result.loc[unparsed] = attempt
```
The loop tries each known format **only on rows not yet parsed**, and records how many rows each format claimed. Why this design:
- **Explicit format list** → no silent misinterpretation of `7/1/2019`.
- **Per-format hit counts in the audit** → if a *new* format appears upstream next month, its rows fail all known formats and the failure count spikes. You find out immediately instead of silently dropping dates.
```python
if pd.api.types.is_datetime64_any_dtype(self.df[column]):
    ... return self      # already datetime -> idempotent no-op
```
The guard at the top makes a second run a no-op.

### `dedupe` — deterministic, therefore idempotent
```python
self.df = self.df.drop_duplicates(subset=[key], keep="first")
```
Dedupe on the **business key** (`player_id`), keeping the first occurrence. `keep="first"` is deterministic, so a second run — which finds zero duplicates — removes nothing. **Uniqueness** dimension.

### `handle_nulls` — a per-column business decision
This is the most nuanced method. Nulls are not a single problem with a single fix:
```python
club_nulls = int(self.df["club"].isna().sum())
self.df["club"] = self.df["club"].fillna("Free Agent")
```
`club = None` means the player is a **free agent** — a *valid state*, not missing data. We label it `Free Agent`. This is the "**when NOT to clean**" rule: blindly dropping or imputing this would destroy real signal.

```python
value_nulls_mask = self.df["value_eur"].isna()
if "value_eur_imputed" in self.df.columns:
    self.df["value_eur_imputed"] = self.df["value_eur_imputed"] | value_nulls_mask
else:
    self.df["value_eur_imputed"] = value_nulls_mask
position_median = self.df.groupby("position")["value_eur"].transform("median")
self.df["value_eur"] = (self.df["value_eur"]
                        .fillna(position_median)
                        .fillna(self.df["value_eur"].median()))
```
`value_eur = None` is diagnosed as **MAR (Missing At Random)** — missingness relates to *observable* attributes (obscure players lack a market value). The correct response to MAR is **conditional imputation**: fill with the median *of the player's position group*, not a global median. Three subtleties:
1. **Flag before filling** (`value_eur_imputed`) so downstream consumers can exclude imputed rows from analysis. Never silently substitute.
2. **The `| ` (OR) instead of `=`** — on a re-run the values are already filled (mask all False); overwriting the flag with `=` would erase the flags from the first run. This exact line was a **bug caught by the idempotency test** during development. Getting idempotency right is subtle.
3. **The second `.fillna(global median)`** handles a position group where *every* value was null (group median would itself be NaN).

### `validate` — assertions, not warnings
```python
assert self.df["player_id"].is_unique, "player_id must be unique after dedupe"
assert self.df["overall"].between(1, 99).all(), "overall out of 1-99 range"
assert self.df["value_eur"].notna().all(), "value_eur still has nulls after imputation"
...
```
Hard gates. `assert` **raises** — bad data cannot flow downstream. This is a "hard fail" quality gate (Primer 2.4). Range checks (`between(1, 99)`) are the cheapest available proxy for the hardest quality dimension, **accuracy**.

### Outputs
```python
def quality_report(self):
    return pd.DataFrame([...])     # the audit list as a dataframe
def to_parquet(self, path):
    self.df.to_parquet(path, index=False)
```
The report is a **dataframe/CSV artifact** — storable, diffable between runs, alertable — not print statements. Parquet output is typed, compressed, and columnar (ready for the analytical engines in later phases).

---

## Part C — `run_pipeline.py`: the pipeline reads as a sentence
```python
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
```
That chain *is* the documentation of what cleaning happens, in order. This readability is the entire reason for the fluent (return-`self`) design.

---

## Part D — `test_fifa_cleaner.py`: proving it works

### Parser tests (parametrized)
```python
@pytest.mark.parametrize("raw,expected", [
    ("€105.5M", 105_500_000.0),
    (750_000.0, 750_000.0),     # already numeric passes through
    ("garbage", None),          # unparseable -> None, never an exception
    ...
])
def test_parse_currency_value(raw, expected):
    assert FIFACleaner.parse_currency_value(raw) == expected
```
Because the parsers are pure static functions, you can hammer them with edge cases cheaply. Note the cases that lock in idempotency (numeric passthrough) and safety (garbage → None).

### The most important test — idempotency
```python
def test_pipeline_is_idempotent(dirty_df):
    once = run_full_pipeline(dirty_df).df.reset_index(drop=True)
    twice = run_full_pipeline(once).df.reset_index(drop=True)
    pd.testing.assert_frame_equal(once, twice)
```
Run the pipeline, then feed its **output** back through the **same** pipeline. If any value differs, some step isn't idempotent and the pipeline is unsafe to retry. **This is the test that caught the imputed-flag bug** described above. Idempotency is the theme that runs through the entire playbook — a pipeline you can safely re-run is a pipeline you can operate.

**Assignment tie-in:** Assignment 1.2 explicitly requires "one unit test proving idempotency (running twice = running once)." This is your template.

---

## Your Assignment 1.2 checklist, mapped to what you just learned

| Assignment requirement | Where this project taught it |
|---|---|
| Chainable, class-based cleaner | `FIFACleaner`, every method returns `self` |
| Classify ≥5 issues by the 6 QC dimensions | the dirt table in README + `quality_dimension` on each step |
| Split a column by content type | you'll split Netflix `duration` (min vs. seasons) — analogous to why one global transform fails |
| Handle a multi-value column | `listed_in`/`cast` → array-vs-bridge decision (see Primer 4.3 explode vs. unpivot) |
| Diagnose MCAR/MAR/MNAR + justify | `handle_nulls` MAR reasoning for `value_eur` |
| Produce a data-quality report artifact | `quality_report()` → CSV |
| Unit test proving idempotency | `test_pipeline_is_idempotent` |

For Netflix, the tricky new bit is `duration`: movies use `"90 min"`, TV shows use `"2 Seasons"`. A single global parser fails because the *unit depends on `type`* — you must branch on content type. That's the direct analogue of "one parser per systematic pattern." Now go build it.
