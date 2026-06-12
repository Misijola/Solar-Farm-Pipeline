-- =============================================================================
-- queries_solar.sql
-- Solar Farm Energy Production & Consumption — SQL Analysis
-- Author: Marvellous Isijola | EMIMO
-- Project: Hagital Bootcamp — Group 2 (Solo)
-- =============================================================================


-- ─── 1. BASIC AGGREGATIONS ───────────────────────────────────────────────────

-- Q1: Total energy generated and consumed per panel (across all 30 days)
SELECT
    panel_id,
    ROUND(SUM(power_generated_kw)::numeric, 2) AS total_generated_kwh,
    ROUND(SUM(consumption_kw)::numeric, 2)     AS total_consumed_kwh,
    ROUND(SUM(net_energy_kw)::numeric, 2)      AS net_energy_kwh
FROM solar_readings
GROUP BY panel_id
ORDER BY total_generated_kwh DESC;


-- Q2: Average efficiency per panel
SELECT
    panel_id,
    ROUND(AVG(efficiency_pct)::numeric, 2) AS avg_efficiency_pct,
    ROUND(MAX(efficiency_pct)::numeric, 2) AS max_efficiency_pct,
    ROUND(MIN(efficiency_pct)::numeric, 2) AS min_efficiency_pct
FROM solar_readings
WHERE irradiance_w_m2 > 0   -- exclude night hours where efficiency is 0
GROUP BY panel_id
ORDER BY avg_efficiency_pct DESC;


-- Q3: Daily total generation across all panels
SELECT
    date,
    ROUND(SUM(total_generated_kwh)::numeric, 2) AS daily_total_kwh,
    ROUND(AVG(avg_efficiency_pct)::numeric, 2)  AS avg_daily_efficiency
FROM solar_daily
GROUP BY date
ORDER BY date;


-- ─── 2. PEAK HOURS ANALYSIS ──────────────────────────────────────────────────

-- Q4: Average generation by hour of day (to identify actual peak hours)
SELECT
    hour,
    ROUND(AVG(power_generated_kw)::numeric, 4) AS avg_generation_kw,
    ROUND(AVG(consumption_kw)::numeric, 4)     AS avg_consumption_kw,
    COUNT(*) AS reading_count
FROM solar_readings
GROUP BY hour
ORDER BY hour;


-- Q5: Compare peak vs off-peak generation
SELECT
    CASE WHEN peak_hour_flag = 1 THEN 'Peak (10am-2pm)'
         ELSE 'Off-Peak'
    END AS hour_category,
    COUNT(*)                                            AS reading_count,
    ROUND(AVG(power_generated_kw)::numeric, 4)         AS avg_generation_kw,
    ROUND(AVG(efficiency_pct)::numeric, 2)             AS avg_efficiency_pct
FROM solar_readings
WHERE irradiance_w_m2 > 0
GROUP BY peak_hour_flag
ORDER BY peak_hour_flag DESC;


-- ─── 3. BATTERY ANALYSIS ─────────────────────────────────────────────────────

-- Q6: Battery status breakdown per panel
SELECT
    panel_id,
    battery_status,
    COUNT(*) AS hours_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY panel_id), 2) AS pct_of_time
FROM solar_readings
GROUP BY panel_id, battery_status
ORDER BY panel_id, hours_count DESC;


-- Q7: Average battery SOC by hour of day
SELECT
    hour,
    ROUND(AVG(battery_soc_kwh)::numeric, 4) AS avg_soc_kwh
FROM solar_readings
GROUP BY hour
ORDER BY hour;


-- ─── 4. WINDOW FUNCTIONS ─────────────────────────────────────────────────────

-- Q8: Running total of energy generated per panel over time (cumulative kWh)
SELECT
    timestamp,
    panel_id,
    power_generated_kw,
    ROUND(
        SUM(power_generated_kw) OVER (
            PARTITION BY panel_id
            ORDER BY timestamp
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )::numeric, 4
    ) AS cumulative_generated_kwh
FROM solar_readings
ORDER BY panel_id, timestamp
LIMIT 72;   -- show first 3 days per panel


-- Q9: 3-hour rolling average of generation per panel (smooths out noise)
SELECT
    timestamp,
    panel_id,
    power_generated_kw,
    ROUND(
        AVG(power_generated_kw) OVER (
            PARTITION BY panel_id
            ORDER BY timestamp
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW  -- current row + 2 previous
        )::numeric, 4
    ) AS rolling_3hr_avg_kw
FROM solar_readings
ORDER BY panel_id, timestamp
LIMIT 72;


-- Q10: Rank panels by daily generation (which panel performed best each day?)
SELECT
    date,
    panel_id,
    ROUND(total_generated_kwh::numeric, 2) AS generated_kwh,
    RANK() OVER (
        PARTITION BY date
        ORDER BY total_generated_kwh DESC
    ) AS daily_rank
FROM solar_daily
ORDER BY date, daily_rank;


-- ─── 5. JOINS ────────────────────────────────────────────────────────────────

-- Q11: Join hourly readings with daily summary to show how each hour
--      contributes to that day's total for each panel
SELECT
    r.timestamp,
    r.panel_id,
    r.power_generated_kw,
    d.total_generated_kwh AS day_total_kwh,
    ROUND(
        (r.power_generated_kw / NULLIF(d.total_generated_kwh, 0) * 100)::numeric, 2
    ) AS pct_of_day_total
FROM solar_readings r
JOIN solar_daily d
    ON r.date = d.date AND r.panel_id = d.panel_id
WHERE r.date = '2025-01-05'   -- example: Jan 5th
ORDER BY r.panel_id, r.timestamp;


-- ─── 6. GRAFANA-READY QUERIES ─────────────────────────────────────────────────
-- These are formatted for direct use in Grafana panel queries.

-- Grafana Panel 1: Solar generation vs consumption over time (time-series)
-- Use this in Grafana with Time column = timestamp
SELECT
    timestamp AS time,
    SUM(power_generated_kw) AS total_generated_kw,
    SUM(consumption_kw)     AS total_consumed_kw
FROM solar_readings
GROUP BY timestamp
ORDER BY timestamp;


-- Grafana Panel 2: Efficiency % over time per panel
SELECT
    timestamp AS time,
    panel_id,
    efficiency_pct
FROM solar_readings
WHERE irradiance_w_m2 > 0
ORDER BY timestamp;


-- Grafana Panel 3: Battery SOC over time (charge/discharge cycles)
SELECT
    timestamp AS time,
    panel_id,
    battery_soc_kwh,
    battery_status
FROM solar_readings
ORDER BY timestamp;


-- Grafana Panel 4: Daily generation bar chart
SELECT
    date AS time,
    panel_id,
    total_generated_kwh
FROM solar_daily
ORDER BY date;


-- Grafana Panel 5: Average generation by hour (heatmap / bar)
SELECT
    hour,
    ROUND(AVG(power_generated_kw)::numeric, 4) AS avg_kw
FROM solar_readings
GROUP BY hour
ORDER BY hour;
