-- ============================================================================
-- Geographic Expansion & Site Selection: cleanup.sql
-- Drops everything sql/setup.sql (and setup_census.sql / deploy_streamlit.sql)
-- created: the database (tables, views, semantic view, agent, stage, Streamlit
-- app), the warehouse, and the role. Nothing else is touched. Irreversible.
-- Safe to re-run on an account where some or all of it is already gone.
-- ============================================================================
USE ROLE SYSADMIN;
DROP DATABASE IF EXISTS SNOWPACK_SITE_SELECTION;
DROP WAREHOUSE IF EXISTS SNOWPACK_SITE_SELECTION_WH;

USE ROLE ACCOUNTADMIN;
DROP ROLE IF EXISTS SNOWPACK_SITE_SELECTION_ROLE;

SHOW DATABASES LIKE 'SNOWPACK_SITE_SELECTION';
