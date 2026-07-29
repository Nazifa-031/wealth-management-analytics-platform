-- =====================================================================
-- Phase 4: Visualization — Databricks SQL (Lakeview) Dashboard Queries
-- =====================================================================
-- Each query below is meant to become ONE widget in a Lakeview dashboard.
-- Workflow per query: Databricks SQL Editor -> paste query -> Save as a
-- Query -> open/create a Lakeview Dashboard -> "Add visualization" ->
-- pick the saved query -> choose the chart type noted in the comment.
--
-- Organized into 5 dashboard pages:
--   A. Executive Summary
--   B. Client & Portfolio
--   C. Advisor Performance
--   D. Scheme & AMC
--   E. Revenue, SIP & Redemption
-- =====================================================================


-- =====================================================================
-- A. EXECUTIVE SUMMARY DASHBOARD
-- =====================================================================

-- A1. Counter widgets: total_clients, total_advisors, total_aum, total_investment,
--     total_redemption, total_revenue, active_sips, active_schemes, dashboard_date
-- Chart type: Counter (one per column) or a single Table widget for all KPIs at once
SELECT * FROM mart.executive_dashboard;

-- A2. AUM vs Investment vs Redemption (single-row comparison)
-- Chart type: Bar chart
SELECT 'Total AUM' AS metric, total_aum AS value FROM mart.executive_dashboard
UNION ALL
SELECT 'Total Investment', total_investment FROM mart.executive_dashboard
UNION ALL
SELECT 'Total Redemption', total_redemption FROM mart.executive_dashboard
UNION ALL
SELECT 'Total Revenue', total_revenue FROM mart.executive_dashboard;

-- A3. Client base health: active vs total schemes/sips
-- Chart type: Counter pair or bar chart
SELECT active_sips, active_schemes FROM mart.executive_dashboard;


-- =====================================================================
-- B. CLIENT & PORTFOLIO DASHBOARD
-- =====================================================================

-- B1. Top 10 clients by current portfolio value
-- Chart type: Bar chart (client_name vs current_value)
SELECT client_name, current_value
FROM mart.client_portfolio_summary
ORDER BY current_value DESC
LIMIT 10;

-- B2. Top 10 clients by gain % (best performing portfolios)
-- Chart type: Bar chart
SELECT client_name, gain_percent
FROM mart.client_portfolio_summary
WHERE total_investment > 0
ORDER BY gain_percent DESC
LIMIT 10;

-- B3. Bottom 10 clients by gain % (portfolios losing value — retention risk)
-- Chart type: Bar chart
SELECT client_name, gain_percent
FROM mart.client_portfolio_summary
WHERE total_investment > 0
ORDER BY gain_percent ASC
LIMIT 10;

-- B4. Gain % distribution across all clients
-- Chart type: Histogram
SELECT gain_percent FROM mart.client_portfolio_summary;

-- B5. Full client portfolio table (searchable/sortable in the dashboard)
-- Chart type: Table
SELECT client_id, client_name, advisor_name, total_investment, current_value,
       gain_loss, gain_percent, active_scheme_count, total_units, last_updated_date
FROM mart.client_portfolio_summary
ORDER BY current_value DESC;

-- B6. Clients segmented by number of active schemes (diversification view)
-- Chart type: Bar chart
SELECT active_scheme_count, COUNT(*) AS client_count
FROM mart.client_portfolio_summary
GROUP BY active_scheme_count
ORDER BY active_scheme_count;


-- =====================================================================
-- C. ADVISOR PERFORMANCE DASHBOARD
-- =====================================================================

-- C1. Top 10 advisors by total AUM managed
-- Chart type: Bar chart
SELECT advisor_name, total_aum
FROM mart.advisor_performance
ORDER BY total_aum DESC
LIMIT 10;

-- C2. Top 10 advisors by total revenue generated
-- Chart type: Bar chart
SELECT advisor_name, total_revenue
FROM mart.advisor_performance
ORDER BY total_revenue DESC
LIMIT 10;

-- C3. Advisor client load vs average client AUM (are big books high-value or high-volume?)
-- Chart type: Scatter plot (x = total_clients, y = average_client_aum)
SELECT advisor_name, total_clients, average_client_aum
FROM mart.advisor_performance;

