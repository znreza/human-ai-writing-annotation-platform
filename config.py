"""Central configuration. Reads from Streamlit secrets first, then environment, then dev defaults.

Local development runs entirely on SQLite with the dev-default passwords below. For deployment,
set the same keys in .streamlit/secrets.toml (see .streamlit/secrets.toml.example) and switch
DATABASE_URL to the Supabase Postgres connection string. No code changes are needed to switch.
"""
import os


def _get(key, default=None):
    # Streamlit secrets are optional at import time (e.g. when running seed scripts).
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)

# ---- access control (two roles) ----
ANNOTATOR_PASSWORD = _get("ANNOTATOR_PASSWORD", "annotate-dev")
ADMIN_PASSWORD     = _get("ADMIN_PASSWORD", "admin-dev")

# ---- Prolific recruitment ----
# Participants arrive from Prolific with ?PROLIFIC_PID=... in the URL; that becomes their ID.
# The completion code is shown/linked at the end so Prolific can register their submission.
# Set PROLIFIC_COMPLETION_CODE in the environment / secrets (found on the Prolific study page).
PROLIFIC_COMPLETION_CODE = _get("PROLIFIC_COMPLETION_CODE", "")
PROLIFIC_COMPLETION_URL  = "https://app.prolific.com/submissions/complete?cc="

# ---- storage ----
# SQLite locally; a postgresql+psycopg2://... URL (from Supabase) in production.
_DEFAULT_DB = "sqlite:///" + os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.db")
DATABASE_URL = _get("DATABASE_URL", _DEFAULT_DB)

# ---- study parameters ----
# The study covers three genres only. Each annotator sees PER_GENRE pairs from each, so
# PAIRS_PER_ANNOTATOR = PER_GENRE * len(STUDY_GENRES). Sets are drawn per annotator so they differ
# (overlap allowed, never fully identical). Same set is shown across both stages.
STUDY_GENRES = ["fiction", "academic", "application"]
PER_GENRE = int(_get("PER_GENRE", "4"))
PAIRS_PER_ANNOTATOR = PER_GENRE * len(STUDY_GENRES)  # 12 (4 per genre)
TARGET_MINUTES = 30          # displayed guidance only
STUDY_TITLE = "Study on the Impact of AI on Writing"

# stage labels (used across UI and DB). The study has two stages: stage1 (differences) and
# stage2 (asked-or-implied judgement). The DB key "stage2" is driven by render_stage2 in stages.py.
STAGES = ["stage1", "stage2"]
STAGE_TITLES = {
    "stage1": "Stage 1",
    "stage2": "Stage 2",
}
