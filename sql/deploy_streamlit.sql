-- ============================================================================
-- Geographic Expansion & Site Selection: deploy the Streamlit in Snowflake app
-- ----------------------------------------------------------------------------
-- Run after sql/setup.sql. First upload these files to the stage
-- SNOWPACK_SITE_SELECTION.CORE.SITE_SELECTION_APP_STAGE, keeping the folders:
--   app/streamlit_app.py           -> streamlit_app.py
--   app/environment.yml            -> environment.yml
--   app/.streamlit/config.toml     -> .streamlit/config.toml
--   app/static/*                   -> static/   (logo.svg, Figtree.woff2, OFL.txt, dotmap.json)
--   app/sample/*.json (optional)   -> sample/   (adds the Sample switch in Snowsight)
-- Upload with Snowsight (Data > Databases > SNOWPACK_SITE_SELECTION > CORE >
-- Stages > SITE_SELECTION_APP_STAGE > + Files), or from a terminal with PUT, e.g.
--   PUT file://app/streamlit_app.py @SNOWPACK_SITE_SELECTION.CORE.SITE_SELECTION_APP_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
-- The app lives inside the pack database, so sql/cleanup.sql removes it.
-- ============================================================================
USE ROLE SNOWPACK_SITE_SELECTION_ROLE;
USE WAREHOUSE SNOWPACK_SITE_SELECTION_WH;
USE SCHEMA SNOWPACK_SITE_SELECTION.CORE;

CREATE OR REPLACE STREAMLIT SITE_SELECTION_APP
  FROM '@SNOWPACK_SITE_SELECTION.CORE.SITE_SELECTION_APP_STAGE'
  MAIN_FILE = 'streamlit_app.py'
  RUNTIME_NAME = 'SYSTEM$WAREHOUSE_RUNTIME'   -- packages come from environment.yml
  QUERY_WAREHOUSE = SNOWPACK_SITE_SELECTION_WH
  TITLE = 'Geographic Expansion & Site Selection'
  COMMENT = 'Geographic Expansion & Site Selection example app';

SHOW STREAMLITS LIKE 'SITE_SELECTION_APP';
