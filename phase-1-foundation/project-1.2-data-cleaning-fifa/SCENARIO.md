# 🎫 Scenario — Project 1.2: Production Cleaning Pipeline for a Sports Analytics Firm

> Read this like a ticket handed to you at work. Everything you must do is in the question. Try to plan it yourself **before** opening [BUILD_GUIDE.md](BUILD_GUIDE.md).

## The situation

You work for a sports analytics firm that licenses the **FIFA player database** to betting and scouting clients. The raw export is a mess: market values arrive as strings like `€105.5M`, ratings as `90+2`, the same column mixes three date formats, players appear twice, and nationality values have random casing and whitespace. Last month an analyst "cleaned" it by hand in Excel; this month's export broke everything again.

Your tech lead assigns you this ticket:

## The ticket

> **Replace the hand-fixing with a reusable, auditable, re-runnable cleaning pipeline that turns the raw export into a validated Parquet file — every month, with zero manual steps.**

## 📊 Business questions the stakeholders need answered

Your clients can't compute ANY of these on the raw export — each one is blocked by a specific mess pattern. Clean data must unblock all of them:

| Stakeholder | Business question | Blocked by |
|---|---|---|
| **Scouting clients** | Who are the top-N most valuable players per position, and what's the total squad value per club? | `value_eur` is the string `€105.5M` — can't SUM or rank |
| **Scouting clients** | Which players' *true* current rating (base + form modifier) is highest? | ratings like `90+2` are text |
| **Betting clients** | What's the value-vs-wage efficiency by club and nationality? | currency strings + `  BRAZIL ` vs `Brazil` double-counts groups |
| **Analysts** | How does market value trend with tenure (time since joining)? | `joined_date` mixes 3 formats — can't sort or diff dates |
| **Account managers** | Exact player counts per club/nationality for licensing invoices | duplicate rows inflate counts; free agents (`club = NULL`) must count as a real segment, not be dropped |
| **Data governance** | "How trustworthy is this month's export?" | no audit trail exists — your quality report becomes the answer |

Every cleaning step you build should trace back to unblocking one of these.

## What you must work out (and your implementation must prove)

1. **Classify the dirt:** For each mess pattern (currency strings, composite ratings, mixed dates, casing noise, duplicates, null club, null value) — **which of the 6 data-quality dimensions** (completeness, validity, consistency, uniqueness, accuracy, timeliness) does it violate?
2. **Systematic parsers:** Why must `€105.5M → 105_500_000` be handled by **one parser function** rather than hand fixes? What should a parser return for garbage input — raise, or `None` + log — and why?
3. **Composite ratings:** How do you resolve `90+2 → 92` and `78-1 → 77` safely?
4. **Mixed dates:** Why is an *explicit, ordered format list* safer than a smart auto-parser for a column mixing `2019-07-01`, `7/1/2019`, `1 Jul 2019`? How do you detect when a *new* format appears upstream?
5. **Chainable design:** How do you structure the cleaner as a class where every step returns `self`, so the pipeline reads `clean().parse().dedupe().validate()`? Why does the constructor copy the input dataframe?
6. **Nulls are decisions:** `club = NULL` means *free agent* — a valid state. `value = NULL` is missing-at-random (MAR). What's the correct, *different* handling of each? Why must every imputed value carry a flag column?
7. **Idempotency:** What has to be true of every step so that running the pipeline **twice produces exactly the same output as once**? How do you *prove* it with a unit test?
8. **Quality gates:** Which invariants (unique player_id, ratings 1–99, no negative values, dates parsed) should be hard assertions that block the pipeline?
9. **Audit trail:** How do you record what every step did (rows affected, failures, samples) as a **report artifact** — not print statements?

## Deliverables (definition of done)

- [ ] `FIFACleaner` class with fluent method chaining
- [ ] Data-quality report artifact (CSV) listing every step, its quality dimension, rows affected, and failure samples
- [ ] Unit tests including **an idempotency proof** (output fed back through the pipeline is unchanged)
- [ ] Clean, typed Parquet output

## Data

- **To test:** `python generate_sample_data.py` creates a synthetic FIFA export with all the dirt above.
- **To practice for real:** download [FIFA 19 complete player dataset](https://www.kaggle.com/datasets/karangadiya/fifa19) (`data.csv` — its `Value`/`Wage` columns have the real `€105.5M` strings). Rename columns to match (`Value→value_eur`, `Wage→wage_eur`, `Overall→overall`, `Joined→joined_date`, `Club→club`, `Nationality→nationality`) or adapt the cleaner's column names — adapting to a real schema **is** the practice.

➡️ Ready to build? Follow [BUILD_GUIDE.md](BUILD_GUIDE.md). Reference implementation in this folder, explained in [EXPLANATION.md](EXPLANATION.md).
