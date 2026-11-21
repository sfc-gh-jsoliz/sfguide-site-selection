# What changed in v2

This branch rebuilds Geographic Expansion & Site Selection to the Snow Packs v2 bar (see
`COCO-V2-INSTRUCTIONS.md`). Your data story (white-space ranking by demand growth × coverage gap),
Snowflake features (semantic view, Cortex AI_COMPLETE draft + verifier, Cortex Agent over Cortex
Analyst, optional free Census demand), Streamlit stack and owner line are unchanged. The app, the
landing page and the polish are new. The app is titled with the pack's plain name; there is no
product name.

## Screen by screen

| Screen | v1 | v2 | Why |
|---|---|---|---|
| App shell | Streamlit title, a sidebar button, a warning banner for the data mode | Indigo sidebar with the Site Selection logo and five screens, a user/role chip, **Sample/Live** environment badge and switch, as-of date and "Synthetic data" chip | v2 asks for a branded, enterprise-looking shell with a visible mode badge |
| Overview | Not present (the app opened on the note gallery) | KPI tiles (white space, weighted penetration, top target, fastest category, cells ranked), an opportunity heat map by metro and category, a "What stands out" panel, and 24 months of category demand with the holiday months shaded. Read from the semantic view with `SEMANTIC_VIEW()` | Shows the ranking stories at a glance and makes the semantic view a runtime feature instead of setup-only |
| Market map | Not present | Dot-map of the contiguous US with metros sized by white-space dollars and colored by region, apricot rings on metros holding a top-5 cell, region totals from the semantic view, and a metro table that opens a panel per metro | Site selection is geographic; the map makes it readable |
| Opportunity ranking | A ranked table inside each note only | Penetration vs demand-growth scatter with a "growing and under-covered" corner, region/category filters and search, a sortable table of all 60 cells with Top target / Saturated / No demand growth / Watch pills, and a panel per cell that works the score out on its own numbers | Rich tables and drill-downs; explains why the biggest pool is not the top score |
| Expansion notes | One button, spinner, gallery of cards | Two scopes (national top 12, or South and West top 8). Staged progress steps, streaming reveal, `[F#]` citation chips tied to the fact-pack rows, a Verified / Needs review stamp, a **Try to break it** button that adds a hedged forecast and reruns only the verifier, and a gallery that opens saved notes in a panel | v2 AI bar: staged steps, streaming, citations and a visible quality gate |
| Ask the analyst | Agent only in Snowsight | In-app chat with the Cortex Agent: three sample questions, staged steps, streamed answer, result table, and the generated SQL as the source | Cortex Agents / Analyst were created but not used by the app; now they run in Live mode |
| Hosted example (`/try/`) | Static page with mocked notes | Static copy of all five screens on data captured from a Live run, labeled "Sample AI response", 4–8 s simulated delays, sortable tables, drawers, tooltips; works at 390 px | v2 hosted-example bar |
| Landing page | Shared template look | Own identity: indigo hero with a dot-map whose top two targets pulse, problem-first headline, captioned screenshots with matching alt text, capability table with measured timings, dark mode, self-hosted Figtree font, no CDN scripts | v2 landing-page bar |

## Data and SQL

- SQL moved to `sql/`: `setup.sql` is the synthetic default (was `app/setup_synthetic.sql`),
  `setup_census.sql` swaps in real US Census demand on top of it (was `app/setup.sql`),
  `cleanup.sql` replaces `app/teardown.sql`, and `deploy_streamlit.sql` is new.
- **Least-privilege role** `SNOWPACK_SITE_SELECTION_ROLE` owns everything; cleanup drops it too.
- **Deterministic generator:** `RANDOM(77)` is not guaranteed to give the same value to the same
  row across runs. Every draw is now `UNIFORM(lo, hi, HASH(row key, salt))`; two runs give
  identical `HASH_AGG` (see `data/README.md`).
- **Planted stories** (documented in `data/README.md`): Houston grocery is the top target (8%
  covered), Phoenix restaurants is second, Furniture has no growth so it scores zero, Chicago
  grocery is saturated (46%), New York grocery has the most white space but ranks 7th, and gift
  categories show a holiday lift.
- **Census growth window fixed:** v1 compared the first and latest month of the whole Census
  history, so growth covered decades. The benchmark now uses the latest 24 months of whatever
  demand source is active.
- `SITE_SELECTION_METRO` gains city-centre latitude/longitude for the map. The semantic view
  gains a volume-weighted `weighted_penetration` metric. The agent spec pins its warehouse, has
  three sample questions and is told not to name real companies.
- `SITE_SELECTION_REPORTS` gains `scope`, `edits`, `fact_pack` and `latency_ms` (the notebook's
  inserts still work).
- AI fixes: `AI_COMPLETE` returns a JSON-encoded string, which broke the verifier's parsing in v1
  (notes came back "Needs review / unparseable"). The output is now decoded, the verifier's last
  JSON object is taken, both prompts share the same rounding rules, and the fact pack carries
  `*_display` values and the growth window so the draft copies figures the verifier accepts.

## What to do after merging

1. **Pull:** once this PR is merged into your `main`, run `git pull` in your local clone to bring
   it up to date. Nothing else in your repo changes.
2. **GitHub Pages:** Settings > Pages > Deploy from a branch > `main` / `/docs`. The guide moves to
   `docs/index.html` and the hosted example to `docs/try/`. `docs/.nojekyll` is included. Until you
   switch, the root `index.html` and `try/index.html` redirect to `docs/`, so existing links keep
   working either way.
3. **Check the site** once Pages shows "built": open `/` and `/try/` signed out, on a phone and on
   desktop.
4. **No build step.** The app is plain Streamlit and the hosted example is static HTML/JS/CSS.
5. **To refresh the Sample data** after changing the data or prompts: run `sql/setup.sql`, then
   `python scripts/capture_sample.py` with the key-pair environment variables from the README. It
   rewrites `app/sample/` and `docs/try/data/`. If you change metros, rerun
   `scripts/build_landing_map.py` and paste its SVG into the hero of `docs/index.html`.
6. **To redeploy the Streamlit in Snowflake app:** upload the `app/` files to
   `SITE_SELECTION_APP_STAGE` and run `sql/deploy_streamlit.sql` (steps in the README).
7. The catalog card images are in `docs/catalog/` (960×600, under 100 KB). The Snow Packs
   maintainers will update the catalog entry's screenshots in a separate PR.
8. The old `assets/site-selection-*.png` images are kept so existing catalog links don't break;
   delete them once the catalog points at the new cards.

`COCO-V2-INSTRUCTIONS.md` is the checklist used for this rebuild; give it to your CoCo to bring
your other packs to v2.
