"""Capture Sample-mode data from a Live run (run after sql/setup.sql).

Calls every data op, the two expansion notes, the forecast re-verify and the three agent
questions against Snowflake, and writes app/sample/*.json (and a copy for the hosted example in
docs/try/data/). Uses key-pair auth from the same environment variables as the app's Live mode.
User names are never written.

    SNOWFLAKE_ACCOUNT=... SNOWFLAKE_USER=... SNOWFLAKE_PRIVATE_KEY_PATH=... \
      python scripts/capture_sample.py [--resume]
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import streamlit_app as app  # noqa: E402

OUT = ROOT / "app" / "sample"
TRY = ROOT / "docs" / "try" / "data"
resume = "--resume" in sys.argv


def save(key, data):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{key}.json").write_text(json.dumps(data, indent=1, default=str))
    print("saved", key, flush=True)


def done(key):
    return resume and (OUT / f"{key}.json").exists()


sess = app._local_session()
for name in ("cells", "metros", "regions", "demand", "source"):
    if not done(name):
        save(name, app.LIVE_OPS[name](sess))
for scope in app.SCOPES:
    if not done(app.sample_key("fact_pack", scope)):
        save(app.sample_key("fact_pack", scope), app.live_fact_pack(sess, scope))
    if not done(app.sample_key("generate", scope)):
        save(app.sample_key("generate", scope), app.live_generate(sess, scope))
    if not done(app.sample_key("reverify", scope)):
        g = json.loads((OUT / f"{app.sample_key('generate', scope)}.json").read_text())
        save(app.sample_key("reverify", scope), app.live_reverify(sess, scope, g["draft"] + app.HEDGE_LINE))
save("reports", app.live_reports(sess))
for i, q in enumerate(app.SAMPLE_QUESTIONS):
    if not done(app.sample_key("ask", i)):
        save(app.sample_key("ask", i), app.live_ask(sess, q))

TRY.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("*.json"):
    shutil.copy(f, TRY / f.name)
print("copied", len(list(OUT.glob("*.json"))), "files to", TRY)
