# 🎯 Phase 1 Mastery Plan

> Mastery = you can build it **without help**, explain it **cold in an interview**, and spot the classic bugs in someone else's code. This plan gets you there in ~3 weeks at 1–2 hrs/day (compress or stretch as you like — the *sequence* is what matters).

---

## The rule for every topic

```
1. SCENARIO.md   -> plan your approach ON PAPER before any code
2. BUILD_GUIDE   -> build it yourself, checkpoint by checkpoint
3. Reference     -> diff your build vs the reference; read EXPLANATION.md
4. ASSIGNMENT    -> new dataset, real Kaggle data, no guide. This is the exam.
```
Never skip step 4 — the guided project teaches the pattern; **the assignment is where you find out if you actually own it.**

---

## Week 1 — Dimensional Modeling (Project 1.1 → Assignment 1.1)

- **Day 1:** Read the playbook's Concept Primer 1.1. Then [SCENARIO](phase-1-foundation/project-1.1-star-schema-olist/SCENARIO.md) — write answers to all 10 questions on paper.
- **Day 2–3:** Build via the [BUILD_GUIDE](phase-1-foundation/project-1.1-star-schema-olist/BUILD_GUIDE.md) (steps 0–6) on synthetic data.
- **Day 4:** Steps 7–8 (queries + README). Download the **real Olist dataset** from Kaggle, drop into `data/raw/`, re-run everything against it. Real data will surprise you — that's the point.
- **Day 5–7:** [Assignment 1.1 — Global Superstore](assignments/assignment-1.1-global-superstore-QUESTIONS.md), real Kaggle data, no guide.

**Self-check before moving on (answer aloud, no notes):**
- [ ] "Walk me through designing a schema for X. What's the grain?" — 2-minute answer
- [ ] Why surrogate keys? What breaks with natural keys?
- [ ] What's a fan trap and how did your design avoid it?
- [ ] Why is a ratio non-additive, and what's the correct aggregation?

## Week 2 — Data Quality & Cleaning (Project 1.2 → Assignment 1.2)

- **Day 1:** Primer 1.2 → [SCENARIO](phase-1-foundation/project-1.2-data-cleaning-fifa/SCENARIO.md) on paper. Pay special attention to MCAR/MAR/MNAR.
- **Day 2–3:** Build via the [BUILD_GUIDE](phase-1-foundation/project-1.2-data-cleaning-fifa/BUILD_GUIDE.md). Write the parsers + their tests *first* (step 1) — TDD works beautifully here.
- **Day 4:** The idempotency test (step 7). If it fails, debug until you *feel* why idempotency is subtle. Then run against the **real FIFA 19 Kaggle export** (column mapping in the SCENARIO).
- **Day 5–7:** [Assignment 1.2 — Netflix](assignments/assignment-1.2-netflix-QUESTIONS.md).

**Self-check:**
- [ ] Name the 6 quality dimensions with an example of each from YOUR pipeline
- [ ] When should you NOT clean a null? Give your free-agent example
- [ ] MCAR vs MAR vs MNAR — definition + correct response for each
- [ ] Prove idempotency in one sentence + one test

## Week 3 — Slowly Changing Dimensions (Project 1.3 → Assignment 1.3)

- **Day 1:** Primer 1.3 → [SCENARIO](phase-1-foundation/project-1.3-scd-instacart/SCENARIO.md) on paper. Write your date-range conventions before anything else.
- **Day 2–4:** Build via the [BUILD_GUIDE](phase-1-foundation/project-1.3-scd-instacart/BUILD_GUIDE.md). Steps 5–6 (merge + point-in-time join) are the hardest thing in Phase 1 — budget two sessions. Deliberately join on `is_current` once and observe the wrong revenue; you'll never forget the bug after seeing it.
- **Day 5:** Real Instacart data: simulate 3 snapshots from the real `products.csv` yourself (the SCENARIO tells you how).
- **Day 6–7+:** [Assignment 1.3 — IBM HR](assignments/assignment-1.3-ibm-hr-scd-QUESTIONS.md) — includes the **late-arriving correction**, the one thing the guided project didn't hand you.

**Self-check:**
- [ ] Type 1 vs 2 vs 3: when each, and what each cannot answer
- [ ] Business key vs surrogate key in one breath
- [ ] Write the point-in-time join condition from memory
- [ ] What single assertion validates an entire Type 2 implementation?

---

## Mastery checklist (Phase 1 exit criteria)

You've mastered Phase 1 when **all** are true:

- [ ] All 3 guided projects built by you (not just run) and checked against the references
- [ ] All 3 assignments completed on **real Kaggle data** with zero guide
- [ ] Every self-check question above answerable cold
- [ ] You can explain to a rubber duck: grain → surrogate keys → unknown members → the 6 quality dimensions → idempotency → SCD Type 2 → point-in-time joins, as **one connected story** (they all serve "reports that are correct and stay correct")
- [ ] Bonus: read a colleague's (or an LLM's) star schema and find one flaw in under 10 minutes

**Then** tell Claude: *"Phase 1 done — build Phase 2"* and the next phase gets scaffolded the same way.
