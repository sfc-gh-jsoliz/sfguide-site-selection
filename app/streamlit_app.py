"""Geographic Expansion & Site Selection (Streamlit).

One file, so it can be pasted into a Streamlit in Snowflake app as-is.
- Live mode: Snowpark. Inside Streamlit in Snowflake it uses the app's session; locally it
  uses key-pair auth from environment variables (see README, "Run locally in Live mode").
- Sample mode: bundled JSON in app/sample/, captured from a Live run of sql/setup.sql by
  scripts/capture_sample.py. Simulated AI waits 4-8 s and is labeled "Sample AI response".
There is no silent fallback: if a Live call fails, the error is shown.
"""
import json
import os
import random
import re
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DB = "SNOWPACK_SITE_SELECTION"
SCHEMA = f"{DB}.CORE"
SV = f"{SCHEMA}.SITE_SELECTION_SV"
AGENT = f"{SCHEMA}.SITE_SELECTION_AGENT"
MODEL = "claude-sonnet-4-5"
ROLE = "SNOWPACK_SITE_SELECTION_ROLE"
WAREHOUSE = "SNOWPACK_SITE_SELECTION_WH"
AS_OF = "30 Jun 2026"
HERE = Path(__file__).parent
SAMPLE_DIR = HERE / "sample"

C = {  # design tokens (docs/DESIGN.md)
    "indigo950": "#1C1A4A", "indigo800": "#2E2A78", "indigo600": "#4F46C8", "indigo300": "#8E88E8", "indigo50": "#EEF0FB",
    "canvas": "#F4F5FA", "paper": "#FFFFFF", "paper2": "#F8F8FC", "line": "#DCDEEA", "ink": "#16163A", "muted": "#565873",
    "apricot": "#F29A4A", "apricot_ink": "#A44A12", "saturated": "#5E6A85", "good": "#1F7A4D", "bad": "#B23A2E",
}
REGIONS = {"Northeast": "#4F46C8", "West": "#0E7C86", "South": "#B34F12", "Midwest": "#7A6A1F"}
HEAT = ["#EEF0FB", "#B7B4F0", "#6A5FD8", "#2E2A78"]
CAT_SHORT = {"Restaurants & Food Service": "Restaurants", "Clothing & Accessories": "Apparel",
             "Electronics & Appliances": "Electronics", "Food & Beverage Stores": "Grocery",
             "Furniture & Home Furnishings": "Furniture", "Health & Personal Care": "Health"}
CAT_COLORS = {"Grocery": "#2E2A78", "Restaurants": "#4F46C8", "Health": "#0E7C86", "Apparel": "#B34F12",
              "Electronics": "#7A6A1F", "Furniture": "#8A8CA6"}
SATURATED = 0.30
TOP_N = 5
SAMPLE_QUESTIONS = [
    "Which metro and category pairs have the highest white-space opportunity?",
    "Which metros have the most white-space dollars in total, and how covered are they?",
    "Compare average penetration and opportunity score by region.",
]
SCOPES = {
    "national": "National shortlist: top 12 cells by opportunity score",
    "sunbelt": "South and West: top 8 cells in the two leading regions",
}
HEDGE_LINE = "\n\nHouston grocery will likely double its coverage next year and could add around $500M in processed volume."


# ----------------------------------------------------------------------------
# Data layer: one function per op, Live (Snowpark) or Sample (bundled JSON)
# ----------------------------------------------------------------------------
def _sis_session():
    try:
        from snowflake.snowpark.context import get_active_session
        return get_active_session()
    except Exception:
        return None


def _env_ready():
    return all(os.environ.get(k) for k in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PRIVATE_KEY_PATH"))


@st.cache_resource(show_spinner=False)
def _local_session():
    from snowflake.snowpark import Session
    return Session.builder.configs({
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "authenticator": "SNOWFLAKE_JWT",
        "private_key_file": os.path.expanduser(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]),
        "role": os.environ.get("SNOWFLAKE_ROLE", ROLE),
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", WAREHOUSE),
        "database": DB,
        "schema": "CORE",
    }).create()


def live_session():
    return _sis_session() or (_local_session() if _env_ready() else None)


def _rows(sess, q, params=None):
    df = sess.sql(q, params=params or []).to_pandas()
    df.columns = [c.lower() for c in df.columns]
    for c in df.columns:
        if str(df[c].dtype).startswith("datetime"):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
        elif df[c].dtype == object:
            df[c] = df[c].map(lambda v: v.isoformat() if hasattr(v, "isoformat") else (float(v) if hasattr(v, "as_tuple") else v))
    return json.loads(df.to_json(orient="records", date_format="iso"))


def live_cells(sess):
    """One row per metro x category. The semantic view does not allow facts with dimensions, so each
    cell's value is a metric over a single row (SUM / MAX / weighted ratio of one cell = the cell)."""
    return _rows(sess, f"""SELECT * FROM SEMANTIC_VIEW({SV}
        METRICS total_white_space_usd, total_market_usd, total_processed_usd, total_merchants, weighted_penetration,
                max_opportunity_score, avg_demand_growth_pct, avg_merchants_per_100k
        DIMENSIONS metro_id, metro_name, region, category_code, category_name)
        ORDER BY max_opportunity_score DESC, metro_id, category_code""")


def live_metros(sess):
    return _rows(sess, f"""SELECT metro_id, metro_name, state, region, population, median_hh_income, est_business_count,
        latitude, longitude FROM {SCHEMA}.SITE_SELECTION_METRO ORDER BY metro_id""")


def live_regions(sess):
    return _rows(sess, f"""SELECT * FROM SEMANTIC_VIEW({SV}
        METRICS total_white_space_usd, total_market_usd, weighted_penetration, avg_opportunity_score, max_opportunity_score
        DIMENSIONS region) ORDER BY region""")


def live_demand(sess):
    return _rows(sess, f"""SELECT category_code, category_name, month_end, market_sales_usd
        FROM {SCHEMA}.SITE_SELECTION_CATEGORY_DEMAND
        QUALIFY month_end > DATEADD(month, -24, MAX(month_end) OVER (PARTITION BY category_code))
        ORDER BY category_code, month_end""")


def live_source(sess):
    return _rows(sess, f"SELECT mode, note FROM {SCHEMA}.SITE_SELECTION_DATA_SOURCE_INFO")[0]


def live_reports(sess):
    return _rows(sess, f"""SELECT run_id, subject, scope, status, edits_applied, residual_hedges, edits,
        report_md, fact_pack, latency_ms, TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at
        FROM {SCHEMA}.SITE_SELECTION_REPORTS ORDER BY created_at DESC LIMIT 24""")


def live_fact_pack(sess, scope):
    where = "WHERE region IN ('South', 'West')" if scope == "sunbelt" else ""
    limit = 8 if scope == "sunbelt" else 12
    rows = _rows(sess, f"""SELECT metro_name AS metro, region, category_name AS category,
            ROUND(penetration_pct, 3) AS penetration, TO_CHAR(penetration_pct * 100, 'FM990.0') || '%' AS penetration_display,
            category_demand_growth_pct AS demand_growth_pct, 'first to latest of the last 24 months' AS growth_window, opportunity_score,
            ROUND(white_space_volume / 1e9, 2) AS white_space_usd_b, '$' || TO_CHAR(white_space_volume / 1e9, 'FM990.00') || 'B' AS white_space_display,
            ROW_NUMBER() OVER (ORDER BY opportunity_score DESC, white_space_volume DESC) AS rank
        FROM {SCHEMA}.SITE_SELECTION_BENCHMARK {where}
        ORDER BY opportunity_score DESC, white_space_volume DESC LIMIT {limit}""")
    return [{"id": f"F{i + 1}", **r} for i, r in enumerate(rows)]


ALLOWED = ("Allowed and NOT a problem (never flag these): copying the *_display strings; rounding penetration to a whole "
           "percent (24.6% written as 25% is correct); rounding white space to one decimal ($5.50B written as $5.5B); sums or "
           "differences of facts if correct to the nearest 0.1; rank numbers; counts of cells in FACTS; long category names; "
           "and citation tags like [F2].")


