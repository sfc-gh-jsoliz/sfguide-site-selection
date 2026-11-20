# Geographic Expansion & Site Selection

Rank every metro × merchant-category cell by white-space opportunity — where category demand is strong but merchant coverage is still thin — on governed Snowflake data.

Owner: Javier Soliz · Last reviewed: November 2026

## What it shows

A payments processor expansion / go-to-market strategy team needs to decide where to grow next. This pack ranks every metro × merchant-category cell by a computed **opportunity score** (strong, growing category demand meeting a low-coverage gap), surfaces the top expansion targets in a ranked table, and writes a one-page expansion note grounded only in the ranked, governed figures — with a verification pass that flags the note **Verified** or **Needs review**.

## How it works

- A Streamlit-in-Snowflake app ranks metro × merchant-category white-space opportunity on governed data. `opportunity_score = max(category demand growth %, 0) × (1 − penetration)` — the more demand growth meets a coverage gap, the higher the cell ranks.
- The app calls Cortex **`AI_COMPLETE`** twice per run: once to draft the expansion note under strict data rules (copy the ranked figures exactly, no estimates, no hedging), and once to fact-check that draft against the fact pack.
- Setup also creates a **Cortex Agent** and a **Cortex Analyst semantic view** over the benchmark. These are explorable in Snowsight (AI & ML → Agents, or the semantic view in a worksheet) for natural-language questions — they are **not** called by the Streamlit app.
- The demand backdrop can use **real, free US Census** Advance Retail Sales data (the free Snowflake Marketplace Financial Data Package). Metro geography and processor coverage are synthetic.

## Prerequisites

- A Snowflake account — Snowflake Enterprise Edition or higher, in a region where Cortex AISQL and Cortex Agents are available.
- A role that can `CREATE DATABASE` and `CREATE WAREHOUSE` (setup builds a dedicated database and warehouse).
- Cortex AI functions available in your region (the app uses `AI_COMPLETE`; it defaults to `claude-sonnet-4-5` — change the `MODEL` constant if your account differs).
- Streamlit in Snowflake (to deploy the app).
- **Sample mode** (`setup_synthetic.sql`) is fully synthetic — no Marketplace listing or external data required.
- **Deploy mode** (`setup.sql`) blends synthetic geography/coverage with the free, public US Census demand data — no paid data.

## Setup

1. **Sample (fully synthetic):** run [`app/setup_synthetic.sql`](app/setup_synthetic.sql). It builds everything — geography, coverage, *and* demand — on synthetic data. No listing required.
2. **Real demand (free):** in Snowsight → Marketplace, get the free **Financial Data Package** (`SNOWFLAKE_PUBLIC_DATA_FINANCIAL_PACKAGE`), then run [`app/setup.sql`](app/setup.sql). Demand becomes real US Census Advance Retail Sales (`mode = hybrid`).
3. **Deploy the app:** create a stage and a Streamlit in Snowflake app inside `SNOWPACK_SITE_SELECTION.CORE` over [`app/streamlit_app.py`](app/streamlit_app.py) — keeping the stage and app in this schema lets `teardown.sql` remove them with the database.
4. **Explore the agent:** Snowsight → AI & ML → Agents → **Site Selection Agent**, or query the semantic view directly.

Both setup scripts build the identical objects in `SNOWPACK_SITE_SELECTION.CORE`, so the app, semantic view, and agent are unchanged between modes. An optional lab notebook, [`notebook/lab-site-selection.ipynb`](notebook/), builds the whole pattern cell by cell.

## Objects created

| Object | Type | Purpose |
|---|---|---|
| `SNOWPACK_SITE_SELECTION` | Database | Dedicated, isolated home for all pack objects |
| `SNOWPACK_SITE_SELECTION.CORE` | Schema | Holds the tables, views, semantic view, and agent |
| `SNOWPACK_SITE_SELECTION_WH` | Warehouse | XSMALL warehouse (auto-suspend 60s) for setup and the app |
| `SITE_SELECTION_MERCHANT_CATEGORY` | Table | MCC-aligned merchant categories mapped to Census variable codes |
| `SITE_SELECTION_METRO` | Table | Synthetic metro geography (population, income, business counts) |
| `SITE_SELECTION_CATEGORY_DEMAND` | Table (sample) / View (deploy) | Category demand by month — synthetic in sample, real US Census in deploy |
| `SITE_SELECTION_COVERAGE` | Table | Synthetic processor coverage per metro × category (penetration, processed vs est. market) |
| `SITE_SELECTION_BENCHMARK` | View | Wide, pre-joined metro × category grain with white-space and opportunity score |
| `SITE_SELECTION_DATA_SOURCE_INFO` | View | Marker view describing the active data mode (`synthetic` / `hybrid`) |
| `SITE_SELECTION_SV` | Semantic view | Governed business meaning over the benchmark for Cortex Analyst |
| `SITE_SELECTION_REPORTS` | Table | Stores generated expansion notes and their verification status |
| `SITE_SELECTION_AGENT` | Cortex Agent | Natural-language access to the semantic view (explorable in Snowsight) |
| Streamlit app | Streamlit | Ranks white-space opportunity and generates verified expansion notes |

## Cost & time

Setup and a few app runs take a handful of minutes. All compute runs on an XSMALL warehouse that auto-suspends after 60 seconds. `AI_COMPLETE` calls incur Cortex usage per run. Costs depend on your account's rates and region.

## Known limitations

- Metro geography and processor coverage are **synthetic** — coverage and opportunity figures are illustrative, not a real book of business.
- Census demand is by national category (metro × category demand is approximated by blending national category demand with synthetic metro sizing).
- The browser Try page is a static, client-side illustration — not live inference.
- Not a production system: review, test, and adapt before any real use.

## Customize with Cortex Code

Adapt this pack to your own expansion questions by prompting Cortex Code against the objects in `SNOWPACK_SITE_SELECTION.CORE`:

- "Change the `opportunity_score` in `SITE_SELECTION_BENCHMARK` to weight median income and population so dense, high-income metros score higher."
- "Add a coverage-gap view that lists every metro × category where penetration is below 20% but category demand growth is in the top quartile, and expose it to `SITE_SELECTION_SV`."
- "Join real US Census ACS demographics to `SITE_SELECTION_METRO` and rebuild the demand signal per metro instead of blending national category demand with synthetic sizing."

## Cleanup

Run [`app/teardown.sql`](app/teardown.sql) to drop the database (and all its objects) and the warehouse created by this pack.

## Learn more

- [Cortex AISQL (AI_COMPLETE and related functions)](https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql)
- [Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)
- [Cortex Analyst](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)
- [Streamlit in Snowflake](https://docs.snowflake.com/en/developer-guide/streamlit/about-streamlit)

---

Apache 2.0 (see [`LICENSE`](LICENSE)). Illustrative example provided as-is, not an official Snowflake product, not supported by Snowflake Support. Contains no customer data. Review and test before any production use.
