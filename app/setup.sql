-- ============================================================================
-- Geographic Expansion & Site Selection — setup.sql  (DEPLOY mode: real category demand)
-- ----------------------------------------------------------------------------
-- Geographic Expansion & Site Selection for a payments processor / acquirer.
-- Ranks metro x merchant-category cells by WHITE-SPACE opportunity: where is
-- category demand strong but the processor's merchant coverage (penetration)
-- still low? opportunity_score = category demand growth x (1 - penetration).
--
-- mode = 'hybrid': metro geography + processor coverage are SYNTHETIC (there is
-- no free demographics/POI in-account), but the DEMAND side is REAL US Census
-- Advance Retail Sales by category, from the free Snowflake Marketplace
-- "Financial Data Package" (SNOWFLAKE_PUBLIC_DATA_FINANCIAL_PACKAGE).
--
-- Real demographics (Census ACS) and POI / business density (Overture places)
-- are PAID Marketplace add-ons; swap SITE_SELECTION_METRO / SITE_SELECTION_COVERAGE
-- for those (same columns) to go fully live.
--
-- Prereq: mount the free "Financial Data Package" listing from the Marketplace.
-- Run setup_synthetic.sql instead for a no-listing TRY.
-- ============================================================================

-- 0a. Dedicated, isolated home: database, schema, and warehouse ---------------
CREATE DATABASE IF NOT EXISTS SNOWPACK_SITE_SELECTION;
CREATE SCHEMA IF NOT EXISTS SNOWPACK_SITE_SELECTION.CORE;
CREATE WAREHOUSE IF NOT EXISTS SNOWPACK_SITE_SELECTION_WH WITH WAREHOUSE_SIZE='XSMALL' AUTO_SUSPEND=60 AUTO_RESUME=TRUE INITIALLY_SUSPENDED=TRUE;
USE WAREHOUSE SNOWPACK_SITE_SELECTION_WH;
USE SCHEMA SNOWPACK_SITE_SELECTION.CORE;

CREATE SCHEMA IF NOT EXISTS SNOWPACK_SITE_SELECTION.CORE
  COMMENT = 'Geographic Expansion & Site Selection: metro x category white-space / expansion benchmarking';
USE SCHEMA SNOWPACK_SITE_SELECTION.CORE;

-- 0. Type-switch drops: CATEGORY_DEMAND is a VIEW here but a TABLE in
--    setup_synthetic.sql. Drop both forms so switching modes in the shared
--    schema never hits an "object exists but is not a <type>" error.
DROP VIEW  IF EXISTS SNOWPACK_SITE_SELECTION.CORE.SITE_SELECTION_CATEGORY_DEMAND;
DROP TABLE IF EXISTS SNOWPACK_SITE_SELECTION.CORE.SITE_SELECTION_CATEGORY_DEMAND;

-- 1. Category dim (MCC-aligned, mapped to Census variable codes) ---------------
--    (reuses ONLY the 6 verified ADV_* codes from the MarketShare template)
CREATE OR REPLACE TABLE SITE_SELECTION_MERCHANT_CATEGORY (
  category_code STRING, category_name STRING, mcc STRING, census_variable STRING
);
INSERT INTO SITE_SELECTION_MERCHANT_CATEGORY VALUES
  ('RESTAURANTS','Restaurants & Food Service','5812','ADV_722SM_SA'),
  ('APPAREL','Clothing & Accessories','5651','ADV_448SM_SA'),
  ('ELECTRONICS','Electronics & Appliances','5732','ADV_443SM_SA'),
  ('GROCERY','Food & Beverage Stores','5411','ADV_445SM_SA'),
  ('FURNITURE','Furniture & Home Furnishings','5712','ADV_442SM_SA'),
  ('HEALTH','Health & Personal Care','5912','ADV_446SM_SA');

-- 2. Metro geography dimension — SYNTHETIC (no free demographics in-account) -----
--    Population / income / business counts are plausible but fabricated. Real
--    demographics (Census ACS) and POI (Overture) are paid Marketplace listings;
--    swap this table for them (same columns) to go live.
CREATE OR REPLACE TABLE SITE_SELECTION_METRO (
  metro_id STRING, metro_name STRING, state STRING, region STRING,
  population NUMBER, median_hh_income NUMBER, est_business_count NUMBER
)
  COMMENT = 'SYNTHETIC metro geography (population/income/business counts fabricated). Real ACS/Overture are paid Marketplace add-ons.';
INSERT INTO SITE_SELECTION_METRO VALUES
  ('M01','New York-Newark','NY','Northeast', 8800000, 76000, 210000),
  ('M02','Los Angeles','CA','West',         3900000, 69000, 145000),
  ('M03','Chicago','IL','Midwest',          2700000, 65000,  98000),
  ('M04','Houston','TX','South',            2300000, 58000,  82000),
  ('M05','Phoenix','AZ','West',             1700000, 64000,  61000),
  ('M06','Philadelphia','PA','Northeast',   1600000, 52000,  57000),
  ('M07','Dallas','TX','South',             1340000, 60000,  54000),
  ('M08','Atlanta','GA','South',             500000, 67000,  41000),
  ('M09','Miami','FL','South',               470000, 47000,  38000),
  ('M10','Denver','CO','West',               715000, 78000,  44000);

