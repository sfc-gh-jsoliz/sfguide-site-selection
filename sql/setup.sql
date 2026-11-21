-- ============================================================================
-- Geographic Expansion & Site Selection: setup.sql (synthetic, no listing needed)
-- ----------------------------------------------------------------------------
-- A payments processor / acquirer decides where to grow next. Every metro x
-- merchant-category cell is ranked by WHITE-SPACE opportunity: where category
-- demand is growing but the processor's merchant coverage (penetration) is thin.
--   opportunity_score = max(category demand growth %, 0) x (1 - penetration)
-- Here metro geography, coverage AND category demand are synthetic.
-- sql/setup_census.sql swaps the demand side for REAL US Census Advance Retail
-- Sales from the free Snowflake Marketplace "Financial Data Package".
--
-- Synthetic data and illustrative logic only. Not production or investment
-- advice. Run top to bottom in a Snowsight SQL worksheet; no edits needed.
-- Takes under 1 minute on an XSMALL warehouse.
--
-- Requires: ACCOUNTADMIN (or USERADMIN + SECURITYADMIN) and SYSADMIN, and Cortex
-- AI (AI_COMPLETE, Cortex Agents, Cortex Analyst) in your region or with
-- cross-region inference enabled.
--
-- Creates (sql/cleanup.sql drops all of it); changes nothing that already exists:
--   role       SNOWPACK_SITE_SELECTION_ROLE  least-privilege role for setup + app
--   warehouse  SNOWPACK_SITE_SELECTION_WH    XSMALL, AUTO_SUSPEND = 60
--   database   SNOWPACK_SITE_SELECTION       schema CORE (prefix SITE_SELECTION_):
--     MERCHANT_CATEGORY, METRO (dims), CATEGORY_DEMAND (24 months), COVERAGE
--     (60 metro x category cells), BENCHMARK (wide view), DATA_SOURCE_INFO,
--     SV (semantic view), REPORTS, AGENT (Cortex Agent),
--     stage SITE_SELECTION_APP_STAGE (for the Streamlit app files)
--
-- Determinism: every random value is UNIFORM(lo, hi, HASH(<row key>, <salt>)),
-- so re-running gives identical rows (checked with HASH_AGG; see data/README.md).
-- ============================================================================

-- 0. Least-privilege role ------------------------------------------------------
USE ROLE ACCOUNTADMIN;
CREATE ROLE IF NOT EXISTS SNOWPACK_SITE_SELECTION_ROLE
  COMMENT = 'Geographic Expansion & Site Selection example: owns only objects in SNOWPACK_SITE_SELECTION';
GRANT ROLE SNOWPACK_SITE_SELECTION_ROLE TO ROLE SYSADMIN;
SET my_user = CURRENT_USER();
GRANT ROLE SNOWPACK_SITE_SELECTION_ROLE TO USER IDENTIFIER($my_user);
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE SNOWPACK_SITE_SELECTION_ROLE; -- AI_COMPLETE, Agents, Analyst

-- 1. Warehouse, database, schema (SYSADMIN) with schema-scoped grants ----------
USE ROLE SYSADMIN;
CREATE WAREHOUSE IF NOT EXISTS SNOWPACK_SITE_SELECTION_WH
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Geographic Expansion & Site Selection example';
CREATE DATABASE IF NOT EXISTS SNOWPACK_SITE_SELECTION COMMENT = 'Geographic Expansion & Site Selection example (synthetic data)';
CREATE SCHEMA IF NOT EXISTS SNOWPACK_SITE_SELECTION.CORE
  COMMENT = 'Geographic Expansion & Site Selection: metro x category white-space / expansion benchmarking';
GRANT USAGE, OPERATE ON WAREHOUSE SNOWPACK_SITE_SELECTION_WH TO ROLE SNOWPACK_SITE_SELECTION_ROLE;
GRANT USAGE ON DATABASE SNOWPACK_SITE_SELECTION TO ROLE SNOWPACK_SITE_SELECTION_ROLE;
GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE SEMANTIC VIEW, CREATE AGENT, CREATE STAGE, CREATE STREAMLIT
  ON SCHEMA SNOWPACK_SITE_SELECTION.CORE TO ROLE SNOWPACK_SITE_SELECTION_ROLE;

