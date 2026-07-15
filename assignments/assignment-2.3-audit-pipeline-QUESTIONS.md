# Assignment 2.3 — Provably-Idempotent Audit Pipeline

> **You build this.** Answer every question in writing before coding. Prep: [Project 2.3 EXPLANATION](../phase-2-core-etl/project-2.3-append-only-chicago-crime/EXPLANATION.md).

**Dataset:** Any event-log dataset (GitHub Events, or simulated from Chicago Crime) — append-heavy, re-delivered records.

---

## Framing questions to answer first

### The three idempotency techniques
- [ ] Implement all three on different slices and be able to say **when each fits**:
  - **Dedup-key upsert (MERGE)** — when?
  - **Record hashing** — when?
  - **Partition overwrite** — when?
- [ ] For your dataset, which slice suits which technique, and why?

### Record identity
- [ ] What fields define a record's identity (the hash inputs)? What volatile fields must you **exclude**?
- [ ] Could two genuinely different events collide on your identity fields? How do you prevent it?

### Prove it
- [ ] How will an **automated test** run a full load **twice** and assert row counts *and* content are identical?
- [ ] How will you **simulate at-least-once delivery** — feed the same batch **3 times** with timing differences — and prove the final state is correct?

### The audit log
- [ ] What columns does your **separate immutable audit-log** table need (timestamp, row count, success/failure)? Why must it be **append-only and never mutated**?

### The concept
- [ ] Write a paragraph: **why does "exactly-once processing" not require "exactly-once delivery"?** Use *your* pipeline as the worked example.

---

## Playbook requirements (self-check when done)
- [ ] All three idempotency techniques implemented on different slices; when-to-use documented
- [ ] Automated test: full load twice → identical row counts and content
- [ ] At-least-once simulated: same batch ×3 with timing differences → correct final state
- [ ] Separate immutable audit-log table (timestamp, row count, status), append-only
- [ ] One paragraph explaining exactly-once processing ≠ exactly-once delivery, using your pipeline