-- Per-category synthetic coverage drivers (deterministic):
--   base_penetration    = processor's starting share of a metro's category market
--   base_mkt_per_capita = $ of category market volume per resident (metro sizing)
CREATE OR REPLACE TEMP TABLE SITE_SELECTION_drivers
  (category_code STRING, base_penetration FLOAT, base_mkt_per_capita FLOAT) AS
SELECT * FROM VALUES
  ('RESTAURANTS', 0.18, 1800),
  ('APPAREL',     0.12,  900),
  ('ELECTRONICS', 0.09,  600),
  ('GROCERY',     0.22, 2600),
  ('FURNITURE',   0.10,  500),
  ('HEALTH',      0.15, 1100)
  AS d(category_code, base_penetration, base_mkt_per_capita);

-- 3. Category demand side — REAL US Census Advance Retail Sales (latest vintage)
CREATE OR REPLACE VIEW SITE_SELECTION_CATEGORY_DEMAND
  COMMENT = 'REAL category demand by month, from SNOWFLAKE_PUBLIC_DATA_FINANCIAL_PACKAGE (US Census Advance Retail Sales, seasonally adjusted, USD), deduped to latest vintage.'
AS
WITH ts AS (
  SELECT variable, date,
         ROW_NUMBER() OVER (PARTITION BY variable, date ORDER BY _EFFECTIVE_START_TIMESTAMP DESC) AS rn,
         value
  FROM SNOWFLAKE_PUBLIC_DATA_FINANCIAL_PACKAGE.COMMERCIAL_BANKING.FINANCIAL_ECONOMIC_INDICATORS_TIMESERIES_PIT
  WHERE variable IN (SELECT census_variable FROM SITE_SELECTION_MERCHANT_CATEGORY)
)
SELECT c.category_code, c.category_name, ts.date AS month_end, ts.value AS market_sales_usd
FROM ts JOIN SITE_SELECTION_MERCHANT_CATEGORY c ON c.census_variable = ts.variable
WHERE ts.rn = 1;

-- 4. Coverage — SYNTHETIC processor coverage per metro x category ----------------
--    Fixed RNG seed (RANDOM(77)) so penetration jitter is stable across re-runs.
CREATE OR REPLACE TABLE SITE_SELECTION_COVERAGE
  COMMENT = 'SYNTHETIC: this processor''s merchant coverage by metro and category (penetration, processed vs estimated market volume). Replace with your own settlement + ACS market sizing to go live.'
AS
WITH base AS (
  SELECT mt.metro_id, mt.population, c.category_code, c.category_name,
         ROUND(mt.population * d.base_mkt_per_capita, 0) AS est_market_volume_usd,
         ROUND(LEAST(0.95, GREATEST(0.02,
                d.base_penetration + (UNIFORM(-30, 30, RANDOM(77)) / 1000.0))), 4) AS penetration_pct
  FROM SITE_SELECTION_METRO mt
  CROSS JOIN SITE_SELECTION_MERCHANT_CATEGORY c
  JOIN SITE_SELECTION_drivers d ON d.category_code = c.category_code
)
SELECT metro_id,
       category_code AS category,
       category_name,
       current_merchant_count,
       processed_volume_usd,
       est_market_volume_usd,
       penetration_pct
FROM (
  SELECT metro_id, category_code, category_name, est_market_volume_usd, penetration_pct,
         ROUND(est_market_volume_usd * penetration_pct, 0) AS processed_volume_usd,
         GREATEST(1, ROUND(est_market_volume_usd * penetration_pct / 2500000.0, 0)) AS current_merchant_count
  FROM base
);

-- 5. Benchmark view: ONE wide, pre-joined grain (metro x category) ---------------
--    Demand is pre-aggregated to the CATEGORY grain before the join so the metro
--    coverage rows never fan out; demand-derived columns are exposed as AVG (non-
--    additive) in the SV. opportunity_score is computed here (demand growth x gap).
CREATE OR REPLACE VIEW SITE_SELECTION_BENCHMARK
  COMMENT = 'Metro x merchant-category coverage vs category demand: penetration, white-space volume, opportunity score. Grain = (metro_id, category_code).'