-- Everything below runs as the pack role, so it owns only what it creates.
USE ROLE SNOWPACK_SITE_SELECTION_ROLE;
USE WAREHOUSE SNOWPACK_SITE_SELECTION_WH;
USE SCHEMA SNOWPACK_SITE_SELECTION.CORE;

-- Type-switch safety: CATEGORY_DEMAND is a TABLE here and a VIEW in setup_census.sql.
-- DROP VIEW fails on a table (and vice versa), so try both quietly.
EXECUTE IMMEDIATE $$
BEGIN
  BEGIN DROP VIEW IF EXISTS SITE_SELECTION_CATEGORY_DEMAND; EXCEPTION WHEN OTHER THEN NULL; END;
  BEGIN DROP TABLE IF EXISTS SITE_SELECTION_CATEGORY_DEMAND; EXCEPTION WHEN OTHER THEN NULL; END;
END;
$$;

-- 2. Category dimension: MCC-aligned merchant categories mapped to Census codes --
CREATE OR REPLACE TABLE SITE_SELECTION_MERCHANT_CATEGORY (
  category_code STRING, category_name STRING, mcc STRING, census_variable STRING
);
INSERT INTO SITE_SELECTION_MERCHANT_CATEGORY VALUES
  ('RESTAURANTS', 'Restaurants & Food Service',   '5812', 'ADV_722SM_SA'),
  ('APPAREL',     'Clothing & Accessories',       '5651', 'ADV_448SM_SA'),
  ('ELECTRONICS', 'Electronics & Appliances',     '5732', 'ADV_443SM_SA'),
  ('GROCERY',     'Food & Beverage Stores',       '5411', 'ADV_445SM_SA'),
  ('FURNITURE',   'Furniture & Home Furnishings', '5712', 'ADV_442SM_SA'),
  ('HEALTH',      'Health & Personal Care',       '5912', 'ADV_446SM_SA');

-- 3. Metro geography: SYNTHETIC sizing (population / income / business counts are
--    illustrative, not Census figures). Latitude/longitude are the public city
--    centres, used only to place metros on the app's map.
CREATE OR REPLACE TABLE SITE_SELECTION_METRO (
  metro_id STRING, metro_name STRING, state STRING, region STRING,
  population NUMBER, median_hh_income NUMBER, est_business_count NUMBER,
  latitude FLOAT, longitude FLOAT
) COMMENT = 'SYNTHETIC metro sizing (population/income/business counts illustrative); lat/lon are city centres for the map.';
INSERT INTO SITE_SELECTION_METRO VALUES
  ('M01', 'New York-Newark', 'NY', 'Northeast', 8800000, 76000, 210000, 40.71,  -74.01),
  ('M02', 'Los Angeles',     'CA', 'West',      3900000, 69000, 145000, 34.05, -118.24),
  ('M03', 'Chicago',         'IL', 'Midwest',   2700000, 65000,  98000, 41.88,  -87.63),
  ('M04', 'Houston',         'TX', 'South',     2300000, 58000,  82000, 29.76,  -95.37),
  ('M05', 'Phoenix',         'AZ', 'West',      1700000, 64000,  61000, 33.45, -112.07),
  ('M06', 'Philadelphia',    'PA', 'Northeast', 1600000, 52000,  57000, 39.95,  -75.17),
  ('M07', 'Dallas',          'TX', 'South',     1340000, 60000,  54000, 32.78,  -96.80),
  ('M08', 'Atlanta',         'GA', 'South',      500000, 67000,  41000, 33.75,  -84.39),
  ('M09', 'Miami',           'FL', 'South',      470000, 47000,  38000, 25.76,  -80.19),
  ('M10', 'Denver',          'CO', 'West',       715000, 78000,  44000, 39.74, -104.99);

