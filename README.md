# 🏗️ Data Engineering Mastery

> **Goal: master Data Engineering by building projects** — following the Silicon Valley Senior DE Playbook.
> Every phase: read the scenario → build it yourself with the step-by-step guide → compare against the reference → prove the skill on a solo assignment with **real Kaggle data**.

---

## 🔁 The learning workflow (how to use this repo)

Each guided project folder contains a complete learning kit:

| File | What it is | When to use it |
|---|---|---|
| **`SCENARIO.md`** | A realistic work ticket — *everything you must do, phrased as the question* | **Start here.** Plan your approach on paper first |
| **`BUILD_GUIDE.md`** | Step-by-step build instructions with checkpoints | Build it yourself, step by step |
| reference code | A complete, tested implementation | Compare after each checkpoint, or when stuck |
| **`EXPLANATION.md`** | The reference explained line by line | Deep study after building |
| **`README.md`** | Design decisions + how to run | Reference |

**Data policy:** every project ships `generate_sample_data.py` producing a **synthetic dataset** (same schema and dirt as the real one) so the code always runs and tests pass offline. **For your practice, use the original Kaggle dataset** — each SCENARIO links it and explains how to drop it into `data/raw/`.

Then prove the skill transfers: do the matching **solo assignment** (questions in [`assignments/`](assignments/) — deliberately not built) on a *different* real Kaggle dataset, with no guide.

📅 **Your Phase 1 plan is in [MASTERY_PLAN.md](MASTERY_PLAN.md) — the concrete step-by-step path to mastering this phase.**

---

## 📋 Full Agenda — all phases of the playbook

### ✅ Phase 1 — Foundation: Data Modeling & Cleaning *(built — start here)*

*Click a project to open its directory with all files; the 🎫 link jumps straight to its scenario.*

| Project (directory) | Start | Scenario | Skills | Kaggle dataset |
|---|---|---|---|---|
| [1.1 Star Schema](phase-1-foundation/project-1.1-star-schema-olist/) | [🎫](phase-1-foundation/project-1.1-star-schema-olist/SCENARIO.md) | Build the analytics warehouse for an e-commerce marketplace | Dimensional modeling, grain, surrogate keys, star schema, fan traps | Olist Brazilian E-Commerce |
| [1.2 Data Cleaning](phase-1-foundation/project-1.2-data-cleaning-fifa/) | [🎫](phase-1-foundation/project-1.2-data-cleaning-fifa/SCENARIO.md) | Replace hand-fixed Excel cleaning with an auditable pipeline | 6 quality dimensions, systematic parsers, MCAR/MAR/MNAR, idempotency | FIFA 19 players |
| [1.3 SCD](phase-1-foundation/project-1.3-scd-instacart/) | [🎫](phase-1-foundation/project-1.3-scd-instacart/SCENARIO.md) | Stop historical reports from rewriting themselves | SCD Type 1/2/3, merge logic, point-in-time joins | Instacart Market Basket |

**Solo assignments (you build, on real Kaggle data):** [1.1 Global Superstore](assignments/assignment-1.1-global-superstore-QUESTIONS.md) · [1.2 Netflix](assignments/assignment-1.2-netflix-QUESTIONS.md) · [1.3 IBM HR](assignments/assignment-1.3-ibm-hr-scd-QUESTIONS.md)

### ⏳ Phase 2 — Core ETL Pipeline Engineering *(next)*
Incremental loading & watermarks (NYC Taxi) · multi-source joins & null semantics (Flight Delays) · idempotency & append-only patterns (Chicago Crime) · data-quality frameworks & contracts (Google Play Store). Assignments: Divvy bikeshare, Craigslist cars, audit pipeline, Amazon/Zomato quality gate.

### ⏳ Phase 3 — Advanced Processing & Warehousing
Medallion architecture Bronze/Silver/Gold (Airbnb) · transformation-as-code with dbt (Walmart retail) · analytical SQL: window functions, cohorts, OLAP (MovieLens 25M). Assignments: hotel bookings medallion, video-game-sales dbt project, Spotify cohort analysis.

### ⏳ Phase 4 — Large-Scale & Distributed Systems
PySpark on 130M Amazon reviews (partitions, shuffles, broadcast joins, skew) · Delta Lake ACID + time travel (US Accidents) · wide-to-long & UNPIVOT (Stack Overflow survey). Assignments: Yelp distributed processing, ACID pipeline with time travel, World Bank reshaping.

### ⏳ Phase 5 — Streaming & Real-Time Pipelines
Kafka producers/consumers & delivery semantics (Wikipedia clickstream) · micro-batching, enrichment & dead-letter queues (Sentiment140) · event time, watermarks & windowing. Assignments: crypto price feed, micro-batch enrichment with DLQ, out-of-order event handling.

### ⏳ Phase 6 — Production Engineering
Orchestration (Airflow DAGs, retries, backfills) · observability & data quality monitoring · cost optimization · CI/CD for data pipelines.

### 🏁 Capstone — end-to-end platform
One integrated project: ingestion → lakehouse → warehouse → streaming → orchestrated, tested, monitored. Plus the playbook's **Missing Pieces** (the gaps curricula skip) and the **Career & Interview Playbook**.

> Phases 2–6 get built here the same way — scenario, build guide, reference, assignment — when you're ready. Say the word after finishing Phase 1.

---

## 🚀 Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd phase-1-foundation/project-1.1-star-schema-olist
# read SCENARIO.md, then follow BUILD_GUIDE.md — or run the reference:
python generate_sample_data.py && python build_star_schema.py && python run_queries.py
```

| Project | Reference run |
|---|---|
| 1.1 | `python generate_sample_data.py && python build_star_schema.py && python run_queries.py` |
| 1.2 | `python generate_sample_data.py && python run_pipeline.py && pytest -q` |
| 1.3 | `python generate_sample_data.py && python scd_pipeline.py && python demo_queries.py` |

## 🗂️ Layout

```
README.md            <- this agenda          MASTERY_PLAN.md  <- your Phase 1 path
requirements.txt     .gitignore (data/ is regenerable, never committed)
phase-1-foundation/
    project-1.1-star-schema-olist/      SCENARIO · BUILD_GUIDE · reference code · EXPLANATION
    project-1.2-data-cleaning-fifa/     SCENARIO · BUILD_GUIDE · reference code · EXPLANATION · tests
    project-1.3-scd-instacart/          SCENARIO · BUILD_GUIDE · reference code · EXPLANATION
assignments/         <- solo assignment questions (not built — that's your job)
```