AS
WITH demand AS (
  SELECT category_code, category_name,
         MAX(CASE WHEN rn_desc = 1 THEN market_sales_usd END) AS latest_demand_usd,
         MAX(CASE WHEN rn_asc  = 1 THEN market_sales_usd END) AS earliest_demand_usd
  FROM (
    SELECT category_code, category_name, market_sales_usd,
           ROW_NUMBER() OVER (PARTITION BY category_code ORDER BY month_end DESC) AS rn_desc,
           ROW_NUMBER() OVER (PARTITION BY category_code ORDER BY month_end ASC)  AS rn_asc
    FROM SITE_SELECTION_CATEGORY_DEMAND
  ) r
  GROUP BY category_code, category_name
)
SELECT cov.metro_id, mt.metro_name, mt.state, mt.region,
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

-- 6. Data-source marker -------------------------------------------------------
CREATE OR REPLACE VIEW SITE_SELECTION_DATA_SOURCE_INFO AS
SELECT 'hybrid' AS mode,
       'HYBRID: REAL US Census Advance Retail Sales category demand (free Financial Data Package listing) blended with SYNTHETIC metro geography and processor coverage. Real demographics/POI (Census ACS, Overture places) are paid Marketplace add-ons; swap SITE_SELECTION_METRO / SITE_SELECTION_COVERAGE for them (same columns) to go fully live.' AS note;

-- 7. Semantic view — single wide view over the benchmark, no RELATIONSHIPS ------
CREATE OR REPLACE SEMANTIC VIEW SITE_SELECTION_SV
  TABLES ( ss AS SNOWPACK_SITE_SELECTION.CORE.SITE_SELECTION_BENCHMARK PRIMARY KEY (metro_id, category_code)
           WITH SYNONYMS = ('site selection','expansion','white space','market coverage')
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
    ss.metro_name AS METRO_NAME WITH SYNONYMS = ('metro','city','market','msa') COMMENT = 'Metro area (synthetic)',
    ss.metro_id AS METRO_ID,
    ss.state AS STATE WITH SYNONYMS = ('state'),
    ss.region AS REGION WITH SYNONYMS = ('region','geography'),
    ss.category_name AS CATEGORY_NAME WITH SYNONYMS = ('merchant category','vertical','segment') COMMENT = 'Merchant category (MCC-aligned)',
    ss.category_code AS CATEGORY_CODE
  )
  METRICS (
    ss.total_processed_usd AS SUM(ss.processed_volume_usd) COMMENT = 'Total processed volume (USD)',
    ss.total_market_usd AS SUM(ss.est_market_volume_usd) COMMENT = 'Total estimated market volume (USD)',
    ss.total_white_space_usd AS SUM(ss.white_space_volume) COMMENT = 'Total white-space (unpenetrated) volume (USD)',
    ss.total_merchants AS SUM(ss.current_merchant_count) COMMENT = 'Total current merchants',
    ss.avg_penetration_pct AS AVG(ss.penetration_pct) COMMENT = 'Average penetration (processed / estimated market)',
    ss.avg_opportunity_score AS AVG(ss.opportunity_score) COMMENT = 'Average opportunity score (demand growth x white space)',
    ss.max_opportunity_score AS MAX(ss.opportunity_score) COMMENT = 'Peak opportunity score',
    ss.avg_merchants_per_100k AS AVG(ss.merchants_per_100k) COMMENT = 'Average merchants per 100k population',
    ss.avg_demand_growth_pct AS AVG(ss.category_demand_growth_pct) COMMENT = 'Average category demand growth % (real Census)'
  )
  COMMENT = 'Site-selection semantic view (synthetic metro coverage vs REAL Census category demand).';

-- 8. Output table + agent -----------------------------------------------------
CREATE TABLE IF NOT EXISTS SITE_SELECTION_REPORTS (
  run_id STRING DEFAULT UUID_STRING(), subject STRING, draft_md STRING, report_md STRING,
  status STRING, edits_applied INT, residual_hedges INT, created_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE AGENT SITE_SELECTION_AGENT
  COMMENT = 'Geographic Expansion & Site Selection agent (Cortex Analyst over SITE_SELECTION_SV)'
  PROFILE = '{"display_name": "Site Selection Agent", "color": "blue"}'
  FROM SPECIFICATION
  $$
  models:
    orchestration: auto
  instructions:
    response: 'You are a payments expansion strategist. Use ONLY figures from the Analyst tool. opportunity_score blends REAL category demand growth with coverage gap (higher = better expansion target). penetration_pct is a ratio (0-1). Express USD in $B/$M. Never invent numbers. Be concise and name the metro + category.'
    orchestration: 'For any metro, category, penetration, white-space, or opportunity question use the SiteSelection Analyst tool.'
    sample_questions:
      - question: 'Which metro and category pairs have the highest white-space opportunity?'
  tools:
    - tool_spec:
        type: cortex_analyst_text_to_sql
        name: SiteSelection
        description: 'Metro x merchant-category coverage vs REAL Census category demand: penetration, white-space volume, and opportunity score.'
  tool_resources:
    SiteSelection:
      semantic_view: SNOWPACK_SITE_SELECTION.CORE.SITE_SELECTION_SV
  $$;
