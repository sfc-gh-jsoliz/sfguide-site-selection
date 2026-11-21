# Synthetic data

Everything in this pack is synthetic except the optional real demand variant. The fictional
processor is **Corvane Payments**. Metro names and city-centre coordinates are public geography;
every metro's population, income, business count and coverage figure is illustrative. No
customer, merchant or real company data is used.

## Generator

`sql/setup.sql` generates the data inside Snowflake, so there is nothing to download:

| Table | Rows | What it holds |
|---|---|---|
| `SITE_SELECTION_MERCHANT_CATEGORY` | 6 | MCC-aligned merchant categories mapped to Census Advance Retail Sales codes |
| `SITE_SELECTION_METRO` | 10 | Metro sizing (synthetic), region, and city-centre latitude/longitude for the map |
| `SITE_SELECTION_CATEGORY_DEMAND` | 144 | National category demand, 24 month-ends from July 2024 to the as-of date, **30 June 2026** |
| `SITE_SELECTION_COVERAGE` | 60 | Corvane's coverage per metro × category: penetration, processed vs estimated market volume, merchant count |

`SITE_SELECTION_BENCHMARK` joins them at the metro × category grain and computes
`white_space_volume = est_market_volume - processed_volume` and
`opportunity_score = max(category demand growth %, 0) × (1 − penetration)`.

**Seeded and deterministic.** Every random draw is `UNIFORM(lo, hi, HASH(<row key>, <salt>))`
(row key = metro and category, or category and month). There is no `RANDOM()`, so re-running
setup produces identical rows. Checked on two consecutive runs (November 2026):

```sql
SELECT COUNT(*), HASH_AGG(*) FROM SITE_SELECTION_CATEGORY_DEMAND; -- 144, 3369395391973732245
SELECT COUNT(*), HASH_AGG(*) FROM SITE_SELECTION_COVERAGE;        -- 60,  -7413935289104092247
SELECT COUNT(*), HASH_AGG(*) FROM SITE_SELECTION_METRO;           -- 10,  4574997303911979360
```

The Sample mode files in `app/sample/` and `docs/try/data/` were captured from a Live run of
this generator (`scripts/capture_sample.py`), so Sample and Live show the same numbers.

## Planted stories

| # | Story | Where it shows | Value on this data set |
|---|---|---|---|
| 1 | **Houston grocery is the top target.** The fastest-growing category, almost uncovered. | Overview KPI, map ring, ranking #1, notes | 8.0% penetration, 10.35% demand growth, score 9.52, $5.50B white space |
| 2 | **Phoenix restaurants is the runner-up.** | Ranking #2, map, notes | 6.0% penetration, score 8.65, $2.88B white space |
| 3 | **Flat demand scores zero.** Furniture has $10.7B of white space but no demand growth, so no cell ranks. | Heat map (empty row), category chart, ranking | 0.00% growth, every Furniture score 0 |
| 4 | **Chicago grocery is saturated.** The only cell above 30% penetration. | Ranking "Saturated" pill, Chicago panel | 46.0% penetration, score 5.59 despite the top growth category |
| 5 | **The biggest pool is not the best target.** New York grocery has the most white-space dollars but ranks 7th, because the score is a growth × gap index, not a dollar figure. | Ranking, map bubble size, notes | $17.53B white space, score 7.93 |
| 6 | **Holiday lift in gift categories.** Apparel and Electronics demand jumps in November and December. Growth is measured first month to latest, so it does not move the score. | Overview demand chart | Apparel +9%, Electronics +14% in Nov–Dec |
| 7 | **South and West lead the expansion list.** | Ranking region filter, map | 4 South and 4 West cells in the top 12, 3 Northeast, 1 Midwest |

Category demand growth over 24 months: Grocery 10.35%, Restaurants 9.20%, Health 6.90%,
Apparel 6.90%, Electronics 4.60%, Furniture 0.00%.

## Real demand variant

`sql/setup_census.sql` replaces `SITE_SELECTION_CATEGORY_DEMAND` with a view over real US Census
Advance Retail Sales from the free Marketplace Financial Data Package (latest 24 months), so the
data mode becomes `hybrid`. Stories 1–5 depend on the planted coverage and still hold in shape,
but the growth figures and scores change with the real data.