-- C4. Active SIP count by advisor (who's driving recurring investment behavior)
-- Chart type: Bar chart
SELECT advisor_name, active_sip_count
FROM mart.advisor_performance
ORDER BY active_sip_count DESC
LIMIT 10;

-- C5. Full advisor performance table
-- Chart type: Table
SELECT advisor_id, advisor_name, total_clients, total_aum, total_commission,
       total_revenue, average_client_aum, active_sip_count, last_updated_date
FROM mart.advisor_performance
ORDER BY total_aum DESC;


-- =====================================================================
-- D. SCHEME & AMC DASHBOARD
-- =====================================================================

-- D1. Total AUM by category (Equity, Debt, Hybrid, etc.)
-- Chart type: Pie chart
SELECT category_name, SUM(total_aum) AS category_aum
FROM mart.scheme_performance
GROUP BY category_name
ORDER BY category_aum DESC;

-- D2. Top 10 schemes by AUM
-- Chart type: Bar chart
SELECT scheme_name, total_aum
FROM mart.scheme_performance
ORDER BY total_aum DESC
LIMIT 10;

-- D3. Top 10 schemes by average return (best performers)
-- Chart type: Bar chart
SELECT scheme_name, average_return
FROM mart.scheme_performance
ORDER BY average_return DESC
LIMIT 10;

-- D4. Bottom 10 schemes by average return (worst performers — review candidates)
-- Chart type: Bar chart
SELECT scheme_name, average_return
FROM mart.scheme_performance
ORDER BY average_return ASC
LIMIT 10;

-- D5. AUM by AMC
-- Chart type: Bar chart
SELECT amc_name, total_aum, investor_count, scheme_count, average_return
FROM mart.amc_business
ORDER BY total_aum DESC;

-- D6. Investor count vs scheme count by AMC (breadth vs depth)
-- Chart type: Scatter plot
SELECT amc_name, scheme_count, investor_count
FROM mart.amc_business;

-- D7. Full scheme performance table
-- Chart type: Table
SELECT scheme_id, scheme_name, amc_name, category_name, investor_count,
       total_aum, average_return, units_held, latest_nav, last_updated_date
FROM mart.scheme_performance
ORDER BY total_aum DESC;


-- =====================================================================
-- E. REVENUE, SIP & REDEMPTION DASHBOARD
-- =====================================================================

-- E1. Monthly revenue trend (brokerage vs trail)
-- Chart type: Stacked bar chart or line chart (x = year/month)
SELECT year, month, SUM(brokerage_amount) AS brokerage_amount, SUM(trail_commission) AS trail_commission,
       SUM(total_revenue) AS total_revenue
FROM mart.revenue
GROUP BY year, month
ORDER BY year, month;

-- E2. Top 10 advisors by total revenue (all months combined)
-- Chart type: Bar chart
SELECT advisor_name, SUM(total_revenue) AS total_revenue
FROM mart.revenue
GROUP BY advisor_name
ORDER BY total_revenue DESC
LIMIT 10;

-- E3. Top 10 schemes by total SIP inflow
-- Chart type: Bar chart
SELECT scheme_name, SUM(total_sip_amount) AS total_sip_amount, SUM(installment_count) AS installment_count
FROM mart.sip_analytics
GROUP BY scheme_name
ORDER BY total_sip_amount DESC
LIMIT 10;

-- E4. SIP current value vs invested amount, by client (top 15 by current value)
-- Chart type: Bar chart (grouped: total_sip_amount vs current_value)
SELECT client_name, SUM(total_sip_amount) AS invested, SUM(current_value) AS current_value
FROM mart.sip_analytics
GROUP BY client_name
ORDER BY current_value DESC
LIMIT 15;

-- E5. Monthly redemption trend
-- Chart type: Line chart
SELECT redemption_year, redemption_month,
       SUM(redeemed_amount) AS total_redeemed, SUM(redemption_count) AS redemption_events
FROM mart.redemption_analytics
GROUP BY redemption_year, redemption_month
ORDER BY redemption_year, redemption_month;

-- E6. Top 10 schemes by redemption amount (money leaving — attrition watch)
-- Chart type: Bar chart
SELECT scheme_name, SUM(redeemed_amount) AS total_redeemed
FROM mart.redemption_analytics
GROUP BY scheme_name
ORDER BY total_redeemed DESC
LIMIT 10;

-- E7. Net flow by month (SIP inflow vs redemption outflow) — requires a join across marts
-- Chart type: Line chart with two series
WITH sip_by_month AS (
    SELECT t.year, t.month, SUM(f.installment_amount) AS sip_inflow
    FROM warehouse.fact_sip_installments f
    JOIN warehouse.dim_time t ON f.date_key = t.date_key
    GROUP BY t.year, t.month
),
redemption_by_month AS (
    SELECT redemption_year AS year, redemption_month AS month, SUM(redeemed_amount) AS redemption_outflow
    FROM mart.redemption_analytics
    GROUP BY redemption_year, redemption_month
)
SELECT COALESCE(s.year, r.year) AS year, COALESCE(s.month, r.month) AS month,
       COALESCE(s.sip_inflow, 0) AS sip_inflow, COALESCE(r.redemption_outflow, 0) AS redemption_outflow,
       COALESCE(s.sip_inflow, 0) - COALESCE(r.redemption_outflow, 0) AS net_flow
FROM sip_by_month s
FULL OUTER JOIN redemption_by_month r ON s.year = r.year AND s.month = r.month
ORDER BY year, month;
