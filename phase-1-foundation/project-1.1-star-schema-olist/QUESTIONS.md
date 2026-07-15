# Project 1.1 — Framing Questions (ask these BEFORE you build)

> **Step 0 of the learning loop.** Before reading any code, answer "what are we expecting from this dataset and what should the project produce?" These questions — *with answers* — set the frame. The answers point at the built code (`README.md` for decisions, `EXPLANATION.md` for line-by-line).

Dataset: **Olist Brazilian E-Commerce** (8 CSVs).

---

### Q1. What is this dataset — what does each file represent?
Eight related tables from a real e-commerce marketplace:
- `orders` — one row per order (status, purchase/delivery timestamps).
- `order_items` — one row per **item line** within an order (price, freight, product, seller).
- `customers`, `sellers`, `products` — the descriptive entities.
- `order_payments`, `order_reviews` — per-order payment and review facts.
- `geolocation` — zip → lat/long/city.

It arrives in **OLTP (normalized) shape**. Our job is to reshape it to **OLAP (dimensional) shape**.

### Q2. What is the grain — what will one fact row represent?
**One item within one order.** Decide this *before* writing DDL. An order with 3 items becomes 3 fact rows. Everything else (which measures are additive, whether payments can be joined) follows from this choice. Choosing the *lowest* useful grain means you can always roll up but never need to re-extract to drill down.

### Q3. What business questions should the model answer?
- Revenue by customer state? By product category? By month/quarter?
- Freight cost as a share of item price, by category?
- Weekend vs. weekday order value? Delivery time by state?
- Quarter-over-quarter growth? Value of cancelled orders?

If the model can't answer these with **one join hop** from fact to dimension, the design is wrong.

### Q4. What do we expect to be *wrong* / tricky in the data?
- **Missing product categories** (~2%) → need an "unknown member" so facts aren't dropped.
- **Structural nulls**: only *delivered* orders have a delivery timestamp — that null means "not applicable," not "missing."
- **One-to-many** order→items cardinality → the reason grain matters.
- **Two facts at different grains** (payments are order-grain, items are item-grain) → a fan-trap risk if naively joined.

### Q5. What's the target output/shape?
A **star schema**: one central `fact_order_items` surrounded by `dim_customer`, `dim_product`, `dim_seller`, `dim_date` — each with an integer **surrogate key**. Plus 10 analytical queries and validation gates.

### Q6. Key design decisions to reason through
| Decision | The question | How this project answered it |
|---|---|---|
| Grain | What is one fact row? | one order-item |
| Star vs snowflake | Normalize dimensions? | star — flat dims, cheap with columnar storage |
| Keys | Natural or surrogate PK? | surrogate (`ROW_NUMBER()`), natural kept for trace |
| Unknown members | How to survive late/missing dims? | key `-1` row + `COALESCE` |
| dim_date | Build or derive on the fly? | build from scratch — highest-leverage dim |
| Additivity | Which measures can you SUM? | price/freight additive; freight *ratio* is not |

### Q7. Gotchas to watch
- **Fan trap**: joining payments (order grain) onto items (item grain) multiplies payment values by item count. Keep them as separate facts.
- **Non-additive measures**: never average a ratio — recompute `SUM(freight)/SUM(price)` at every level.
- **Never** put descriptive text in the fact table; **never** build the fact before declaring the grain.

---

➡️ Now read [README.md](README.md) (decisions) and [EXPLANATION.md](EXPLANATION.md) (line-by-line). Then attempt **Assignment 1.1** using [assignments/assignment-1.1-global-superstore-QUESTIONS.md](../../assignments/assignment-1.1-global-superstore-QUESTIONS.md).