-- Per-category drivers (fixed):
--   base_mkt_musd       national demand magnitude ($M) for the synthetic demand series
--   mkt_g               monthly demand growth (Furniture is flat: planted story 3)
--   holiday_lift        extra demand in Nov and Dec (Apparel, Electronics)
--   base_penetration    processor's typical share of a metro's category market
--   base_mkt_per_capita $ of category market volume per resident (metro sizing)
CREATE OR REPLACE TEMP TABLE SITE_SELECTION_DRIVERS AS
SELECT * FROM VALUES
  ('RESTAURANTS', 95000, 0.0040, 0.00, 0.18, 1800),
  ('APPAREL',     26000, 0.0030, 0.09, 0.12,  900),
  ('ELECTRONICS',  8000, 0.0020, 0.14, 0.09,  600),
  ('GROCERY',     85000, 0.0045, 0.00, 0.22, 2600),
  ('FURNITURE',   11000, 0.0000, 0.00, 0.10,  500),
  ('HEALTH',      38000, 0.0030, 0.00, 0.15, 1100)
  AS d(category_code, base_mkt_musd, mkt_g, holiday_lift, base_penetration, base_mkt_per_capita);

-- Planted coverage overrides (stories 1, 2 and 4 in data/README.md)
CREATE OR REPLACE TEMP TABLE SITE_SELECTION_PLANTED AS
SELECT * FROM VALUES
  ('M04', 'GROCERY',     0.08),   -- Houston grocery: barely covered in the fastest-growing category
  ('M05', 'RESTAURANTS', 0.06),   -- Phoenix restaurants: second white-space target
  ('M03', 'GROCERY',     0.46)    -- Chicago grocery: already saturated
  AS p(metro_id, category_code, penetration_pct);

-- 4. Category demand: SYNTHETIC national retail-sales proxy, 24 month-ends to
--    30 Jun 2026. Linear growth, a holiday lift in Nov/Dec for gift categories,
--    and +/-0.5% month noise (never on the first or last month, so growth % is exact).
CREATE OR REPLACE TABLE SITE_SELECTION_CATEGORY_DEMAND
  COMMENT = 'SYNTHETIC category demand (national retail-sales proxy by month). sql/setup_census.sql replaces this with REAL US Census Advance Retail Sales.'
AS
WITH months AS (
  SELECT LAST_DAY(DATEADD(month, SEQ4(), '2024-07-01'::date)) AS month_end, SEQ4() AS m_idx
  FROM TABLE(GENERATOR(ROWCOUNT => 24))
)
SELECT c.category_code, c.category_name, m.month_end,
       ROUND(d.base_mkt_musd * 1e6 * (1 + d.mkt_g * m.m_idx)
             * (1 + IFF(MONTH(m.month_end) IN (11, 12), d.holiday_lift, 0))
             * (1 + IFF(m.m_idx IN (0, 23), 0, UNIFORM(-50, 50, HASH(c.category_code, m.month_end, 11)) / 10000.0)), 0)
         AS market_sales_usd
FROM SITE_SELECTION_MERCHANT_CATEGORY c
JOIN SITE_SELECTION_DRIVERS d ON d.category_code = c.category_code
CROSS JOIN months m;

-- 5. Coverage: SYNTHETIC processor coverage per metro x category -------------------
--    penetration = category base +/- 3 points (hash-seeded), then the planted overrides.
CREATE OR REPLACE TABLE SITE_SELECTION_COVERAGE
  COMMENT = 'SYNTHETIC: this processor''s merchant coverage by metro and category (penetration, processed vs estimated market volume).'
AS
WITH base AS (
  SELECT mt.metro_id, c.category_code, c.category_name,
         ROUND(mt.population * d.base_mkt_per_capita, 0) AS est_market_volume_usd,
         COALESCE(p.penetration_pct,
                  ROUND(LEAST(0.95, GREATEST(0.02, d.base_penetration + UNIFORM(-30, 30, HASH(mt.metro_id, c.category_code, 21)) / 1000.0)), 4))
           AS penetration_pct
  FROM SITE_SELECTION_METRO mt
  CROSS JOIN SITE_SELECTION_MERCHANT_CATEGORY c
  JOIN SITE_SELECTION_DRIVERS d ON d.category_code = c.category_code
  LEFT JOIN SITE_SELECTION_PLANTED p ON p.metro_id = mt.metro_id AND p.category_code = c.category_code
)
SELECT metro_id, category_code AS category, category_name,
       GREATEST(1, ROUND(est_market_volume_usd * penetration_pct / 2500000.0, 0)) AS current_merchant_count,
       ROUND(est_market_volume_usd * penetration_pct, 0) AS processed_volume_usd,
       est_market_volume_usd, penetration_pct
FROM base;

