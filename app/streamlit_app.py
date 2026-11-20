import json
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Payments Site Selection", layout="wide")

SCHEMA = "SNOWPACK_SITE_SELECTION.CORE"
MODEL = "claude-sonnet-4-5"
session = get_active_session()
_rerun = getattr(st, "rerun", getattr(st, "experimental_rerun", lambda: None))
BADGE = {"verified": "✅ Verified", "needs_review": "⚠️ Needs review"}


def sql_df(q, p=None):
    df = session.sql(q, params=p or []).to_pandas()
    df.columns = [c.lower() for c in df.columns]
    return df


def data_mode():
    try:
        r = session.sql(f"SELECT mode, note FROM {SCHEMA}.SITE_SELECTION_DATA_SOURCE_INFO").collect()[0]
        return r[0], r[1]
    except Exception:
        return "unknown", ""


def load_reports():
    return sql_df(f"SELECT run_id, subject, status, edits_applied, residual_hedges, report_md, created_at FROM {SCHEMA}.SITE_SELECTION_REPORTS ORDER BY created_at DESC")


def fact_pack():
    return session.sql(f"""
        SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
          'metro', metro_name, 'state', state, 'region', region, 'category', category_name,
          'penetration_pct', penetration_pct, 'opportunity_score', opportunity_score,
          'white_space_usd', white_space_volume, 'merchants_per_100k', merchants_per_100k,
          'demand_growth_pct', category_demand_growth_pct))
        FROM (
          SELECT * FROM {SCHEMA}.SITE_SELECTION_BENCHMARK
          ORDER BY opportunity_score DESC
          LIMIT 12)
    """).collect()[0][0]


def draft_note(fp):
    rules = (
        "You are a payments expansion strategist. Write a concise site-selection note using ONLY the FACTS JSON.\n"
        "DATA RULES: use only numbers in FACTS, copy exactly; opportunity_score blends category demand growth with coverage gap "
        "(higher = stronger expansion target); penetration_pct is a ratio (0-1); white_space_usd is USD, express $B/$M; "
        "no estimates, no hedging, no outside benchmarks; missing = n/d.\n"
        "OUTPUT markdown starting with '# ', a one-line takeaway (top expansion targets), a table "
        "(metro | category | penetration | opportunity | white space), 3 bullets, ending with '## Data Coverage'."
    )
    return session.sql("SELECT AI_COMPLETE(?, ?)", params=[MODEL, rules + f"\n\nFACTS: {fp}"]).collect()[0][0]


def verify(fp, draft):
    vp = (
        "You are a fact-checker. Compare the DRAFT against the FACTS JSON (only allowed source). Return ONLY a JSON object with keys "
        "status ('verified' if every number/claim is supported and no hedge words like likely/approximately/around/could, else 'needs_review'), "
        "residual_hedges (int), edits (array of strings).\n\n" + f"FACTS: {fp}\n\nDRAFT:\n{draft}"
    )
    raw = session.sql("SELECT AI_COMPLETE(?, ?)", params=[MODEL, vp]).collect()[0][0]
    s, e = raw.find("{"), raw.rfind("}")
    try:
        return json.loads(raw[s:e + 1])
    except Exception:
        return {"status": "needs_review", "residual_hedges": None, "edits": ["unparseable verifier output"]}


st.title("Payments Site Selection & Expansion")
st.caption("Rank metro x merchant-category cells by white-space opportunity: strong category demand, low coverage.")
_mode, _note = data_mode()
if _mode == "synthetic":
    st.warning("Sample mode — fully synthetic. " + _note)
elif _mode == "hybrid":
    st.info("Hybrid — real Census demand, synthetic geography. " + _note)

if "view" not in st.session_state:
    st.session_state["view"] = "gallery"

with st.sidebar:
    st.subheader("Generate a note")
    st.caption("Ranks the top white-space opportunities and writes a verified expansion note.")
    if st.button("Run site-selection analysis", type="primary", use_container_width=True):
        with st.spinner("Fact pack → grounded draft → verify (~20-40s)..."):
            fp = fact_pack()
            draft = draft_note(fp)
            v = verify(fp, draft)
            status = "verified" if v.get("status") == "verified" else "needs_review"
            session.sql(
                f"INSERT INTO {SCHEMA}.SITE_SELECTION_REPORTS (subject, draft_md, report_md, status, edits_applied, residual_hedges) SELECT ?, ?, ?, ?, ?, ?",
                params=["Expansion white-space ranking", draft, draft, status, len(v.get("edits", [])), v.get("residual_hedges")],
            ).collect()
        st.success(f"Done — {BADGE[status]}")
        st.session_state["view"] = "gallery"
        _rerun()

if st.session_state["view"].startswith("report:"):
    run_id = st.session_state["view"].split(":", 1)[1]
    rpt = load_reports()
    row = rpt[rpt["run_id"] == run_id]
    if st.button("← Back to gallery"):
        st.session_state["view"] = "gallery"
        _rerun()
    if not row.empty:
        r = row.iloc[0]
        st.markdown(f"**{BADGE.get(r['status'], r['status'])}**  &nbsp; residual hedges: {r['residual_hedges']}  |  flagged: {r['edits_applied']}")
        st.divider()
        st.markdown(r["report_md"])
else:
    reports = load_reports()
    if reports.empty:
        st.info("No notes yet. Use the sidebar to generate one.")
    else:
        cols = st.columns(3)
        for i, (_, r) in enumerate(reports.iterrows()):
            with cols[i % 3]:
                c = st.container()
                c.markdown(f"**{BADGE.get(r['status'], r['status'])}**")
                c.markdown(f"**{r['subject']}**")
                c.caption(f"{str(r['created_at'])[:16]} · {r['edits_applied']} flagged")
                if c.button("Open report", key=f"open_{r['run_id']}", use_container_width=True):
                    st.session_state["view"] = f"report:{r['run_id']}"
                    _rerun()
                c.markdown("---")
