"""WritingMirror draft-comparison annotation platform (Streamlit).

Two roles via two passwords:
  - annotator: consent -> register (name -> unique ID) -> tutorial -> staged annotation with gating
    (all pairs of a stage must be done before the next stage opens).
  - admin: dashboard (progress + CSV export) and a preview mode that walks the whole annotation flow
    with no gating and without writing real data (rows flagged is_preview).

Local-first: runs on SQLite (config.DATABASE_URL). Point DATABASE_URL at Supabase Postgres to deploy.
"""
import json, os
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

    # register or resume
    if not st.session_state.get("annotator_id"):
        st.header("Enter your name")
        st.markdown("Enter your name to receive a participant ID, or resume with an existing ID.")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("New participant")
            name = st.text_input("Your name")
            if st.button("Get my participant ID and start", type="primary"):
                if name.strip():
                    aid = db.create_annotator(name, role="annotator")
                    db.assign_items(aid)
                    db.log_event(aid, "register")
                    st.session_state["annotator_id"] = aid
                    st.rerun()
                else:
                    st.warning("Please enter your name.")
        with col2:
            st.subheader("Returning participant")
            rid = st.text_input("Your participant ID (e.g. WM-AB12)")
            if st.button("Resume"):
                a = db.get_annotator(rid.strip().upper())
                if a and a.role == "annotator":
                    st.session_state["annotator_id"] = a.id
                    st.rerun()
                else:
                    st.error("ID not found.")
        st.stop()

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

    # prominent one-time "save your ID" gate before Stage 1
    if not st.session_state.get("id_ack"):
        st.header("Your participant ID")
        st.success(f"### {ann_id}")
        st.markdown(f'<div style="background:#FFF4E5;border-left:6px solid #E4695A;padding:12px 16px;'
                    f'border-radius:6px;color:#1a1a1a;font-size:1.05rem;margin:6px 0 14px 0">'
                    f'<b>Please write down or copy your participant ID: {ann_id}</b><br>'
                    f'You will need it to resume if you stop partway through. It will not be shown '
                    f'again on its own.</div>', unsafe_allow_html=True)
        if st.button("I have saved my ID, continue to Stage 1", type="primary"):
            st.session_state["id_ack"] = True
            st.rerun()
        return

    st.markdown(f'<span style="color:#1a1a1a">Participant ID <b style="color:#E4695A">{ann_id}</b> '
                f'— save it to resume later.</span>', unsafe_allow_html=True)
    stage = current_stage(ann_id, items)
    if stage is None:
        st.balloons()
        st.success("You have completed all stages. Thank you for participating.")
        st.markdown(f"Your participant ID is **{ann_id}**.")
        return

    # gentle gate notice when a stage just opened
    run_stage(ann_id, items, stage, is_preview=False)

def main():
    role = auth.check_password()
    if not role:
        return
    sidebar(role)

    if role == "admin":
        mode = st.sidebar.radio("Admin view", ["Dashboard", "Preview annotation flow"])
        if mode == "Dashboard":
            admin.render_dashboard()
        else:
            annotator_flow(role)
    else:
        annotator_flow(role)

if __name__ == "__main__":
    main()
