# 🏗️ Data Engineering Mastery

> A production-grade, hands-on journey through data engineering, built from the **Silicon Valley Senior DE Playbook**.
> **README-first development. One folder per project. Every pipeline runs end-to-end.**

This repository contains the **worked guided projects** for each phase. Each project ships:
- runnable code with a synthetic-data generator (so it runs offline — no Kaggle download required),
- a **`README.md`** with design decisions, and
- an **`EXPLANATION.md`** that walks the code **line by line** so you can learn the pattern, then do the matching **solo assignment** yourself.

---

## 📋 The 4-Step Learning Loop

Every phase follows the same loop:

```
1. READ    the Concept Primer   -> understand WHY before HOW
2. BUILD   the guided project    -> apply concepts with working code   (this repo)
3. DO      the Solo Assignment   -> same concepts, new dataset, no help (you)
4. REFLECT on the Missing Pieces -> connect to production reality
```

The guided projects here are step 2. The `EXPLANATION.md` files are your bridge to step 3.

---

## 🎯 Phase 1 — Foundation: Data Modeling & Cleaning

**Agenda:** learn the three foundational skills every data engineer needs — shaping data into an analytical (dimensional) model, cleaning dirty real-world data reliably, and tracking how dimensions change over time.

| # | Guided Project | Core Concepts | Dataset (shape) | Status |
|---|---|---|---|---|
| **1.1** | [Star Schema with Olist](phase-1-foundation/project-1.1-star-schema-olist/) | Dimensional modeling, grain, surrogate keys, star schema, unknown members, additive vs. non-additive measures | Olist Brazilian E-Commerce (8 tables) | ✅ Runs, 10 queries |
| **1.2** | [Data Cleaning with FIFA](phase-1-foundation/project-1.2-data-cleaning-fifa/) | 6 quality dimensions, systematic parsers, method chaining, MCAR/MAR/MNAR, idempotency, audit trails | FIFA player catalog | ✅ Runs, 23 tests pass |
| **1.3** | [Slowly Changing Dimensions with Instacart](phase-1-foundation/project-1.3-scd-instacart/) | SCD Type 1/2/3, merge/upsert, effective dates, point-in-time joins, hybrid SCD | Instacart catalog (3 monthly snapshots) | ✅ Runs, point-in-time verified |

### 📚 Study path for each project
1. Read the project's **`README.md`** — what it builds and the design decisions.
2. Run it (see below) and inspect the output.
3. Read the **`EXPLANATION.md`** — the line-by-line walkthrough.
4. Do the matching **solo assignment** from the playbook, on your own.

### ✍️ Your Phase 1 solo assignments (do these yourself)
These are deliberately **not** in this repo — the guided projects + explainers prepare you to build them unaided. Each explainer ends with a checklist mapping what you learned to the assignment.

- [ ] **Assignment 1.1** — Star schema for **Global Superstore** (grain, ≥4 dims, `dim_date` with fiscal quarter + holidays, a non-additive measure, fan-trap write-up) → prep: [1.1 EXPLANATION](phase-1-foundation/project-1.1-star-schema-olist/EXPLANATION.md)
- [ ] **Assignment 1.2** — Cleaning class for **Netflix** catalog (split `duration` by content type, multi-value `listed_in`/`cast`, MCAR/MAR/MNAR diagnosis, quality report, idempotency test) → prep: [1.2 EXPLANATION](phase-1-foundation/project-1.2-data-cleaning-fifa/EXPLANATION.md)
- [ ] **Assignment 1.3** — Employee history with SCD Type 2 for **IBM HR** (3 simulated batches, per-attribute Type 1 vs 2, point-in-time proof, **late-arriving correction**) → prep: [1.3 EXPLANATION](phase-1-foundation/project-1.3-scd-instacart/EXPLANATION.md)

---

## 🚀 Quick Start

```bash
# 1. Environment
python -m venv .venv && source .venv/bin/activate    # or: conda create -n de-mastery python=3.11
pip install -r requirements.txt

# 2. Run any project (each is self-contained)
cd phase-1-foundation/project-1.1-star-schema-olist
python generate_sample_data.py    # writes synthetic CSVs into data/raw/
python build_star_schema.py        # builds the star schema in DuckDB
python run_queries.py              # runs the 10 analytical queries
```

Per-project run commands:

| Project | Commands |
|---|---|
| **1.1** | `python generate_sample_data.py && python build_star_schema.py && python run_queries.py` |
| **1.2** | `python generate_sample_data.py && python run_pipeline.py && pytest -q` |
| **1.3** | `python generate_sample_data.py && python scd_pipeline.py && python demo_queries.py` |

> **Using the real Kaggle datasets instead?** Every project reads from `data/raw/`. Drop the real CSVs there (matching the column names the generator produces) and skip `generate_sample_data.py` — the rest of the pipeline is identical.

---

## 🗂️ Repository Layout

```
Data-Engineering-Mastery/
├── README.md                  <- you are here (the agenda)
├── requirements.txt
├── .gitignore                 <- generated data/ is ignored (regenerate anytime)
└── phase-1-foundation/
    ├── project-1.1-star-schema-olist/
    │   ├── README.md                 design decisions + ER diagram
    │   ├── EXPLANATION.md            line-by-line walkthrough
    │   ├── generate_sample_data.py
    │   ├── build_star_schema.py
    │   ├── analytical_queries.sql
    │   └── run_queries.py
    ├── project-1.2-data-cleaning-fifa/
    │   ├── README.md   EXPLANATION.md
    │   ├── generate_sample_data.py
    │   ├── fifa_cleaner.py
    │   ├── run_pipeline.py
    │   └── test_fifa_cleaner.py
    └── project-1.3-scd-instacart/
        ├── README.md   EXPLANATION.md
        ├── generate_sample_data.py
        ├── scd_pipeline.py
        └── demo_queries.py
```

Data files are `.gitignore`d — they're regenerable, so the repo stays lean. Run each project's `generate_sample_data.py` to recreate them.

---

## 🧭 Roadmap (from the Playbook)

- ✅ **Phase 1 — Foundation:** Data Modeling & Cleaning *(this repo)*
- ⏳ **Phase 2 — Core ETL:** incremental loading, multi-source joins, idempotency, quality frameworks
- ⏳ **Phase 3 — Warehousing:** medallion architecture, dbt, analytical SQL
- ⏳ **Phase 4 — Distributed:** PySpark, Delta Lake, wide-to-long
- ⏳ **Phase 5 — Streaming:** Kafka, micro-batch, event time & watermarks
- ⏳ **Phase 6 — Production:** orchestration, observability, cost, CI/CD

Each future phase will follow the same structure: guided projects with line-by-line explainers, leaving the solo assignments to you.
