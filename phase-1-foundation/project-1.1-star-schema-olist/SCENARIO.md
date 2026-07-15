# 🎫 Scenario — Project 1.1: Star Schema for an E-Commerce Marketplace

> Read this like a ticket handed to you at work. Everything you must do is in the question. Try to answer/plan it yourself **before** opening [BUILD_GUIDE.md](BUILD_GUIDE.md).

## The situation

You've just joined **Olist**, a Brazilian e-commerce marketplace, as a Data Engineer. The analytics team is drowning: every business question ("revenue by state?", "which categories have the worst freight costs?", "are deliveries slower in the north?") requires them to hand-join **8 normalized OLTP CSVs** (orders, order items, customers, sellers, products, payments, reviews, geolocation), and every analyst does it differently — so no two dashboards agree.

Your tech lead assigns you this ticket:

## The ticket

> **Build our first analytical star schema in DuckDB so any analyst can answer revenue/delivery/category questions with a single join.**

## 📊 Business questions the stakeholders need answered

Your schema exists to serve these asks — design for them, then prove them with your 10 queries:

| Stakeholder | Business question |
|---|---|
| **CFO** | Which states generate the most revenue, and what's the month-over-month and quarter-over-quarter growth trend? |
| **CFO** | How much revenue are we losing to cancelled orders each month? |
| **Category manager** | Which product categories drive revenue — and which have freight costs eating an outsized share of the item price? |
| **Logistics lead** | What's the average delivery time per state, and where are we slowest? |
| **Marketing** | Do customers buy differently on weekends vs weekdays (order counts, basket value)? |
| **Marketplace ops** | Which seller states host the most active, highest-revenue sellers? |
| **Marketplace ops** | How are orders distributed by size (items per order), and how much revenue comes from multi-item orders? |

If any of these needs more than **one join hop** from your fact table, your model isn't done.

## What you must work out (and your implementation must prove)

1. **Profiling:** What does each of the 8 files contain, what does one row of each represent, and which columns link them? Is `customer_id` actually unique? How many items does a typical order have (what's the real cardinality)? How many products have no category?
2. **Grain:** What will **one row of your fact table** represent — an order, or an item within an order? Why is the lower grain safer? Where will you declare it?
3. **Dimensions:** Which descriptive entities deserve their own dimension tables (customer? product? seller? date?), and why is each not just folded into the fact?
4. **Keys:** Why must every dimension get an integer **surrogate key** instead of using Olist's 32-char hex IDs? Where do the natural keys go?
5. **dim_date:** Why must you build a date dimension from scratch (one row per calendar day, with year/quarter/month/day-of-week/is_weekend), and why is it the highest-leverage table you'll build?
6. **The unknown member:** ~2% of products have a NULL category, and a fact might reference a product you've never seen. How do you guarantee such facts are **never silently dropped** by a join? (Hint: surrogate key `-1`.)
7. **Measures:** Which measures (price, freight) are **additive**? Why is the freight *ratio* non-additive, and how must it be computed at every aggregation level?
8. **The fan trap:** Payments are order-grain; your fact is item-grain. What goes wrong if you join payments onto the fact, and what do you do instead?
9. **Validation:** After the build, how do you *prove* no join fanned out or dropped rows, and that every fact points at a real dimension row?
10. **Queries:** Write **10 analytical queries** — each exactly **one join hop** from fact to dimension — covering revenue by state, freight ratio by category, monthly trend, weekend vs weekday, delivery days by state, QoQ growth, and cancelled-order value.

## Deliverables (definition of done)

- [ ] ER diagram of the star schema
- [ ] Python loader script: raw CSVs → profiled → dims → fact → validated, in DuckDB
- [ ] 10 analytical queries, all one join hop
- [ ] README documenting grain, star-vs-snowflake choice, surrogate keys, unknown member, and one fan-trap scenario

## Data

- **To test:** `python generate_sample_data.py` creates synthetic CSVs with the exact Olist schema (including the dirt above).
- **To practice for real:** download [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) from Kaggle and drop the CSVs into `data/raw/` — the pipeline runs unchanged.

➡️ Ready to build? Follow [BUILD_GUIDE.md](BUILD_GUIDE.md) step by step. Stuck on a step? The finished reference is in this folder, explained line-by-line in [EXPLANATION.md](EXPLANATION.md).
