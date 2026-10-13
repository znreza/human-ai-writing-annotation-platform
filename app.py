"""WritingMirror draft-comparison annotation platform (Streamlit).

Two roles via two passwords:
  - annotator: consent -> register (name -> unique ID) -> tutorial -> staged annotation with gating
    (all pairs of a stage must be done before the next stage opens).
  - admin: dashboard (progress + CSV export) and a preview mode that walks the whole annotation flow
    with no gating and without writing real data (rows flagged is_preview).

Local-first: runs on SQLite (config.DATABASE_URL). Point DATABASE_URL at Supabase Postgres to deploy.
"""
import json, os, re
import streamlit as st
import streamlit.components.v1 as components
import config, db, auth, stages, admin, taxonomy

def _scroll_to_top():
    components.html(
        "<script>const d=window.parent.document;"
        "const t=d.querySelector('section.main')||d.querySelector('[data-testid=\"stMain\"]')"
        "||d.scrollingElement||d.documentElement;"
        "if(t){t.scrollTo({top:0,left:0,behavior:'auto'});}window.parent.scrollTo(0,0);</script>",
        height=0)

def _valid_prolific(pid):
    """Prolific IDs are alphanumeric tokens (commonly 24 chars). Keep the check loose but non-empty."""
    return bool(pid) and re.fullmatch(r"[A-Za-z0-9]{5,64}", pid) is not None

def _prolific_pid_from_url():
    """Prolific appends ?PROLIFIC_PID=... (plus STUDY_ID / SESSION_ID) to the study URL."""
    try:
        pid = st.query_params.get("PROLIFIC_PID")
    except Exception:
        pid = None
    pid = (pid or "").strip()
    return pid if _valid_prolific(pid) else ""

st.set_page_config(page_title=config.STUDY_TITLE, layout="wide")

# global: larger, more readable fonts across the app
st.markdown("""<style>
 html, body, [data-testid="stAppViewContainer"] { font-size: 17px; }
 .stMarkdown p, .stMarkdown li { font-size: 1.07rem; line-height: 1.6; }
 .stRadio label p, .stCheckbox label p { font-size: 1.02rem; }
 h1 { font-size: 2.0rem; } h2 { font-size: 1.6rem; } h3 { font-size: 1.3rem; }
 h4 { font-size: 1.12rem; }
 .stButton button { font-size: 1.05rem; padding: 0.5rem 1.1rem; }
 textarea, input { font-size: 1.02rem !important; }
 summary { font-size: 1.05rem; }
</style>""", unsafe_allow_html=True)

# ensure schema on first run; seed demo items ONLY on local SQLite (never into a real Postgres/Supabase db)
db.init_db()
if config.DATABASE_URL.startswith("sqlite") and db.counts()["items"] == 0:
    sample = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_items.json")
    if os.path.exists(sample):
        db.upsert_items(json.load(open(sample)))

def sidebar(role):
    with st.sidebar:
        st.markdown(f"**Role:** {role}")
        if st.session_state.get("annotator_id"):
            st.markdown(f"**Your ID:** `{st.session_state['annotator_id']}`")
        if st.button("Log out"):
            auth.logout()

# ---------------- annotator onboarding ----------------
def onboarding():
    # declined earlier
    if st.session_state.get("declined"):
        st.header("Thank you")
        st.markdown("You have chosen not to participate. You may now close this window.")
        st.stop()

    # study rules + formal consent gate
    if not st.session_state.get("agreed"):
        st.markdown(taxonomy.STUDY_RULES)
        st.divider()
        st.markdown(taxonomy.CONSENT_FORM)
        c1, c2, _ = st.columns([1, 1, 3])
        if c1.button("I consent", type="primary"):
            st.session_state["agreed"] = True
            st.rerun()
        if c2.button("I do not consent"):
            st.session_state["declined"] = True
            st.rerun()
        st.stop()

    # identify via Prolific ID: passed in the recruitment URL as ?PROLIFIC_PID=..., or entered manually.
    # The same Prolific link resumes an existing participant automatically (no ID to memorize).
    if not st.session_state.get("annotator_id"):
        pid = st.session_state.get("prolific_pid") or _prolific_pid_from_url()
        if not pid:
            st.header("Enter your Prolific ID")
            st.markdown("Please enter your **Prolific ID** to begin. If you followed the study link from "
                        "Prolific, it is normally detected automatically.")
            entered = st.text_input("Prolific ID")
            if st.button("Start the study", type="primary"):
                entered = (entered or "").strip()
                if _valid_prolific(entered):
                    pid = entered
                else:
                    st.warning("Please enter a valid Prolific ID (letters and numbers).")
            if not pid:
                st.stop()
        st.session_state["prolific_pid"] = pid
        a = db.get_annotator_by_prolific(pid)
        if a is None:
            aid = db.create_annotator(pid, role="annotator", prolific_pid=pid)
            db.assign_items(aid)
            db.log_event(aid, "register")
            st.session_state["annotator_id"] = aid
        else:
            st.session_state["annotator_id"] = a.id
        st.rerun()