def _draft_prompt(scope, fp):
    focus = ("the national shortlist (top 12 cells)" if scope == "national"
             else "the South and West regions only (top 8 cells there)")
    return (
        "You are a payments expansion strategist at a merchant acquirer. Write a concise site-selection note for the expansion "
        f"committee about {focus}, using ONLY the FACTS JSON.\n"
        "DATA RULES: use only numbers in FACTS and copy the *_display values verbatim; opportunity_score blends category demand "
        "growth with the coverage gap (higher = stronger target) and is an index, not dollars; penetration is a ratio (0-1); "
        "demand_growth_pct is category-wide over 24 months; no estimates, forecasts, hedging or outside benchmarks; missing = n/d. "
        + ALLOWED + " After each figure, cite the fact id in square brackets, e.g. [F2]. Do not name any real company, processor or bank.\n"
        "OUTPUT markdown starting with '# ', a one-line takeaway naming the top two targets, a table "
        "(rank | metro | category | penetration | opportunity | white space), 3 bullets (one must note where the biggest "
        "white-space pool is not the top score, if FACTS show it), ending with '## Data Coverage'."
        f"\n\nFACTS: {json.dumps(fp)}"
    )


def _complete(sess, prompt):
    """AI_COMPLETE returns its text as a JSON-encoded string; decode it."""
    raw = sess.sql("SELECT AI_COMPLETE(?, ?)", params=[MODEL, prompt]).collect()[0][0] or ""
    try:
        v = json.loads(raw)
        return v if isinstance(v, str) else raw
    except ValueError:
        return raw


def _last_json(raw):
    """The verifier sometimes re-checks itself and writes several JSON objects; its final one is the verdict."""
    dec, found, i = json.JSONDecoder(), None, raw.find("{")
    while i != -1:
        try:
            obj, end = dec.raw_decode(raw, i)
            if isinstance(obj, dict) and "status" in obj:
                found = obj
            i = raw.find("{", end)
        except ValueError:
            i = raw.find("{", i + 1)
    return found


def _verify(sess, fp, draft):
    vp = (
        "You are a fact-checker. Compare the DRAFT against the FACTS JSON (the only allowed source). " + ALLOWED + " "
        "Flag only numbers or claims that FACTS do not support (including forecasts), and hedge words like "
        "likely/approximately/around/could. Return ONLY a JSON object, no code fences, with keys reason (one sentence), "
        "status ('verified' if nothing is flagged, else 'needs_review'), residual_hedges (int), edits (array of short "
        "strings, one per real problem; never list items you found acceptable; empty if verified).\n\n"
        f"FACTS: {json.dumps(fp)}\n\nDRAFT:\n{draft}"
    )
    v = None
    for _ in range(2):
        v = _last_json(_complete(sess, vp))
        if v is not None:
            break
    if v is None:
        v = {"status": "needs_review", "residual_hedges": None, "edits": ["Verifier output could not be parsed"]}
    v["edits"] = [str(x) for x in (v.get("edits") or [])]
    v["status"] = "verified" if v.get("status") == "verified" and not v["edits"] else "needs_review"
    return v


def live_generate(sess, scope):
    t0 = time.time()
    fp = live_fact_pack(sess, scope)
    t1 = time.time()
    draft = _complete(sess, _draft_prompt(scope, fp)).strip()
    t2 = time.time()
    v = _verify(sess, fp, draft)
    t3 = time.time()
    latency = int((t3 - t0) * 1000)
    sess.sql(
        f"""INSERT INTO {SCHEMA}.SITE_SELECTION_REPORTS (subject, scope, draft_md, report_md, status, edits_applied,
            residual_hedges, edits, fact_pack, latency_ms) SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?""",
        params=[SCOPES[scope].split(":")[0], scope, draft, draft, v["status"], len(v["edits"]), v.get("residual_hedges"),
                json.dumps(v["edits"]), json.dumps(fp), latency],
    ).collect()
    return {"scope": scope, "fact_pack": fp, "draft": draft, "verdict": v, "latency_ms": latency,
            "timings_ms": {"fact_pack": int((t1 - t0) * 1000), "draft": int((t2 - t1) * 1000), "verify": int((t3 - t2) * 1000)}}


def live_reverify(sess, scope, draft):
    t0 = time.time()
    v = _verify(sess, live_fact_pack(sess, scope), draft)
    return {"verdict": v, "latency_ms": int((time.time() - t0) * 1000)}