-- 6. Benchmark view: ONE wide, pre-joined grain (metro x category) ---------------
--    Demand is reduced to the category grain (first and latest of the last 24
--    months) before the join, so coverage rows never fan out.
CREATE OR REPLACE VIEW SITE_SELECTION_BENCHMARK
  COMMENT = 'Metro x merchant-category coverage vs category demand: penetration, white-space volume, opportunity score. Grain = (metro_id, category_code).'
AS
WITH win AS (
  SELECT category_code, category_name, month_end, market_sales_usd
  FROM SITE_SELECTION_CATEGORY_DEMAND
  QUALIFY month_end > DATEADD(month, -24, MAX(month_end) OVER (PARTITION BY category_code))
), demand AS (
  SELECT category_code,
         MAX_BY(market_sales_usd, month_end) AS latest_demand_usd,
         MIN_BY(market_sales_usd, month_end) AS earliest_demand_usd
  FROM win GROUP BY category_code
)
SELECT cov.metro_id, mt.metro_name, mt.state, mt.region, mt.latitude, mt.longitude,
       mt.population, mt.median_hh_income, mt.est_business_count,
       cov.category AS category_code, cov.category_name,
       cov.current_merchant_count, cov.processed_volume_usd, cov.est_market_volume_usd,
       cov.penetration_pct,
       (cov.est_market_volume_usd - cov.processed_volume_usd) AS white_space_volume,
       d.latest_demand_usd AS category_demand_index,
       ROUND((d.latest_demand_usd - d.earliest_demand_usd) / NULLIF(d.earliest_demand_usd, 0) * 100, 2) AS category_demand_growth_pct,
       ROUND(GREATEST((d.latest_demand_usd - d.earliest_demand_usd) / NULLIF(d.earliest_demand_usd, 0) * 100, 0)
             * (1 - cov.penetration_pct), 2) AS opportunity_score,
       ROUND(cov.current_merchant_count / NULLIF(mt.population, 0) * 100000, 2) AS merchants_per_100k
FROM SITE_SELECTION_COVERAGE cov
JOIN SITE_SELECTION_METRO mt ON mt.metro_id = cov.metro_id
JOIN demand d ON d.category_code = cov.category;

-- 7. Data-source marker --------------------------------------------------------
CREATE OR REPLACE VIEW SITE_SELECTION_DATA_SOURCE_INFO AS
SELECT 'synthetic' AS mode,
       'Fully synthetic: metro sizing, processor coverage and category demand. Run sql/setup_census.sql to swap in real US Census Advance Retail Sales demand (free Financial Data Package) -> mode = hybrid.' AS note;