# ---------------- staged annotation flow ----------------
def current_stage(ann_id, items):
    """First stage not yet complete for this annotator; None if all done."""
    for stg in config.STAGES:
        if db.stage_completed_count(ann_id, stg) < len(items):
            return stg
    return None

def run_stage(ann_id, items, stage, is_preview):
    n = len(items)
    idx_key = f"idx_{stage}"
    st.session_state.setdefault(idx_key, 0)
    idx = min(st.session_state[idx_key], n - 1)

    # scroll to the top whenever the stage changes (incl. admin preview switching) or a pair advances
    stage_changed = st.session_state.get("_last_stage") != stage
    st.session_state["_last_stage"] = stage
    if st.session_state.pop("_scroll_top", False) or stage_changed:
        _scroll_to_top()

    done = db.stage_completed_count(ann_id, stage)
    st.subheader(config.STAGE_TITLES[stage])
    st.progress(done / n if n else 0, text=f"{done} of {n} pairs completed in this stage")
    st.markdown(f'<span style="color:#1a1a1a;font-weight:600">Pair {idx + 1} of {n}</span>'
                f'<span style="color:#1a1a1a">  ({items[idx].genre})</span>', unsafe_allow_html=True)

    saved = stages.RENDERERS[stage](ann_id, items[idx], is_preview)
    if saved:
        st.session_state["_scroll_top"] = True
        if idx < n - 1:
            st.session_state[idx_key] = idx + 1
        st.rerun()

    # "Save and continue" (inside the stage renderer) advances to the next pair. Only a Previous
    # control remains, to go back to an earlier pair if needed.
    if st.button("◀ Previous", disabled=(idx == 0), key=f"prev_{stage}"):
        st.session_state[idx_key] = max(0, idx - 1); st.rerun()

def annotator_flow(role):
    is_preview = (role == "admin")
    if is_preview:
        # one persistent preview annotator per admin session
        if not st.session_state.get("annotator_id"):
            aid = db.create_annotator("ADMIN PREVIEW", role="admin", is_preview=True)
            db.assign_items(aid)
            st.session_state["annotator_id"] = aid
        st.warning("Admin preview mode: gating is off, all stages are open, and nothing you enter "
                   "is counted as real data.")
    else:
        onboarding()

    ann_id = st.session_state["annotator_id"]
    items = db.get_assignment(ann_id)
    if not items:
        db.assign_items(ann_id)
        items = db.get_assignment(ann_id)
    if not items:
        st.error("No items are loaded in the study yet."); return

    if is_preview:
        stage = st.sidebar.radio("Preview stage", config.STAGES,
                                 format_func=lambda s: config.STAGE_TITLES[s])
        run_stage(ann_id, items, stage, is_preview=True)
        return

    pid = st.session_state.get("prolific_pid", "")
    if pid:
        st.markdown(f'<span style="color:#1a1a1a">Prolific ID <b style="color:#E4695A">{pid}</b> '
                    f'— your progress is saved; returning via the same Prolific link resumes where you '
                    f'left off.</span>', unsafe_allow_html=True)

    stage = current_stage(ann_id, items)
    if stage is None:
        st.balloons()
        st.success("You have completed the study. Thank you for participating!")
        code = config.PROLIFIC_COMPLETION_CODE
        if code:
            st.markdown("Please return to Prolific to register your completion — click the button below "
                        "(or enter the completion code on Prolific).")
            st.link_button("Return to Prolific and submit", config.PROLIFIC_COMPLETION_URL + code,
                           type="primary")
            st.markdown(f"Completion code: **{code}**")
        else:
            st.markdown("You may now return to Prolific to submit your completion.")
        return

    run_stage(ann_id, items, stage, is_preview=False)

def main():
    role = auth.check_password()
    if not role:
        return

    if role == "admin":
        sidebar(role)
        mode = st.sidebar.radio("Admin view", ["Dashboard", "Preview annotation flow"])
        if mode == "Dashboard":
            admin.render_dashboard()
        else:
            annotator_flow(role)
    else:
        # annotators (Prolific): no sidebar — hide the Role/Log out panel and its toggle entirely
        st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
                    "[data-testid='collapsedControl']{display:none!important}</style>",
                    unsafe_allow_html=True)
        annotator_flow(role)

if __name__ == "__main__":
    main()
