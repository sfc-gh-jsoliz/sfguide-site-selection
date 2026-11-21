# Design: Geographic Expansion & Site Selection (v2)

The app, the hosted example (`docs/try/`) and the guide (`docs/index.html`) share one look. This
file is the source of truth for colors, type and layout. The Streamlit theme
(`app/.streamlit/config.toml`), the app CSS (`app/streamlit_app.py`), `docs/try/app.css` and
`docs/site.css` take their tokens from here.

## Brand

- **Name:** the pack's plain name, **Geographic Expansion & Site Selection**, shortened in the app
  shell to **Site Selection**. No coined product name.
- **Fictional firm in the data:** Corvane Payments, a mid-size merchant acquirer (coined name;
  not a real firm). The user chip reads "Expansion strategist · Corvane Payments".
- **Audience:** go-to-market and expansion strategy teams at a payments processor or acquirer,
  and the expansion committee they report to.
- **Voice:** plain, decisive, numbers first. "Houston grocery: 9% covered, $1.0B of white space."
  No hype words; every claim names the metro and the category.
- **Logo mark (inline SVG):** a 3 × 3 dot grid (the map) on a rounded indigo square, with the
  lower-right dot replaced by an apricot map pin (the chosen site).

```svg
<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Site Selection">
  <rect width="32" height="32" rx="8" fill="#1C1A4A"/>
  <g fill="#8E88E8"><circle cx="9" cy="9" r="2"/><circle cx="16" cy="9" r="2"/><circle cx="23" cy="9" r="2"/>
  <circle cx="9" cy="16" r="2"/><circle cx="16" cy="16" r="2"/><circle cx="23" cy="16" r="2"/>
  <circle cx="9" cy="23" r="2"/><circle cx="16" cy="23" r="2"/></g>
  <path d="M23 26.5c-3-3.4-4.6-5.9-4.6-7.8a4.6 4.6 0 0 1 9.2 0c0 1.9-1.6 4.4-4.6 7.8Z" fill="#F29A4A"/>
  <circle cx="23" cy="18.7" r="1.7" fill="#1C1A4A"/>
</svg>
```

## Palette

| Token | Hex | Use |
|---|---|---|
| `indigo-950` | `#1C1A4A` | Sidebar, landing hero band, logo square |
| `indigo-800` | `#2E2A78` | Active nav item, darkest heat-map step |
| `indigo-600` | `#4F46C8` | Primary buttons, links, Northeast region |
| `indigo-300` | `#8E88E8` | Logo dots, dot-map land on dark |
| `indigo-50` | `#EEF0FB` | Lightest heat-map step, AI pill background |
| `canvas` | `#F4F5FA` | App background |
| `paper` | `#FFFFFF` | Cards, tables, drawers |
| `paper-2` | `#F8F8FC` | Table headers, insight rows |
| `line` | `#DCDEEA` | Borders, gridlines |
| `ink` | `#16163A` | Body text |
| `muted` | `#565873` | Secondary text, axis labels |
| `apricot` | `#F29A4A` | Target pins and accents on dark backgrounds only |
| `apricot-ink` | `#A44A12` | "Top target" text and pills on light backgrounds |
| `apricot-50` | `#FDEBDD` | "Top target" pill background |
| `saturated` | `#5E6A85` | "Saturated" (high penetration) pill text |
| `good` | `#1F7A4D` | Verified stamp, positive trend |
| `bad` | `#B23A2E` | Needs review stamp, negative trend |
| `sample` | `#7A5200` on `#FFF2D6` | Sample badge and "Sample AI response" label |

Regions (charts only, always with a legend): Northeast `#4F46C8`, West `#0E7C86`,
South `#B34F12`, Midwest `#7A6A1F`.

Heat ramp for the opportunity score: `#EEF0FB` → `#B7B4F0` → `#6A5FD8` → `#2E2A78`.

Contrast: every text/background pair above was checked with `scripts/check_contrast.py`
(WCAG AA, 4.5:1 for body text). `apricot` is never used for text on light backgrounds.

## Typography

