# v2 self-review

Checked on the `v2-rebuild` branch, November 2026, against the Snow Packs build standard's
"Before you call it done" list, the v2 addendum and every CONTRIBUTING Must. All results are from
this build session. Live checks ran with key-pair auth in a test account; everything was removed
afterwards.

## Build standard: before you call it done

| Item | Result | Evidence |
|---|---|---|
| Run the app from a fresh clone in Sample (mock) mode | Pass | Fresh `git clone` of the branch, no Snowflake variables: all five pages render with no exceptions (Streamlit AppTest); the app opens in Sample mode |
| Setup → Live mode → cleanup in a clean role | Pass | `sql/setup.sql` run three times (13–16 s each, re-runnable); every screen, both notes, re-verify and the agent run in Live mode as `SNOWPACK_SITE_SELECTION_ROLE`; `sql/cleanup.sql` then `SHOW DATABASES / WAREHOUSES / ROLES LIKE 'SNOWPACK_SITE_SELECTION%'` return nothing; cleanup re-run is a no-op |
| Grep files and git history for secrets, account identifiers, real user names | Pass | Scan of HEAD and every added line in the pushed history, plus every blob for local paths: only placeholders (`<your_key>.p8`, `*.p8` in .gitignore) and public catalog URLs. No `.pyc`, `.env` or keys tracked |
| Open the Pages URL and `/try/` signed out; phone width and dark mode | Pass | Fork Pages (branch `v2-rebuild`, `/docs`) built; guide and all five `/try/` screens at 390 px and 1400 px, light and dark: no console errors, no horizontal scroll |
| Story beats visible in a screenshot | Pass | Houston #1 and Phoenix #2 (overview, map, ranking, cell panel), Furniture zero row (overview heat map), Chicago saturated and New York biggest-pool-ranks-7th (overview panel), verifier catching a forecast (note-needs-review) |

## v2 addendum

| Item | Result | Notes |
|---|---|---|
| `docs/DESIGN.md` before UI: logo SVG, voice, palette, type, layout, density, charts, motion | Pass | Indigo + apricot, Figtree, sidebar shell, dot-map |
| No coined product name; plain pack name | Pass | App and guide titled "Geographic Expansion & Site Selection" / "Site Selection" |
| Distinct from at least 5 live packs | Pass | Nine packs compared in DESIGN.md |
| Branded shell: navigation, logo, user/role chip, Sample/Live badge | Pass | |
| KPI tiles with trends, charts with tooltips and legends, sortable/filterable tables with status pills, drawers, empty/loading/error states | Pass | Trend arrows are omitted on the KPI tiles because the data has no prior period for coverage; the tiles carry comparison notes instead |
| Motion: transitions, skeletons, hover, animated counters | Pass | `prefers-reduced-motion` respected |
| Tokens from DESIGN.md; WCAG AA | Pass | `scripts/check_contrast.py`: 47 of 47 pairs pass |
| Dark mode if the design calls for it | Pass (guide) | Guide supports dark mode; the Streamlit app and hosted example are light by design (DESIGN.md) |
| AI: 4–8 s staged steps, streaming reveal, citations, "Sample AI response" label | Pass | Notes cite fact-pack rows `[F1]`…; agent answers show their SQL |
| 390 px and desktop, no horizontal scroll | Pass | App (Sample and Live), hosted example and guide |
| Sample/Live switch, no silent fallback | Pass | Live without a connection shows setup steps and stops |
| Seeded deterministic generator, stories in `data/README.md` | Pass | Two runs give identical `HASH_AGG` on all three generated tables |
| Docs checked for every feature; preview labeled | Pass | Semantic view SQL queries and Cortex Agents are GA; no Preview feature is used |
| Only claim what ran in Live mode | Pass | `sql/setup_census.sql` is stated as not run (listing not mounted in the test account) |
| Landing page: own identity, problem-first headline, captioned screenshots, matching alt text, disclaimer, docs links, no CDN scripts | Pass | |
| App screenshots in `docs/images/`; 2–8 catalog cards 960×600 JPG < 100 KB, dashboard first | Pass | 9 screenshots; 6 cards, 63–99 KB |
| `docs/.nojekyll`; every JS/CSS from `/try/index.html` returns 200 live | Pass | `app.js`, `app.css`, font, data files all 200 on the fork's Pages site |
| Signed commits, pushed after every step, no force-push | Pass | Every v2 commit shows `G` |

## CONTRIBUTING Musts

| Must | Result |
|---|---|
| Starts from a business problem an industry recognizes | Pass: where an acquirer should expand next |
| One industry and one business function | Pass: Payments · go-to-market / expansion strategy |
| Public repo `sfguide-<topic>` | Pass (owner's repo; this is a fork branch) |
| LICENSE (Apache 2.0) | Pass |
| GitHub Pages enabled, `.nojekyll` | Pass on the fork; the owner switches his repo to `main` `/docs` after merge (V2-CHANGES.md) |
| Business problem and outcome on the first screen | Pass |
| Screenshots of the running app | Pass |
| Caption naming the Snowflake capability, plus alt text, per screenshot | Pass |
| Name the capability behind each component; only tested claims | Pass |
| Visible disclaimer | Pass (guide, app footer, hosted example) |
| Links to repo and Snowflake docs | Pass; all docs links returned 200 |
| No Snowflake logo files or trademarked imagery | Pass |
| No internal sales motions | Pass |
| End-user app with navigation, drill-downs and the key decision | Pass |
| No-account mode on bundled synthetic data | Pass (hosted `/try/` and local Sample mode) |
| Simulated output labeled "Sample AI response" | Pass |
| Live mode against Snowflake | Pass |
| Synthetic data only; deterministic | Pass |
| Self-contained setup: dedicated database, XSMALL warehouse with short auto-suspend, changes nothing existing | Pass |
| Cleanup removes everything | Pass (database with Streamlit app, warehouse, role) |
| No credentials, keys, account IDs or internal hostnames in code, screenshots, output or history | Pass |
| User names redacted in captured output | Pass (captures store no user names; screenshots show only the fictional role chip) |
| No customer names, data or identifiable logic | Pass; "Corvane Payments" is a coined name and no payments firm by that name turned up |
| No deals, internal programs or roadmap | Pass |
| GA or labeled preview features | Pass |
| README: prerequisites with tested versions | Pass |
| README: run steps and objects table | Pass |
| README: cost and time | Pass (measured) |
| README: known limitations | Pass |
| README: Customize with Cortex Code | Pass |
| README: owner and last-reviewed date | Pass: `Owner: Javier Soliz · Last reviewed: November 2026` |
| License and as-is disclaimer | Pass |
| Outcomes as possibilities; no unmeasured numbers | Pass |
| Results qualified as synthetic | Pass |

## Not verified this round

- `sql/setup_census.sql` (real Census demand): written against the listing's documented table,
  but the test account has no Financial Data Package mounted, so it was not run.
- The deployed Streamlit in Snowflake app: `sql/deploy_streamlit.sql` ran and created
  `SITE_SELECTION_APP` from the staged files, but it was not opened in Snowsight (that needs an
  interactive sign-in). The same file was verified locally in Live mode against the same objects.