-- 8. Semantic view: one wide table over the benchmark, no relationships ---------
CREATE OR REPLACE SEMANTIC VIEW SITE_SELECTION_SV
  TABLES ( ss AS SNOWPACK_SITE_SELECTION.CORE.SITE_SELECTION_BENCHMARK PRIMARY KEY (metro_id, category_code)
           WITH SYNONYMS = ('site selection', 'expansion', 'white space', 'market coverage')
           COMMENT = 'Metro x merchant-category coverage vs demand: penetration, white-space, opportunity' )
  FACTS (
    ss.current_merchant_count AS CURRENT_MERCHANT_COUNT,
    ss.processed_volume_usd AS PROCESSED_VOLUME_USD,
    ss.est_market_volume_usd AS EST_MARKET_VOLUME_USD,
    ss.white_space_volume AS WHITE_SPACE_VOLUME,
    ss.population AS POPULATION,
    ss.median_hh_income AS MEDIAN_HH_INCOME,
    ss.est_business_count AS EST_BUSINESS_COUNT,
    ss.penetration_pct AS PENETRATION_PCT,
    ss.opportunity_score AS OPPORTUNITY_SCORE,
    ss.merchants_per_100k AS MERCHANTS_PER_100K,
    ss.category_demand_index AS CATEGORY_DEMAND_INDEX,
    ss.category_demand_growth_pct AS CATEGORY_DEMAND_GROWTH_PCT
  )
  DIMENSIONS (
    ss.metro_name AS METRO_NAME WITH SYNONYMS = ('metro', 'city', 'market', 'msa') COMMENT = 'Metro area',
    ss.metro_id AS METRO_ID,
    ss.state AS STATE WITH SYNONYMS = ('state'),
    ss.region AS REGION WITH SYNONYMS = ('region', 'geography'),
    ss.category_name AS CATEGORY_NAME WITH SYNONYMS = ('merchant category', 'vertical', 'segment') COMMENT = 'Merchant category (MCC-aligned)',
    ss.category_code AS CATEGORY_CODE
  )
  METRICS (
    ss.total_processed_usd AS SUM(ss.processed_volume_usd) COMMENT = 'Total processed volume (USD)',
    ss.total_market_usd AS SUM(ss.est_market_volume_usd) COMMENT = 'Total estimated market volume (USD)',
    ss.total_white_space_usd AS SUM(ss.white_space_volume) COMMENT = 'Total white-space (unpenetrated) volume (USD)',
    ss.total_merchants AS SUM(ss.current_merchant_count) COMMENT = 'Total current merchants',
    ss.weighted_penetration AS SUM(ss.processed_volume_usd) / NULLIF(SUM(ss.est_market_volume_usd), 0) COMMENT = 'Volume-weighted penetration (processed / estimated market), 0-1',
    ss.avg_penetration_pct AS AVG(ss.penetration_pct) COMMENT = 'Simple average of cell penetration, 0-1',
    ss.avg_opportunity_score AS AVG(ss.opportunity_score) COMMENT = 'Average opportunity score (demand growth x coverage gap)',
    ss.max_opportunity_score AS MAX(ss.opportunity_score) COMMENT = 'Peak opportunity score',
    ss.avg_merchants_per_100k AS AVG(ss.merchants_per_100k) COMMENT = 'Average merchants per 100k population',
    ss.avg_demand_growth_pct AS AVG(ss.category_demand_growth_pct) COMMENT = 'Category demand growth % over the last 24 months (same for every metro in a category)'
  )
  COMMENT = 'Site-selection semantic view (metro coverage vs category demand).';

-- 9. Notes table, app stage and agent ------------------------------------------
CREATE TABLE IF NOT EXISTS SITE_SELECTION_REPORTS (
  run_id STRING DEFAULT UUID_STRING(), subject STRING, scope STRING, draft_md STRING, report_md STRING,
  status STRING, edits_applied INT, residual_hedges INT, edits STRING, fact_pack STRING, latency_ms INT,
  created_at TIMESTAMP_NTZ DEFAULT SYSDATE()
);

CREATE STAGE IF NOT EXISTS SITE_SELECTION_APP_STAGE
  DIRECTORY = (ENABLE = TRUE) COMMENT = 'Streamlit app files (see sql/deploy_streamlit.sql)';

CREATE OR REPLACE AGENT SITE_SELECTION_AGENT
  COMMENT = 'Geographic Expansion & Site Selection agent (Cortex Analyst over SITE_SELECTION_SV)'
  PROFILE = '{"display_name": "Site Selection Agent", "color": "blue"}'
  FROM SPECIFICATION
  $$
  models:
    orchestration: auto
  instructions:
    response: 'You are a payments expansion strategist. Use ONLY figures from the Analyst tool. opportunity_score blends category demand growth with the coverage gap (higher = better expansion target). penetration_pct is a ratio (0-1); express it as a percent. Express USD in $B/$M. Never invent numbers. Do not name any real company, processor or bank. Be concise and name the metro and the category.'
    orchestration: 'For any metro, category, penetration, white-space, demand-growth or opportunity question use the SiteSelection Analyst tool.'
    sample_questions:
      - question: 'Which metro and category pairs have the highest white-space opportunity?'
      - question: 'Which metros have the most white-space dollars in total, and how covered are they?'
      - question: 'Compare average penetration and opportunity score by region.'
  tools:
    - tool_spec:
        type: cortex_analyst_text_to_sql
        name: SiteSelection
        description: 'Metro x merchant-category coverage vs category demand: penetration, white-space volume, demand growth and opportunity score.'
  tool_resources:
    SiteSelection:
      semantic_view: SNOWPACK_SITE_SELECTION.CORE.SITE_SELECTION_SV
      execution_environment:
        type: warehouse
        warehouse: SNOWPACK_SITE_SELECTION_WH
  $$;

SELECT 'Setup complete: ' || (SELECT COUNT(*) FROM SITE_SELECTION_BENCHMARK) || ' metro x category cells' AS status;