- **Figtree** (SIL OFL 1.1, self-hosted from `app/static/Figtree.woff2` and `docs/fonts/`), weights
  400–800, for headings, KPI values and the wordmark. Latin subset, 19 KB.
- System UI stack for body text and tables, with tabular figures for every number column.
- Scale: page title 1.55 rem/700, card title 1.0 rem/650, KPI value 1.5 rem/750, body 0.9 rem,
  table 0.82 rem, captions 0.75 rem.

## Layout model and density

- **App shell:** a fixed **indigo left sidebar** (Streamlit sidebar navigation) with the logo,
  wordmark and five screens; content sits on the lavender-grey canvas. A context bar on top of
  every screen holds the user/role chip, the **Sample/Live** environment badge and switch, the
  as-of date and a "Synthetic data" chip. On phones the sidebar collapses behind the menu button.
- **Screens:** Overview, Market map, Opportunity ranking, Expansion notes, Ask the analyst.
- **Density:** medium. KPI row of five tiles, then a 2:1 grid of cards; tables show 10–15 rows
  before scrolling. Cards have 12 px radius, 1 px `line` border and no drop shadow until hover.
- **Detail panels:** selecting a metro or a cell opens a large dialog (drawer) with its own KPIs,
  chart and table.

## Chart style

- Altair in the app, hand-written SVG in the hosted example; same encodings in both.
- **Dot-map:** the contiguous US drawn as a grid of small indigo dots (generated from a coarse
  outline by `scripts/make_dotmap.py`), metros as bubbles sized by white-space dollars and
  colored by region; the top targets get an apricot ring. Positions are plain longitude/latitude.
- **Heat map:** metro × category, opportunity score on the indigo ramp, value labels in cells.
- **Scatter:** penetration (x) vs category demand growth (y), bubble = white space, apricot
  quadrant shading for "growing and under-covered".
- **Lines:** 24-month category demand, one line per category, holiday months shaded.
- Gridlines in `line`, axis labels in `muted`, legends on top, tooltips on every mark.

## Motion

- Cards fade up 8 px on entry (`animation-fill-mode: backwards`, 180 ms).
- KPI values count up from zero (900 ms ease-out).
- Skeleton shimmer while Live queries run.
- Target pins on the landing dot-map pulse (2.4 s loop).
- Verified / Needs review stamp drops in with a short scale.
- All motion is off under `prefers-reduced-motion: reduce`.

## Dark mode

The app follows the light theme (Streamlit in Snowflake theming is per app). The landing page
supports `prefers-color-scheme: dark`: canvas `#11112B`, cards `#1A1A3D`, text `#E9E9F7`,
muted `#A9AACB`, line `#2E2F5A`; the indigo hero stays the same.

## How this pack differs from the rest of the catalog

Looked at the landing pages and Try apps of: Auto Finance Portfolio Analytics, Workforce
Intelligence, Chargeback & Dispute Intelligence (v2), Cross-Border & FX (v2), Macro Stress Testing
(v2), Verified Bank Research (v2), Market Data Discovery, Loan File Review and Complaints
Intelligence.

| Existing pack | What it uses | What this pack does instead |
|---|---|---|
| Auto Finance | Dark-green sidebar, gradient hero banner with stat tiles | Indigo sidebar, no gradient banner; hero is a dot-map |
| Workforce Intelligence | Teal-to-coral, serif headings | Indigo + apricot, geometric sans (Figtree) |
| Dispute Intelligence v2 | Teal masthead with top navigation, ticket-stack hero, Sora | Left sidebar, map hero, Figtree |
| Cross-Border & FX v2 | Pine green and gold, arc mark | Indigo and apricot, dot-grid + pin mark |
| Macro Stress Testing v2 | Charcoal and cream, bar mark | Cool lavender canvas, no warm paper |
| Verified Bank Research v2 | Gold hallmark on ink | No dark-gold palette |
| Market Data Discovery | Navy with pink, contour-field hero | No contour lines; discrete dots, apricot not pink |
| Loan File Review | Cobalt and yellow, transit-line hero | No stage line |
| Complaints Intelligence | Burgundy on light, light hero | Dark indigo hero band |

No other pack uses this palette, a dot-map hero, or Figtree.