def live_ask(sess, question):
    t0 = time.time()
    req = json.dumps({"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]})
    raw = sess.sql("SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?)", params=[AGENT, req]).collect()[0][0]
    content = json.loads(raw).get("content", [])
    last_tool = max([i for i, b in enumerate(content) if b.get("type") in ("tool_use", "tool_result")] or [-1])
    text, tables, sql = [], [], []
    for b in content:
        if b.get("type") == "tool_result":
            for part in b["tool_result"].get("content", []):
                if isinstance(part, dict) and isinstance(part.get("json"), dict) and part["json"].get("sql"):
                    sql.append(part["json"]["sql"])
    for b in content[last_tool + 1:]:
        if b.get("type") == "text":
            text.append(b["text"])
        elif b.get("type") == "table":
            rs = b["table"].get("result_set", {})
            cols = [c.get("name") for c in rs.get("resultSetMetaData", {}).get("rowType", [])]
            tables.append({"title": b["table"].get("title", ""), "columns": cols, "rows": rs.get("data", [])})
    if not text and not tables:
        raise RuntimeError("The Cortex Agent returned no answer. Check that sql/setup.sql created SITE_SELECTION_AGENT.")
    return {"question": question, "text": "".join(text).strip(), "tables": tables, "sql": sql[-1] if sql else "",
            "latency_ms": int((time.time() - t0) * 1000)}


LIVE_OPS = {
    "cells": live_cells, "metros": live_metros, "regions": live_regions, "demand": live_demand, "source": live_source,
    "reports": live_reports, "fact_pack": live_fact_pack,
}
LIVE_OPS_AI = {"generate": live_generate, "reverify": live_reverify, "ask": live_ask}


def sample_key(name, *args):
    return "_".join([name] + [re.sub(r"[^a-z0-9]+", "-", str(a).lower()).strip("-")[:40] for a in args])


def load_sample(name, *args):
    p = SAMPLE_DIR / f"{sample_key(name, *args)}.json"
    if not p.exists():
        raise FileNotFoundError(f"No sample file {p.name}. Run scripts/capture_sample.py against a Live setup.")
    return json.loads(p.read_text())


@st.cache_data(ttl=600, show_spinner=False)
def _cached_live(name, *args):
    return LIVE_OPS[name](live_session(), *args)


def op(name, *args):
    if st.session_state.get("mode") == "Live":
        return _cached_live(name, *args)
    return load_sample(name, *args)


# ----------------------------------------------------------------------------
# Formatting and small HTML helpers
# ----------------------------------------------------------------------------
def usd(v):
    v = float(v or 0)
    return f"${v / 1e9:.2f}B" if abs(v) >= 1e9 else f"${v / 1e6:.0f}M" if abs(v) >= 1e6 else f"${v:,.0f}"


def pct(v, d=1):
    return "n/d" if v is None or pd.isna(v) else f"{float(v) * 100:.{d}f}%"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pill(label, kind):
    return f'<span class="ss-pill ss-{kind}">{esc(label)}</span>'


def html(s):
    st.markdown(s, unsafe_allow_html=True)


def kpi_tile(label, value, note, trend=None, count=False):
    arrow = ""
    if trend is not None:
        arrow = f'<span class="ss-trend {"ss-t-good" if trend >= 0 else "ss-t-bad"}">{"&#9650;" if trend >= 0 else "&#9660;"} {esc(trend_label(trend))}</span>'
    if count:  # each digit ticks up from 0, separators stay put
        val = "".join(f'<span class="ss-count" style="--n:{ch}"></span>' if ch.isdigit() else esc(ch) for ch in value)
        val = f'<span aria-label="{esc(value)}">{val}</span>'
    else:
        val = esc(value)
    return (f'<div class="ss-kpi"><div class="ss-kpi-l">{esc(label)}</div><div class="ss-kpi-v">{val}</div>'
            f'<div class="ss-kpi-n">{arrow}<span>{esc(note)}</span></div></div>')


def trend_label(t):
    return f"{abs(t):.1f} pts" if abs(t) < 50 else f"{abs(t):.0f}"


def badge(text):
    html(f'<div class="ss-powered"><span class="ss-dot"></span>{esc(text)}</div>')


def live_error(e):
    st.error(f"Live call failed: {e}", icon=":material/error:")
    st.caption("Live mode never falls back to sample data. Check that sql/setup.sql ran and the key-pair settings "
               "in the README are set, or switch to Sample.")
    st.stop()


def guarded(name, *args):
    try:
        return op(name, *args)
    except FileNotFoundError as e:
        st.warning(str(e))
        st.stop()
    except Exception as e:  # noqa: BLE001 - shown to the reader, never swallowed
        live_error(e)


def chart_config(ch):
    return (ch.configure(font="-apple-system, Segoe UI, Roboto, sans-serif", background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=C["muted"], titleColor=C["muted"], gridColor=C["line"], domainColor=C["line"],
                            tickColor=C["line"], labelFontSize=11, titleFontSize=11, titleFontWeight=500)
            .configure_legend(orient="top", labelColor=C["ink"], titleColor=C["muted"], labelFontSize=11, symbolSize=80,
                              titleFontSize=11)
            .configure_title(color=C["ink"], fontSize=13, anchor="start"))


def stream_words(text, wps=60):
    for tok in re.split(r"(\s+)", text):
        yield tok
        if tok.strip():
            time.sleep(1 / wps)


def ai_label(latency_ms=None):
    if st.session_state.get("mode") == "Live":
        tail = f" · {latency_ms / 1000:.1f} s measured" if latency_ms else ""
        html(f'<div class="ss-ai-label ss-ai-live">Live Cortex AI response{tail}</div>')
    else:
        html('<div class="ss-ai-label">Sample AI response · captured from a Live run, replayed with a simulated delay</div>')


def staged(steps, total_s=None):
    """Staged progress. Sample: spread a 4-8 s delay over the steps. Live: the caller runs the real call."""
    box = st.status(steps[0], expanded=True)
    if total_s is None:
        for s in steps:
            box.write(f":material/progress_activity: {s}")
        return box
    per = total_s / len(steps)
    for s in steps:
        box.update(label=s)
        box.write(f":material/progress_activity: {s}")
        time.sleep(per * random.uniform(0.85, 1.15))
    return box


# ----------------------------------------------------------------------------
# Theme (CSS on top of .streamlit/config.toml; also works when pasted into Snowsight)
# ----------------------------------------------------------------------------
CSS = """
<style>
@font-face{font-family:Figtree;src:url(app/static/Figtree.woff2) format("woff2");font-weight:300 900;font-display:swap}
:root{--i950:#1C1A4A;--i800:#2E2A78;--i600:#4F46C8;--i300:#8E88E8;--i50:#EEF0FB;--canvas:#F4F5FA;--paper:#FFFFFF;--paper2:#F8F8FC;
--line:#DCDEEA;--ink:#16163A;--muted:#565873;--apr:#F29A4A;--aprink:#A44A12;--apr50:#FDEBDD;--sat:#5E6A85;--good:#1F7A4D;--bad:#B23A2E}
html{overflow-x:clip}
.stApp{background:var(--canvas)}
section[data-testid="stSidebar"]{background:var(--i950)!important;border-right:0}
section[data-testid="stSidebar"] *{color:#C9C7F2}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]{border-radius:10px;margin:2px 0}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover{background:#26235F!important}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"]{background:var(--i800)!important;box-shadow:inset 3px 0 0 var(--apr)}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] span{color:#FFFFFF!important;font-weight:650}
section[data-testid="stSidebar"] svg{fill:#C9C7F2}
[data-testid="stSidebarHeader"] img, [data-testid="stLogo"]{height:30px!important;max-height:30px!important}
.ss-side-foot{font-size:.72rem;line-height:1.45;color:#C9C7F2;border-top:1px solid #34316F;padding-top:.7rem;margin-top:.6rem}
header[data-testid="stHeader"]{background:transparent}
.block-container{padding-top:2.2rem;max-width:1280px}
h1,h2,h3,.ss-kpi-v,.ss-h{font-family:Figtree,-apple-system,"Segoe UI",sans-serif;letter-spacing:-.01em}
h1{font-size:1.55rem!important;font-weight:750!important;color:var(--ink)}
h3{font-size:1.0rem!important;font-weight:700!important;color:var(--ink)}
.ss-ctx{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center;margin:.1rem 0 .2rem}
.ss-chip{display:inline-flex;align-items:center;gap:.4rem;background:var(--paper);border:1px solid var(--line);border-radius:999px;
padding:.22rem .7rem;font-size:.78rem;color:var(--ink);max-width:100%}
.ss-avatar{width:20px;height:20px;border-radius:50%;background:var(--i800);color:#fff;font-size:.62rem;display:inline-grid;place-items:center;font-weight:700}
.ss-env{font-weight:750;letter-spacing:.05em;text-transform:uppercase;font-size:.68rem;border-radius:999px;padding:.25rem .6rem}
.ss-env-sample{background:#FFF2D6;color:#7A5200;border:1px solid #E9C979}
.ss-env-live{background:#E1F2E8;color:var(--good);border:1px solid #9FD3B6}
.ss-sub{color:var(--muted);font-size:.9rem;margin:-.35rem 0 .8rem}
.ss-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.7rem;margin:.3rem 0 .9rem}
.ss-kpi{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:.8rem .9rem;min-width:0;position:relative;overflow:hidden;
animation:ssUp .2s ease-out backwards;transition:box-shadow .15s,transform .15s}
.ss-kpi::before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:linear-gradient(var(--i600),var(--apr))}
.ss-kpi:hover{box-shadow:0 8px 22px rgba(28,26,74,.09);transform:translateY(-1px)}
.ss-kpi:nth-child(2){animation-delay:.04s}.ss-kpi:nth-child(3){animation-delay:.08s}.ss-kpi:nth-child(4){animation-delay:.12s}.ss-kpi:nth-child(5){animation-delay:.16s}
.ss-kpi-l{font-size:.72rem;color:var(--muted);font-weight:650;text-transform:uppercase;letter-spacing:.05em}
.ss-kpi-v{font-size:1.5rem;font-weight:750;color:var(--ink);margin-top:.15rem;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ss-kpi-n{font-size:.75rem;color:var(--muted);margin-top:.15rem;display:flex;gap:.35rem;flex-wrap:wrap}
.ss-trend{font-weight:700}.ss-t-good{color:var(--good)}.ss-t-bad{color:var(--bad)}
@keyframes ssUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@property --n{syntax:"<integer>";initial-value:0;inherits:false}
.ss-count{--n:0;counter-reset:n var(--n);animation:ssCount .9s ease-out backwards}
.ss-count::after{content:counter(n)}
@keyframes ssCount{from{--n:0}}
.ss-pill{display:inline-block;font-size:.72rem;font-weight:650;border-radius:999px;padding:.12rem .55rem;white-space:nowrap}
.ss-target{background:var(--apr50);color:var(--aprink)}.ss-sat{background:#ECEEF3;color:var(--sat)}
.ss-flat{background:#F8E3E0;color:var(--bad)}.ss-watch{background:var(--i50);color:var(--i600)}
.ss-good{background:#E1F2E8;color:var(--good)}.ss-bad{background:#F8E3E0;color:var(--bad)}
.ss-powered{display:inline-flex;align-items:center;gap:.4rem;font-size:.72rem;color:var(--i600);background:var(--i50);border-radius:999px;
padding:.18rem .6rem;font-weight:650;max-width:100%;flex-wrap:wrap;margin-bottom:.3rem}
.ss-dot{width:7px;height:7px;border-radius:50%;background:var(--i600);box-shadow:0 0 0 3px rgba(79,70,200,.18)}
.ss-insight{border-left:3px solid var(--line);padding:.5rem .75rem;margin:.4rem 0;background:var(--paper2);border-radius:0 10px 10px 0;font-size:.86rem;color:var(--ink)}
.ss-insight b{font-family:Figtree,sans-serif}
.ss-i-target{border-left-color:var(--apr)}.ss-i-sat{border-left-color:var(--sat)}.ss-i-flat{border-left-color:var(--bad)}.ss-i-ai{border-left-color:var(--i600)}
[class*="st-key-card"]{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:1rem 1.05rem;min-width:0;
animation:ssUp .2s ease-out backwards}
.ss-skel{background:linear-gradient(90deg,#E6E8F3 25%,#F3F4FA 37%,#E6E8F3 63%);background-size:400% 100%;animation:ssShim 1.3s ease infinite;border-radius:12px;margin:.4rem 0}
@keyframes ssShim{0%{background-position:100% 50%}100%{background-position:0 50%}}
.ss-ai-label{display:inline-block;font-size:.72rem;font-weight:700;color:#7A5200;background:#FFF2D6;border:1px solid #E9C979;border-radius:6px;padding:.15rem .5rem;margin:.2rem 0 .5rem}
.ss-ai-live{color:var(--good);background:#E1F2E8;border-color:#9FD3B6}
.ss-stamp{display:inline-block;font-family:Figtree,sans-serif;font-weight:800;letter-spacing:.08em;text-transform:uppercase;font-size:.82rem;
border:2.5px solid currentColor;border-radius:8px;padding:.25rem .7rem;animation:ssStamp .35s cubic-bezier(.2,1.6,.4,1) backwards}
.ss-stamp-ok{color:var(--good)}.ss-stamp-bad{color:var(--bad)}
@keyframes ssStamp{from{transform:scale(1.6);opacity:0}}
.ss-docket{background:var(--paper);border:1px solid var(--line);border-top:3px solid var(--good);border-radius:12px;padding:.75rem .9rem;margin-bottom:.4rem}
.ss-docket.bad{border-top-color:var(--bad)}
.ss-docket .t{font-family:Figtree,sans-serif;font-weight:700;font-size:.92rem;margin:.3rem 0}
.ss-docket .s{color:var(--muted);font-size:.76rem}
.ss-table{width:100%;border-collapse:collapse;font-size:.82rem;font-variant-numeric:tabular-nums}
.ss-table th{background:var(--paper2);color:var(--muted);font-weight:650;text-align:left;padding:.42rem .5rem;border-bottom:1px solid var(--line);white-space:nowrap}
.ss-table td{padding:.4rem .5rem;border-bottom:1px solid #E9EAF2;white-space:nowrap}
.ss-table td.n,.ss-table th.n{text-align:right}
.ss-scroll{position:relative;overflow-x:auto;max-width:100%}
.ss-empty{border:1.5px dashed var(--line);border-radius:12px;padding:1.6rem;text-align:center;color:var(--muted);background:var(--paper)}
.ss-note-md{font-size:.92rem;color:var(--ink)}.ss-note-md p{margin:.35rem 0}.ss-note-md ul{margin:.3rem 0 .5rem 1.1rem;padding:0}
.ss-md-h1{font-family:Figtree,sans-serif;font-weight:750;font-size:1.2rem;margin:.2rem 0 .5rem}
.ss-md-h2,.ss-md-h3{font-family:Figtree,sans-serif;font-weight:700;font-size:.98rem;margin:.9rem 0 .35rem}
.ss-md td,.ss-md th{white-space:normal}
.ss-cite{font-size:.68rem;font-weight:700;color:var(--i600);background:var(--i50);border-radius:4px;padding:0 .25rem;margin-left:.1rem}
.stButton button[kind="primary"]{background:var(--i600);border-color:var(--i600)}
.stButton button[kind="primary"]:hover{background:var(--i800);border-color:var(--i800)}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:10px}
[data-testid="stDialog"] [role="dialog"]{border-radius:14px}
@media (max-width:900px){.ss-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.block-container{padding-left:.8rem;padding-right:.8rem}}
@media (max-width:480px){.ss-kpi-v{font-size:1.2rem}.ss-chip{font-size:.72rem}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>
"""


def _inline(t):
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"\[(F\d+(?:\s*,\s*F\d+)*)\]",
                  lambda m: "".join(f'<span class="ss-cite">{x}</span>' for x in re.split(r"\s*,\s*", m.group(1))), t)


def cite(md):
    """Render the note's markdown (headings, tables, bullets, bold, [F#] citations) to HTML by hand,
    so citation chips survive inside tables and "$" is never read as math."""
    lines, out, i = esc(md).replace("$", "&#36;").split("\n"), [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[\s:|-]+\|?$", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            body = "".join("<tr>" + "".join(f"<{'th' if j == 0 else 'td'}>{_inline(c)}</{'th' if j == 0 else 'td'}>" for c in r) + "</tr>"
                           for j, r in enumerate(rows))
            out.append(f'<div class="ss-scroll"><table class="ss-table ss-md">{body}</table></div>')
            continue
        if re.match(r"^[-*] ", ln):
            items = []
            while i < len(lines) and re.match(r"^[-*] ", lines[i]):
                items.append(f"<li>{_inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        h = re.match(r"^(#{1,3}) (.*)$", ln)
        if h:
            out.append(f'<div class="ss-md-h{len(h.group(1))}">{_inline(h.group(2))}</div>')
        elif ln.strip():
            out.append(f"<p>{_inline(ln)}</p>")
        i += 1
    return '<div class="ss-note-md">' + "".join(out) + "</div>"


# ----------------------------------------------------------------------------
# Shared frames
# ----------------------------------------------------------------------------
def cells_df():
    df = pd.DataFrame(guarded("cells")).rename(columns={
        "total_white_space_usd": "white_space", "total_market_usd": "market", "total_processed_usd": "processed",
        "total_merchants": "merchants", "weighted_penetration": "penetration", "max_opportunity_score": "score",
        "avg_demand_growth_pct": "growth", "avg_merchants_per_100k": "per_100k"})
    df["category"] = df.category_name.map(CAT_SHORT)
    df = df.sort_values(["score", "white_space"], ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    df["status"] = df.apply(status_of, axis=1)
    return df


def status_of(r):
    if r.growth <= 0:
        return "No demand growth"
    if r.penetration >= SATURATED:
        return "Saturated"
    if r["rank"] <= TOP_N:
        return "Top target"
    return "Watch"


STATUS_PILL = {"Top target": "target", "Saturated": "sat", "No demand growth": "flat", "Watch": "watch"}


def metros_df():
    return pd.DataFrame(guarded("metros"))


def dotmap():
    return pd.DataFrame(json.loads((HERE / "static" / "dotmap.json").read_text()), columns=["longitude", "latitude"])


LABEL_DX = {"Philadelphia": -1, "Miami": -1}


def map_chart(cells, metros, height=470, highlight=None):
    """Dot-map of the contiguous US (scripts/make_dotmap.py) with metros sized by white space."""
    agg = cells.groupby("metro_id", as_index=False).agg(white_space=("white_space", "sum"), best=("score", "max"),
                                                       top=("rank", "min"))
    m = metros.merge(agg, on="metro_id")
    best_cat = cells.sort_values("rank").drop_duplicates("metro_id").set_index("metro_id")["category"]
    m["best_cat"] = m.metro_id.map(best_cat)
    m["ws_b"] = m.white_space / 1e9
    m["target"] = m.top <= TOP_N
    if highlight:
        m["target"] = m.metro_id == highlight
    x = alt.X("longitude:Q", scale=alt.Scale(domain=[-125, -66.5]), axis=None)
    y = alt.Y("latitude:Q", scale=alt.Scale(domain=[24.3, 49.5]), axis=None)
    m["dx"] = m.metro_name.map(LABEL_DX).fillna(10)
    m["align"] = m.dx.map(lambda v: "right" if v < 0 else "left")
    land = alt.Chart(dotmap()).mark_circle(size=26, color="#CFCDF3", opacity=.95).encode(x=x, y=y)
    ring = alt.Chart(m[m.target]).mark_circle(filled=False, stroke=C["apricot"], strokeWidth=3.5, opacity=1).encode(
        x=x, y=y, size=alt.Size("ws_b:Q", scale=alt.Scale(range=[520, 3400], domain=[0, m.ws_b.max()]), legend=None))
    bub = alt.Chart(m).mark_circle(opacity=.9, stroke="#FFFFFF", strokeWidth=1.2).encode(
        x=x, y=y,
        size=alt.Size("ws_b:Q", scale=alt.Scale(range=[120, 1900], domain=[0, m.ws_b.max()]), title="White space ($B)"),
        color=alt.Color("region:N", scale=alt.Scale(domain=list(REGIONS), range=list(REGIONS.values())), title="Region"),
        tooltip=[alt.Tooltip("metro_name:N", title="Metro"), alt.Tooltip("region:N", title="Region"),
                 alt.Tooltip("ws_b:Q", format="$.2f", title="White space ($B)"), alt.Tooltip("best_cat:N", title="Best category"),
                 alt.Tooltip("best:Q", format=".2f", title="Best opportunity score"), alt.Tooltip("top:Q", title="Best rank")])
    lbl_r = alt.Chart(m[m.dx > 0]).mark_text(align="left", dx=14, dy=-12, fontSize=11.5, fontWeight=600, color=C["ink"]).encode(
        x=x, y=y, text="metro_name:N")
    lbl_l = alt.Chart(m[m.dx < 0]).mark_text(align="right", dx=-14, dy=12, fontSize=11.5, fontWeight=600, color=C["ink"]).encode(
        x=x, y=y, text="metro_name:N")
    return alt.layer(land, bub, ring, lbl_r, lbl_l).properties(height=height)


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------
def page_overview():
    st.title("Expansion overview")
    html(f'<p class="ss-sub">Corvane Payments coverage in 10 metros × 6 merchant categories, against 24 months of category '
         f'demand to {AS_OF}. Opportunity score = demand growth % × (1 − penetration).</p>')
    df = cells_df()
    top = df.iloc[0]
    growth = df.groupby("category", as_index=False).growth.max().sort_values("growth", ascending=False)
    pen = df.processed.sum() / df.market.sum()
    ranked = int((df.score > 0).sum())
    html('<div class="ss-kpis">' + "".join([
        kpi_tile("White space", usd(df.white_space.sum()), f"{usd(df.market.sum())} est. market"),
        kpi_tile("Penetration", pct(pen), "volume-weighted, all cells"),
        kpi_tile("Top target", top.metro_name, f"{top.category} · score {top.score:.2f} · {pct(top.penetration)} covered"),
        kpi_tile("Fastest category", growth.iloc[0].category, f"+{growth.iloc[0].growth:.2f}% demand in 24 months"),
        kpi_tile("Cells ranked", f"{ranked} of {len(df)}", f"{len(df) - ranked} with no demand growth", count=False),
    ]) + "</div>")

    left, right = st.columns([2.1, 1], gap="medium")
    with left.container(key="card_heat"):
        st.markdown("### Opportunity score by metro and category")
        badge("Semantic View SITE_SELECTION_SV · SEMANTIC_VIEW() query")
        order_m = df.groupby("metro_name").score.max().sort_values(ascending=False).index.tolist()
        order_c = growth.category.tolist()
        base = alt.Chart(df).encode(
            x=alt.X("category:N", sort=order_c, title=None, axis=alt.Axis(labelAngle=0, orient="top")),
            y=alt.Y("metro_name:N", sort=order_m, title=None, axis=alt.Axis(labelLimit=160)))
        rect = base.mark_rect(cornerRadius=4, stroke="#FFFFFF", strokeWidth=2).encode(
            color=alt.Color("score:Q", scale=alt.Scale(range=HEAT), legend=alt.Legend(title="Score", orient="right")),
            tooltip=[alt.Tooltip("metro_name:N", title="Metro"), alt.Tooltip("category_name:N", title="Category"),
                     alt.Tooltip("score:Q", format=".2f", title="Opportunity"), alt.Tooltip("penetration:Q", format=".1%", title="Penetration"),
                     alt.Tooltip("growth:Q", format=".2f", title="Demand growth %"),
                     alt.Tooltip("white_space:Q", format="$,.0f", title="White space"), alt.Tooltip("rank:Q", title="Rank")])
        txt = base.mark_text(fontSize=11, fontWeight=600).encode(
            text=alt.Text("score:Q", format=".1f"),
            color=alt.condition(alt.datum.score > 6, alt.value("#FFFFFF"), alt.value(C["ink"])))
        st.altair_chart(chart_config(alt.layer(rect, txt).properties(height=330)), width="stretch")
        st.caption("Furniture scores 0 in every metro: its demand did not grow, so its white space is not a target.")
    with right.container(key="card_insights"):
        st.markdown("### What stands out")
        sat = df[df.status == "Saturated"]
        big = df.sort_values("white_space", ascending=False).iloc[0]
        furn = df[df.category == "Furniture"]
        top12 = df.head(12).region.value_counts()
        html(
            f'<div class="ss-insight ss-i-target"><b>{esc(top.metro_name)} {esc(top.category.lower())} leads.</b> {pct(top.penetration)} covered '
            f'in the fastest-growing category (+{top.growth:.2f}%), {usd(top.white_space)} of white space, score {top.score:.2f}.</div>'
            f'<div class="ss-insight ss-i-target"><b>Runner-up: {esc(df.iloc[1].metro_name)} {esc(df.iloc[1].category.lower())}</b> at '
            f'{pct(df.iloc[1].penetration)} covered, score {df.iloc[1].score:.2f}.</div>'
            f'<div class="ss-insight ss-i-ai"><b>Biggest pool is not the top score.</b> {esc(big.metro_name)} {esc(big.category.lower())} '
            f'holds {usd(big.white_space)} but ranks #{int(big["rank"])}.</div>'
            + (f'<div class="ss-insight ss-i-sat"><b>{esc(sat.iloc[0].metro_name)} {esc(sat.iloc[0].category.lower())} is saturated</b> at '
               f'{pct(sat.iloc[0].penetration)} penetration.</div>' if not sat.empty else "")
            + f'<div class="ss-insight ss-i-flat"><b>Flat demand scores zero.</b> Furniture has {usd(furn.white_space.sum())} of white '
            f'space and no growth.</div>'
            f'<div class="ss-insight"><b>Top 12 by region:</b> ' + ", ".join(f"{k} {v}" for k, v in top12.items()) + "</div>")
        st.page_link(PAGES["notes"], label="Write a verified expansion note", icon=":material/edit_note:")

    with st.container(key="card_demand"):
        st.markdown("### Category demand, last 24 months")
        dm = pd.DataFrame(guarded("demand"))
        dm["category"] = dm.category_name.map(CAT_SHORT)
        dm["month"] = pd.to_datetime(dm.month_end).dt.to_period("M").dt.to_timestamp()
        first = dm.sort_values("month").groupby("category").market_sales_usd.transform("first")
        dm["index"] = dm.market_sales_usd / first * 100
        bands = pd.DataFrame({"start": pd.to_datetime(["2024-10-16", "2025-10-16"]), "end": pd.to_datetime(["2024-12-16", "2025-12-16"])})
        x = alt.X("month:T", title=None, axis=alt.Axis(format="%b %y", labelAngle=0, tickCount=8))
        band = alt.Chart(bands).mark_rect(color="#FDEBDD", opacity=.7).encode(x="start:T", x2="end:T")
        line = alt.Chart(dm).mark_line(strokeWidth=2.2, interpolate="monotone").encode(
            x=x, y=alt.Y("index:Q", title="Demand index (first month = 100)", scale=alt.Scale(zero=False)),
            color=alt.Color("category:N", scale=alt.Scale(domain=list(CAT_COLORS), range=list(CAT_COLORS.values())), title=None),
            tooltip=[alt.Tooltip("month:T", format="%b %Y", title="Month"), "category:N",
                     alt.Tooltip("market_sales_usd:Q", format="$,.0f", title="Category sales"), alt.Tooltip("index:Q", format=".1f", title="Index")])
        st.altair_chart(chart_config(alt.layer(band, line).properties(height=250)), width="stretch")
        src = guarded("source")
        st.caption(f"Shaded: November–December. Data mode: {src['mode']}. {src['note']}")


@st.dialog("Metro", width="large")
def metro_drawer(mid):
    df, metros = cells_df(), metros_df()
    m = metros[metros.metro_id == mid].iloc[0]
    c = df[df.metro_id == mid].sort_values("score", ascending=False)
    best = c.iloc[0]
    html(f'<h3 class="ss-h" style="margin:0">{esc(m.metro_name)}, {esc(m.state)}</h3>'
         f'<div class="ss-ctx" style="margin:.4rem 0 .6rem">{pill(m.region, "watch")} '
         f'{pill(f"Best: {best.category} #{int(best["rank"])}", STATUS_PILL[best.status])}</div>')
    html('<div class="ss-kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))">' + "".join([
        kpi_tile("Population", f"{int(m.population):,}", "synthetic sizing"),
        kpi_tile("Median income", f"${int(m.median_hh_income):,}", "household"),
        kpi_tile("White space", usd(c.white_space.sum()), "all 6 categories"),
        kpi_tile("Penetration", pct(c.processed.sum() / c.market.sum()), f"{int(c.merchants.sum()):,} merchants today")]) + "</div>")
    ch = alt.Chart(c).mark_bar(cornerRadiusEnd=4, height=18).encode(
        y=alt.Y("category:N", sort="-x", title=None),
        x=alt.X("score:Q", title="Opportunity score"),
        color=alt.condition(alt.datum.status == "Top target", alt.value(C["apricot"]), alt.value(C["indigo600"])),
        tooltip=[alt.Tooltip("category_name:N", title="Category"), alt.Tooltip("score:Q", format=".2f", title="Score"),
                 alt.Tooltip("penetration:Q", format=".1%", title="Penetration"), alt.Tooltip("white_space:Q", format="$,.0f", title="White space")])
    st.altair_chart(chart_config(ch.properties(height=210, title="Opportunity by category")), width="stretch")
    rows = "".join(
        f'<tr><td>{esc(r.category)}</td><td class="n">{pct(r.penetration)}</td><td class="n">{r.growth:.2f}%</td>'
        f'<td class="n">{r.score:.2f}</td><td class="n">{usd(r.white_space)}</td><td class="n">{int(r.merchants):,}</td>'
        f'<td>{pill(r.status, STATUS_PILL[r.status])}</td></tr>' for r in c.itertuples())
    html('<div class="ss-scroll"><table class="ss-table"><tr><th>Category</th><th class="n">Penetration</th><th class="n">Demand growth</th>'
         f'<th class="n">Score</th><th class="n">White space</th><th class="n">Merchants</th><th>Status</th></tr>{rows}</table></div>')
    badge("Semantic View SITE_SELECTION_SV · metro sizing from SITE_SELECTION_METRO")


def page_map():
    st.title("Market map")
    html('<p class="ss-sub">Each metro sized by its white-space dollars across the six categories, colored by region. '
         'Apricot rings mark the metros that hold a top-5 cell. Select a metro below for its category breakdown.</p>')
    df, metros = cells_df(), metros_df()
    with st.container(key="card_map"):
        st.altair_chart(chart_config(map_chart(df, metros)), width="stretch")
        st.caption("Positions are city-centre longitude/latitude on a dot grid of the contiguous US. Metro sizing is synthetic.")
    regions = pd.DataFrame(guarded("regions"))
    with st.container(key="card_regions"):
        st.markdown("### Regions")
        badge("SEMANTIC_VIEW(SITE_SELECTION_SV) · metrics by region")
        rg = regions.sort_values("total_white_space_usd", ascending=False)
        rows = "".join(f'<tr><td><span class="ss-dot" style="background:{REGIONS[r.region]};box-shadow:none;display:inline-block;margin-right:.4rem"></span>{esc(r.region)}</td>'
                       f'<td class="n">{usd(r.total_white_space_usd)}</td><td class="n">{pct(r.weighted_penetration)}</td>'
                       f'<td class="n">{r.avg_opportunity_score:.2f}</td><td class="n">{r.max_opportunity_score:.2f}</td></tr>' for r in rg.itertuples())
        html('<div class="ss-scroll"><table class="ss-table"><tr><th>Region</th><th class="n">White space</th><th class="n">Penetration</th>'
             f'<th class="n">Avg score</th><th class="n">Best score</th></tr>{rows}</table></div>')
    g = df.groupby(["metro_id", "metro_name", "region"], as_index=False).agg(
        white_space=("white_space", "sum"), market=("market", "sum"), processed=("processed", "sum"),
        merchants=("merchants", "sum"), best=("score", "max"), top=("rank", "min"))
    g["pen"] = g.processed / g.market * 100
    g["ws_b"] = g.white_space / 1e9
    g["best_cat"] = g.metro_id.map(df.sort_values("rank").drop_duplicates("metro_id").set_index("metro_id")["category"])
    g = g.sort_values("top").reset_index(drop=True)
    with st.container(key="card_metros"):
        st.markdown("### Metros")
        ev = st.dataframe(
            g[["metro_name", "region", "ws_b", "pen", "merchants", "best_cat", "best", "top"]],
            hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="metro_grid",
            column_config={
                "metro_name": "Metro", "region": "Region",
                "ws_b": st.column_config.NumberColumn("White space", format="$%.2fB"),
                "pen": st.column_config.ProgressColumn("Penetration", min_value=0, max_value=50, format="%.1f%%"),
                "merchants": st.column_config.NumberColumn("Merchants", format="localized"),
                "best_cat": "Best category", "best": st.column_config.NumberColumn("Best score", format="%.2f"),
                "top": st.column_config.NumberColumn("Best rank", format="#%d"),
            })
    sel = ev.selection.rows if ev else []
    pick = g.iloc[sel[0]].metro_id if sel else None
    if pick and st.session_state.get("_metro_open") != pick:
        st.session_state["_metro_open"] = pick
        metro_drawer(pick)
    elif not pick:
        st.session_state["_metro_open"] = None


@st.dialog("Expansion cell", width="large")
def cell_drawer(metro_id, category):
    df = cells_df()
    r = df[(df.metro_id == metro_id) & (df.category == category)].iloc[0]
    peers = df[df.category == category].sort_values("penetration")
    html(f'<h3 class="ss-h" style="margin:0">#{int(r["rank"])} · {esc(r.metro_name)} · {esc(r.category_name)}</h3>'
         f'<div class="ss-ctx" style="margin:.4rem 0 .6rem">{pill(r.status, STATUS_PILL[r.status])} {pill(r.region, "watch")}</div>')
    html('<div class="ss-kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))">' + "".join([
        kpi_tile("Opportunity", f"{r.score:.2f}", f"rank {int(r['rank'])} of {len(df)}"),
        kpi_tile("Penetration", pct(r.penetration), f"category avg {pct(peers.processed.sum() / peers.market.sum())}"),
        kpi_tile("Demand growth", f"{r.growth:.2f}%", "category, 24 months"),
        kpi_tile("White space", usd(r.white_space), f"{usd(r.market)} est. market")]) + "</div>")
    ch = alt.Chart(peers).mark_bar(cornerRadiusEnd=4, height=16).encode(
        y=alt.Y("metro_name:N", sort=peers.metro_name.tolist(), title=None),
        x=alt.X("penetration:Q", title="Penetration", axis=alt.Axis(format="%")),
        color=alt.condition(alt.datum.metro_id == metro_id, alt.value(C["apricot"]), alt.value("#B7B4F0")),
        tooltip=[alt.Tooltip("metro_name:N", title="Metro"), alt.Tooltip("penetration:Q", format=".1%"),
                 alt.Tooltip("score:Q", format=".2f", title="Score")])
    st.altair_chart(chart_config(ch.properties(height=260, title=f"{category} penetration in every metro")), width="stretch")
    gap = (1 - r.penetration)
    html(f'<div class="ss-insight ss-i-ai">Score check: {r.growth:.2f}% growth × (1 − {r.penetration:.3f}) = <b>{r.growth * gap:.2f}</b>. '
         f'{int(r.merchants):,} merchants processed {usd(r.processed)} of an estimated {usd(r.market)}.</div>')
    badge("Semantic View SITE_SELECTION_SV")


def page_ranking():
    st.title("Opportunity ranking")
    html('<p class="ss-sub">All 60 metro × category cells. Top-right of the scatter is where demand is growing and coverage '
         'is thin. Filter, sort any column, and select a row to open the cell.</p>')
    df = cells_df()
    c1, c2, c3 = st.columns([1.5, 2.1, 1.1])
    regs = c1.pills("Region", list(REGIONS), selection_mode="multi", default=list(REGIONS))
    cats = c2.pills("Category", list(CAT_COLORS), selection_mode="multi", default=list(CAT_COLORS))
    q = c3.text_input("Search", placeholder="e.g. Houston, saturated")
    f = df[df.region.isin(regs or []) & df.category.isin(cats or [])]
    if q:
        f = f[f.apply(lambda r: q.lower() in f"{r.metro_name} {r.category_name} {r.status} {r.region}".lower(), axis=1)]
    if f.empty:
        html('<div class="ss-empty">No cells match these filters. Clear a filter or the search box.</div>')
        return
    with st.container(key="card_scatter"):
        st.markdown("### Penetration vs demand growth")
        quad = pd.DataFrame({"x": [0], "x2": [0.15], "y": [7.5], "y2": [11]})
        shade = alt.Chart(quad).mark_rect(color="#FDEBDD", opacity=.6).encode(x="x:Q", x2="x2:Q", y="y:Q", y2="y2:Q")
        shade_t = alt.Chart(pd.DataFrame({"x": [0.004], "y": [7.6], "t": ["Growing and under-covered"]})).mark_text(
            align="left", baseline="bottom", color=C["apricot_ink"], fontSize=11, fontWeight=700).encode(x="x:Q", y="y:Q", text="t:N")
        pts = alt.Chart(f.assign(ws_b=f.white_space / 1e9)).mark_circle(opacity=.85, stroke="#FFFFFF", strokeWidth=1).encode(
            x=alt.X("penetration:Q", title="Penetration", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, .5])),
            y=alt.Y("growth:Q", title="Category demand growth (%)", scale=alt.Scale(domain=[-0.5, 11])),
            size=alt.Size("ws_b:Q", title="White space ($B)", scale=alt.Scale(range=[40, 1100])),
            color=alt.Color("region:N", scale=alt.Scale(domain=list(REGIONS), range=list(REGIONS.values())), title="Region"),
            tooltip=[alt.Tooltip("metro_name:N", title="Metro"), alt.Tooltip("category_name:N", title="Category"),
                     alt.Tooltip("penetration:Q", format=".1%"), alt.Tooltip("growth:Q", format=".2f", title="Growth %"),
                     alt.Tooltip("score:Q", format=".2f", title="Score"), alt.Tooltip("ws_b:Q", format="$.2f", title="White space ($B)"),
                     alt.Tooltip("rank:Q", title="Rank")])
        st.altair_chart(chart_config(alt.layer(shade, shade_t, pts).properties(height=300)), width="stretch")
    g = f.assign(pen=f.penetration * 100, ws_b=f.white_space / 1e9, label=f.status.map(lambda s: "● " + s))
    with st.container(key="card_rank"):
        badge(f"{len(f)} of {len(df)} cells · rows from SEMANTIC_VIEW(SITE_SELECTION_SV)")
        ev = st.dataframe(
            g[["rank", "metro_name", "region", "category", "pen", "growth", "score", "ws_b", "merchants", "label"]],
            hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="rank_grid",
            column_config={
                "rank": st.column_config.NumberColumn("Rank", format="#%d", width="small"),
                "metro_name": "Metro", "region": "Region", "category": "Category",
                "pen": st.column_config.ProgressColumn("Penetration", min_value=0, max_value=50, format="%.1f%%"),
                "growth": st.column_config.NumberColumn("Demand growth", format="%.2f%%"),
                "score": st.column_config.NumberColumn("Opportunity", format="%.2f"),
                "ws_b": st.column_config.NumberColumn("White space", format="$%.2fB"),
                "merchants": st.column_config.NumberColumn("Merchants", format="localized"),
                "label": st.column_config.TextColumn("Status"),
            })
    sel = ev.selection.rows if ev else []
    pick = (g.iloc[sel[0]].metro_id, g.iloc[sel[0]].category) if sel else None
    if pick and st.session_state.get("_cell_open") != pick:
        st.session_state["_cell_open"] = pick
        cell_drawer(*pick)
    elif not pick:
        st.session_state["_cell_open"] = None


def note_view(res):
    v = res["verdict"]
    ok = v["status"] == "verified"
    html(f'<div style="margin:.3rem 0 .6rem"><span class="ss-stamp {"ss-stamp-ok" if ok else "ss-stamp-bad"}">'
         f'{"Verified" if ok else "Needs review"}</span>'
         f'<span style="margin-left:.8rem;font-size:.8rem;color:{C["muted"]}">residual hedges: {v.get("residual_hedges")} · '
         f'flagged: {len(v["edits"])}</span></div>')
    if v["edits"]:
        html('<div class="ss-insight ss-i-flat"><b>Verifier flags</b><ul style="margin:.2rem 0 0 1rem;padding:0">'
             + "".join(f"<li>{esc(e)}</li>" for e in v["edits"]) + "</ul></div>")


def run_note(scope):
    fp_preview = guarded("fact_pack", scope)
    steps = ["Reading 60 metro × category cells through SITE_SELECTION_SV…",
             f"Ranking by opportunity score and building the fact pack: {len(fp_preview)} cells, the note's only allowed numbers…",
             f"Drafting the expansion note with AI_COMPLETE ({MODEL})…",
             "Verifying every figure against the fact pack and checking for hedges…",
             "Saving the note and verdict to SITE_SELECTION_REPORTS…"]
    if st.session_state.mode == "Live":
        box = staged(steps)
        try:
            res = LIVE_OPS_AI["generate"](live_session(), scope)
        except Exception as e:  # noqa: BLE001
            box.update(label="Live call failed", state="error")
            live_error(e)
        box.update(label=f"Done in {res['latency_ms'] / 1000:.1f} s (fact pack {res['timings_ms']['fact_pack'] / 1000:.1f} s · "
                         f"draft {res['timings_ms']['draft'] / 1000:.1f} s · verify {res['timings_ms']['verify'] / 1000:.1f} s)",
                   state="complete", expanded=False)
        _cached_live.clear()
    else:
        res = load_sample("generate", scope)
        box = staged(steps, random.uniform(4, 8))
        box.update(label="Done (sample replay)", state="complete", expanded=False)
    st.session_state["note"] = {"scope": scope, "res": res, "fresh": True}
    st.session_state.pop("rv", None)


def page_notes():
    st.title("Expansion notes")
    html('<p class="ss-sub">A one-page note for the expansion committee: drafted by Cortex AI_COMPLETE from the ranked fact pack, '
         'then fact-checked by a second AI_COMPLETE pass that refuses unsupported, forecast or hedged claims.</p>')
    left, right = st.columns([1, 2.2], gap="medium")
    with left.container(key="card_gen"):
        st.markdown("### Write a note")
        scope = st.radio("Scope", list(SCOPES), format_func=lambda k: SCOPES[k], key="scope")
        badge("Cortex AI_COMPLETE · draft + verifier")
        if st.button("Run site-selection analysis", type="primary", width="stretch", icon=":material/play_arrow:"):
            with right:
                run_note(scope)
        st.caption("Live runs took 9-12 s in testing and cost two AI_COMPLETE calls.")
    note = st.session_state.get("note")
    with right:
        if not note:
            html('<div class="ss-empty"><b>No note yet.</b><br>Pick a scope and run the analysis. The draft streams in, then the '
                 'verifier stamps it Verified or Needs review.</div>')
        else:
            res, nscope = note["res"], note["scope"]
            with st.container(key="card_note"):
                ai_label(res.get("latency_ms"))
                body = res["draft"]
                if note.get("fresh"):
                    ph = st.empty()
                    acc = ""
                    for tok in stream_words(body, 140):
                        acc += tok
                        ph.markdown(cite(acc + " ▍"), unsafe_allow_html=True)
                    ph.markdown(cite(body), unsafe_allow_html=True)
                    note["fresh"] = False
                else:
                    html(cite(body))
                note_view(res)
                with st.expander(f"Sources: fact pack ({len(res['fact_pack'])} cells, cited as F1-F{len(res['fact_pack'])})"):
                    st.dataframe(pd.DataFrame(res["fact_pack"]), hide_index=True, width="stretch")
            with st.container(key="card_break"):
                st.markdown("### Try to break it")
                st.caption("Add a hedged forecast the facts do not support, and run only the verifier again.")
                if st.button("Insert a forecast and re-verify", icon=":material/gavel:"):
                    steps = ["Re-reading the fact pack…", "Checking each figure in the edited draft…", "Scanning for hedges and forecasts…"]
                    if st.session_state.mode == "Live":
                        box = staged(steps)
                        try:
                            rv = LIVE_OPS_AI["reverify"](live_session(), nscope, res["draft"] + HEDGE_LINE)
                        except Exception as e:  # noqa: BLE001
                            live_error(e)
                        box.update(label=f"Verifier done in {rv['latency_ms'] / 1000:.1f} s", state="complete", expanded=False)
                    else:
                        rv = load_sample("reverify", nscope)
                        box = staged(steps, random.uniform(4, 6))
                        box.update(label="Verifier done (sample replay)", state="complete", expanded=False)
                    st.session_state["rv"] = {"scope": nscope, "rv": rv}
                rv = st.session_state.get("rv")
                if rv and rv["scope"] == nscope:
                    ai_label(rv["rv"].get("latency_ms"))
                    html(f'<div class="ss-insight ss-i-flat">Added: <i>{esc(HEDGE_LINE.strip())}</i></div>')
                    note_view(rv["rv"])
    st.markdown("### Note gallery")
    reports = guarded("reports")
    if not reports:
        html('<div class="ss-empty">No saved notes yet. Each Live run is stored in SITE_SELECTION_REPORTS and shows up here.</div>')
        return
    cols = st.columns(3)
    for i, r in enumerate(reports):
        ok = r["status"] == "verified"
        title = (r.get("report_md") or "").split("\n")[0].lstrip("# ").strip() or r["subject"]
        with cols[i % 3]:
            html(f'<div class="ss-docket {"" if ok else "bad"}">{pill("Verified" if ok else "Needs review", "good" if ok else "bad")}'
                 f'<div class="t">{esc(title[:90])}</div><div class="s">{esc(r["subject"])} · {esc(r["created_at"])} · '
                 f'{r["edits_applied"]} flagged</div></div>')
            if st.button("Open note", key=f"open_{r['run_id']}", width="stretch"):
                report_dialog(r)


@st.dialog("Saved expansion note", width="large")
def report_dialog(r):
    ok = r["status"] == "verified"
    html(f'<span class="ss-stamp {"ss-stamp-ok" if ok else "ss-stamp-bad"}">{"Verified" if ok else "Needs review"}</span>')
    html(cite(r["report_md"]))
    edits = json.loads(r.get("edits") or "[]")
    if edits:
        html("<b>Verifier flags</b><ul>" + "".join(f"<li>{esc(e)}</li>" for e in edits) + "</ul>")
    if r.get("fact_pack"):
        with st.expander("Sources: fact pack"):
            st.dataframe(pd.DataFrame(json.loads(r["fact_pack"])), hide_index=True, width="stretch")


def render_answer(a, fresh):
    ai_label(a.get("latency_ms"))
    text = a["text"].replace("$", "\\$")  # dollar amounts, not LaTeX
    if fresh:
        st.write_stream(stream_words(text, 80))
    else:
        st.markdown(text)
    for t in a.get("tables", []):
        if t["rows"]:
            st.dataframe(pd.DataFrame(t["rows"], columns=t["columns"] or None), hide_index=True, width="stretch")
    if a.get("sql"):
        with st.expander("Source: SQL generated by Cortex Analyst over SITE_SELECTION_SV"):
            st.code(a["sql"], language="sql")


def page_ask():
    st.title("Ask the analyst")
    html('<p class="ss-sub">Plain-English questions answered by a Cortex Agent that writes SQL with Cortex Analyst over the '
         'SITE_SELECTION_SV semantic view. Every figure comes from a query you can inspect.</p>')
    badge("Cortex Agent SITE_SELECTION_AGENT · Cortex Analyst · Semantic View SITE_SELECTION_SV")
    history = st.session_state.setdefault("chat", [])
    cols = st.columns(3)
    asked = None
    for i, q in enumerate(SAMPLE_QUESTIONS):
        if cols[i].button(q, key=f"sq{i}", width="stretch", icon=":material/forum:"):
            asked = q
    typed = st.chat_input("Ask about metros, categories, penetration or white space"
                          if st.session_state.mode == "Live" else "Sample mode answers the three questions above")
    if typed:
        if st.session_state.mode != "Live" and typed not in SAMPLE_QUESTIONS:
            st.info("Sample mode replays captured answers to the three sample questions. Switch to Live to ask your own.")
        else:
            asked = typed
    for h in history:
        with st.chat_message("user"):
            st.markdown(h["question"])
        with st.chat_message("assistant", avatar=":material/travel_explore:"):
            render_answer(h, False)
    if asked:
        with st.chat_message("user"):
            st.markdown(asked)
        with st.chat_message("assistant", avatar=":material/travel_explore:"):
            steps = ["Planning with the Cortex Agent…", "Generating SQL with Cortex Analyst over SITE_SELECTION_SV…",
                     f"Running the query on {WAREHOUSE}…", "Writing the answer from the result set…"]
            if st.session_state.mode == "Live":
                box = staged(steps)
                try:
                    a = LIVE_OPS_AI["ask"](live_session(), asked)
                except Exception as e:  # noqa: BLE001
                    box.update(label="Live call failed", state="error")
                    live_error(e)
                box.update(label=f"Answered in {a['latency_ms'] / 1000:.1f} s", state="complete", expanded=False)
            else:
                a = load_sample("ask", SAMPLE_QUESTIONS.index(asked))
                box = staged(steps, random.uniform(5, 8))
                box.update(label="Answered (sample replay)", state="complete", expanded=False)
            render_answer(a, True)
        history.append(a)


PAGES = {}


def context_bar():
    can_live = live_session() is not None
    has_sample = SAMPLE_DIR.exists()
    if "mode" not in st.session_state:
        st.session_state.mode = "Live" if can_live or not has_sample else "Sample"
    c1, c2 = st.columns([3, 1.1], vertical_alignment="center")
    env = st.session_state.mode
    with c1:
        html('<div class="ss-ctx"><span class="ss-chip"><span class="ss-avatar">ES</span>Expansion strategist · Corvane Payments</span>'
             f'<span class="ss-env ss-env-{env.lower()}">{env}</span><span class="ss-chip">As of {AS_OF}</span>'
             '<span class="ss-chip">Synthetic data</span></div>')
    with c2:
        options = (["Sample"] if has_sample else []) + ["Live"]
        choice = st.segmented_control("Data mode", options, key="mode_pick", default=env, label_visibility="collapsed")
        if choice and choice != env:
            st.session_state.mode = choice
            for k in ("note", "rv"):
                st.session_state.pop(k, None)
            st.session_state["chat"] = []
            st.rerun()
    if st.session_state.mode == "Live" and not can_live:
        st.warning("Live mode needs a Snowflake connection. Nothing was switched silently; set these and restart:", icon=":material/link_off:")
        st.code("export SNOWFLAKE_ACCOUNT=<your_account_identifier>\nexport SNOWFLAKE_USER=<YOUR_USER>\n"
                "export SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/keys/<your_key>.p8\n"
                "streamlit run app/streamlit_app.py", language="bash")
        st.caption("Run sql/setup.sql first. Key-pair setup is in the README under \"Run locally in Live mode\". "
                   "Credentials are never collected in the browser.")
        st.stop()


def main():
    st.set_page_config(page_title="Geographic Expansion & Site Selection", page_icon=":material/location_on:", layout="wide")
    html(CSS)
    logo = HERE / "static" / "logo.svg"
    if logo.exists():
        st.logo(str(logo), size="large", icon_image=str(HERE / "static" / "mark.svg"))
    PAGES.update({
        "overview": st.Page(page_overview, title="Overview", icon=":material/space_dashboard:", default=True),
        "map": st.Page(page_map, title="Market map", icon=":material/map:", url_path="map"),
        "ranking": st.Page(page_ranking, title="Opportunity ranking", icon=":material/leaderboard:", url_path="ranking"),
        "notes": st.Page(page_notes, title="Expansion notes", icon=":material/edit_note:", url_path="notes"),
        "ask": st.Page(page_ask, title="Ask the analyst", icon=":material/forum:", url_path="ask"),
    })
    nav = st.navigation(list(PAGES.values()), position="sidebar")
    with st.sidebar:
        html('<div class="ss-side-foot">Geographic Expansion &amp; Site Selection<br>A Snow Pack example · synthetic data<br>'
             'Owner: Javier Soliz</div>')
    context_bar()
    nav.run()
    html('<p style="color:#565873;font-size:.74rem;margin-top:2rem">Corvane Payments is fictional. Synthetic data and '
         'illustrative logic only; not production or investment advice. Owner: Javier Soliz.</p>')


if __name__ == "__main__":
    main()
