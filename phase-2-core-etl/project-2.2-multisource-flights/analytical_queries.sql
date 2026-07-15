-- ============================================================================
-- Project 2.2 — 5 analytical queries against fact_flights (SQLite).
-- Run with: python run_queries.py
-- Note the null handling: delay sentinel -999 is EXCLUDED from averages so it
-- never pollutes a metric.
-- ============================================================================

-- Q1: On-time performance by airline (avg departure delay, excluding cancelled)
-- name: delay_by_airline
SELECT
    airline_name,
    COUNT(*)                                   AS flights,
    ROUND(AVG(departure_delay_min), 1)         AS avg_dep_delay,
    SUM(is_cancelled)                          AS cancellations
FROM fact_flights
WHERE departure_delay_min <> -999              -- exclude structural sentinel
GROUP BY airline_name
ORDER BY avg_dep_delay DESC;

-- Q2: Busiest origin airports
-- name: busiest_origins
SELECT
    origin, origin_city, origin_state,
    COUNT(*) AS departures
FROM fact_flights
GROUP BY origin, origin_city, origin_state
ORDER BY departures DESC
LIMIT 10;

-- Q3: Cancellation rate by airline
-- name: cancellation_rate
SELECT
    airline_name,
    COUNT(*)                                              AS total_flights,
    SUM(is_cancelled)                                     AS cancelled,
    ROUND(100.0 * SUM(is_cancelled) / COUNT(*), 2)        AS cancel_rate_pct
FROM fact_flights
GROUP BY airline_name
ORDER BY cancel_rate_pct DESC;

-- Q4: Data-quality view — how many rows have unmatched dimension keys?
-- This is the JOIN-INDUCED null surfaced as a metric, not hidden.
-- name: coverage_gaps
SELECT
    SUM(airline_missing) AS unmatched_airline,
    SUM(origin_missing)  AS unmatched_origin,
    SUM(dest_missing)    AS unmatched_destination,
    COUNT(*)             AS total_rows
FROM fact_flights;

-- Q5: Routes with worst schedule adherence (actual vs scheduled elapsed)
-- name: worst_schedule_adherence
SELECT
    origin || '->' || destination           AS route,
    COUNT(*)                                 AS flights,
    ROUND(AVG(elapsed_variance_min), 1)      AS avg_variance_min
FROM fact_flights
WHERE elapsed_variance_min <> -999           -- exclude cancelled
GROUP BY route
HAVING COUNT(*) >= 20
ORDER BY avg_variance_min DESC
LIMIT 10;
