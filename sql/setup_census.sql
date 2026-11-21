-- ============================================================================
-- Geographic Expansion & Site Selection: setup_census.sql (real category demand)
-- ----------------------------------------------------------------------------
-- Run AFTER sql/setup.sql. Swaps the synthetic demand table for a view over REAL
-- US Census Advance Retail Sales (seasonally adjusted, USD) from the free
-- Snowflake Marketplace "Financial Data Package"
-- (SNOWFLAKE_PUBLIC_DATA_FINANCIAL_PACKAGE). Metro sizing and processor coverage
-- stay synthetic, so the data mode becomes 'hybrid'. The benchmark view, semantic
-- view, agent and app are unchanged; growth uses the latest 24 Census months.
--
-- Prerequisite: get the free Financial Data Package listing in Snowsight >
-- Marketplace and grant the pack role access to it, for example
--   USE ROLE ACCOUNTADMIN;
--   GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE_PUBLIC_DATA_FINANCIAL_PACKAGE
--     TO ROLE SNOWPACK_SITE_SELECTION_ROLE;
-- Run sql/setup.sql again to go back to fully synthetic demand.
-- ============================================================================
USE ROLE SNOWPACK_SITE_SELECTION_ROLE;
USE WAREHOUSE SNOWPACK_SITE_SELECTION_WH;
USE SCHEMA SNOWPACK_SITE_SELECTION.CORE;

EXECUTE IMMEDIATE $$
BEGIN
  BEGIN DROP VIEW IF EXISTS SITE_SELECTION_CATEGORY_DEMAND; EXCEPTION WHEN OTHER THEN NULL; END;
  BEGIN DROP TABLE IF EXISTS SITE_SELECTION_CATEGORY_DEMAND; EXCEPTION WHEN OTHER THEN NULL; END;
END;
$$;

CREATE OR REPLACE VIEW SITE_SELECTION_CATEGORY_DEMAND
  COMMENT = 'REAL category demand by month, from SNOWFLAKE_PUBLIC_DATA_FINANCIAL_PACKAGE (US Census Advance Retail Sales, seasonally adjusted, USD), latest vintage only.'
AS
WITH ts AS (
  SELECT variable, date, value,
         ROW_NUMBER() OVER (PARTITION BY variable, date ORDER BY _EFFECTIVE_START_TIMESTAMP DESC) AS rn
  FROM SNOWFLAKE_PUBLIC_DATA_FINANCIAL_PACKAGE.COMMERCIAL_BANKING.FINANCIAL_ECONOMIC_INDICATORS_TIMESERIES_PIT
  WHERE variable IN (SELECT census_variable FROM SITE_SELECTION_MERCHANT_CATEGORY)
)
SELECT c.category_code, c.category_name, LAST_DAY(ts.date) AS month_end, ts.value AS market_sales_usd
FROM ts JOIN SITE_SELECTION_MERCHANT_CATEGORY c ON c.census_variable = ts.variable
WHERE ts.rn = 1;

CREATE OR REPLACE VIEW SITE_SELECTION_DATA_SOURCE_INFO AS
SELECT 'hybrid' AS mode,
       'Hybrid: REAL US Census Advance Retail Sales category demand (free Financial Data Package) with SYNTHETIC metro sizing and processor coverage.' AS note;

SELECT category_code, MIN(month_end) AS first_month, MAX(month_end) AS latest_month, COUNT(*) AS months
FROM SITE_SELECTION_CATEGORY_DEMAND GROUP BY 1 ORDER BY 1;
