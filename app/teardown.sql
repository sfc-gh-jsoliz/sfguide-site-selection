-- ============================================================================
-- Geographic Expansion & Site Selection — teardown.sql
-- ----------------------------------------------------------------------------
-- Removes everything this pack created: the dedicated database (with all of its
-- objects — tables, views, semantic view, agent, reports) and the warehouse.
-- Safe to run multiple times (IF EXISTS). This is irreversible.
-- ============================================================================

DROP DATABASE IF EXISTS SNOWPACK_SITE_SELECTION;
DROP WAREHOUSE IF EXISTS SNOWPACK_SITE_SELECTION_WH;
