-- ============================================================================
-- Guided Project 1.1 — 10 analytical queries against the star schema
-- Every query is exactly ONE join hop from fact to the dimensions it needs.
-- Run with: python run_queries.py
-- ============================================================================

-- Q1: Total revenue by customer state (top 10)
-- name: revenue_by_state
SELECT
    dc.customer_state,
    ROUND(SUM(f.price), 2)        AS revenue,
    COUNT(DISTINCT f.order_id)    AS orders
FROM fact_order_items f
JOIN dim_customer dc ON f.customer_key = dc.customer_key
GROUP BY dc.customer_state
ORDER BY revenue DESC
LIMIT 10;

-- Q2: Freight cost as a share of item price, by product category
-- freight_ratio is NON-ADDITIVE: it must be recomputed from the two
-- additive measures at every aggregation level, never averaged or summed.
-- name: freight_ratio_by_category
SELECT
    dp.product_category,
    ROUND(SUM(f.freight_value) / SUM(f.price), 3) AS freight_ratio,
    COUNT(*)                                      AS items
FROM fact_order_items f
JOIN dim_product dp ON f.product_key = dp.product_key
GROUP BY dp.product_category
HAVING COUNT(*) >= 20
ORDER BY freight_ratio DESC
LIMIT 10;

-- Q3: Monthly revenue trend
-- name: monthly_revenue
SELECT
    dd.year,
    dd.month,
    ROUND(SUM(f.price), 2) AS revenue
FROM fact_order_items f
JOIN dim_date dd ON f.order_date_key = dd.date_key
GROUP BY dd.year, dd.month
ORDER BY dd.year, dd.month;

-- Q4: Weekend vs weekday purchasing behaviour
-- name: weekend_vs_weekday
SELECT
    dd.is_weekend,
    COUNT(DISTINCT f.order_id)              AS orders,
    ROUND(AVG(f.total_item_value), 2)       AS avg_item_value
FROM fact_order_items f
JOIN dim_date dd ON f.order_date_key = dd.date_key
GROUP BY dd.is_weekend;

-- Q5: Top 10 product categories by revenue
-- name: top_categories
SELECT
    dp.product_category,
    ROUND(SUM(f.price), 2) AS revenue
FROM fact_order_items f
JOIN dim_product dp ON f.product_key = dp.product_key
GROUP BY dp.product_category
ORDER BY revenue DESC
LIMIT 10;

-- Q6: Average delivery time (days) by customer state
-- delivery_days is NULL for undelivered orders; AVG ignores nulls, which is
-- exactly what we want here (structural null = "not applicable yet").
-- name: delivery_days_by_state
SELECT
    dc.customer_state,
    ROUND(AVG(f.delivery_days), 1) AS avg_delivery_days,
    COUNT(f.delivery_days)         AS delivered_items
FROM fact_order_items f
JOIN dim_customer dc ON f.customer_key = dc.customer_key
GROUP BY dc.customer_state
ORDER BY avg_delivery_days DESC;

-- Q7: Seller states ranked by revenue — do sellers cluster like customers?
-- name: seller_state_revenue
SELECT
    ds.seller_state,
    ROUND(SUM(f.price), 2)      AS revenue,
    COUNT(DISTINCT ds.seller_natural_key) AS active_sellers
FROM fact_order_items f
JOIN dim_seller ds ON f.seller_key = ds.seller_key
WHERE ds.seller_key <> -1
GROUP BY ds.seller_state
ORDER BY revenue DESC;

-- Q8: Order-size distribution (items per order) with revenue contribution
-- Aggregating the fact to order grain FIRST, then summarizing — the safe
-- way to answer order-level questions from an item-grain fact.
-- name: order_size_distribution
WITH order_grain AS (
    SELECT
        order_id,
        COUNT(*)   AS items_in_order,
        SUM(price) AS order_revenue
    FROM fact_order_items
    GROUP BY order_id
)
SELECT
    items_in_order,
    COUNT(*)                       AS orders,
    ROUND(SUM(order_revenue), 2)   AS revenue
FROM order_grain
GROUP BY items_in_order
ORDER BY items_in_order;

-- Q9: Quarterly revenue with quarter-over-quarter growth (window function)
-- name: qoq_growth
WITH quarterly AS (
    SELECT
        dd.year,
        dd.quarter,
        SUM(f.price) AS revenue
    FROM fact_order_items f
    JOIN dim_date dd ON f.order_date_key = dd.date_key
    GROUP BY dd.year, dd.quarter
)
SELECT
    year,
    quarter,
    ROUND(revenue, 2) AS revenue,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY year, quarter))
          / LAG(revenue) OVER (ORDER BY year, quarter), 1) AS qoq_growth_pct
FROM quarterly
ORDER BY year, quarter;

-- Q10: Cancelled-order value by month — how much revenue is being lost?
-- name: cancelled_value_by_month
SELECT
    dd.year,
    dd.month,
    ROUND(SUM(f.total_item_value), 2) AS cancelled_value,
    COUNT(DISTINCT f.order_id)        AS cancelled_orders
FROM fact_order_items f
JOIN dim_date dd ON f.order_date_key = dd.date_key
WHERE f.order_status = 'canceled'
GROUP BY dd.year, dd.month
ORDER BY dd.year, dd.month;
