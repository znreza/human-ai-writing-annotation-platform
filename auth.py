"""Access control.

For the Prolific launch the annotator password gate is DISABLED: participants who arrive from the
study link go straight into the flow (no access password). Admin access is still protected — reach the
dashboard at  <app-url>/?admin=1  and enter the admin password.

To restore the password gate for everyone, see the note inside check_password() and uncomment the
original gate block kept at the bottom of this file.
"""
import streamlit as st
import config

def check_password():
    """Return the role. Annotators enter WITHOUT a password (Prolific launch); admin via ?admin=1."""
    if st.session_state.get("role"):
        return st.session_state["role"]

    # ---- admin still needs the admin password; reach it with ?admin=1 in the URL ----
    try:
        wants_admin = bool(st.query_params.get("admin"))
    except Exception:
        wants_admin = False
    if wants_admin:
        st.title(config.STUDY_TITLE)
        st.markdown("Admin access — please enter the admin password.")
        pw = st.text_input("Admin password", type="password")
        if st.button("Enter", type="primary"):
            if pw == config.ADMIN_PASSWORD:
                st.session_state["role"] = "admin"
                st.rerun()
            else:
                st.error("Incorrect password.")
        return st.session_state.get("role")

    # ---- annotator password gate DISABLED for the Prolific launch: enter directly ----
    # To re-enable the password gate for everyone, remove the two lines just below and
    # uncomment the "ORIGINAL password gate" block at the bottom of this function.
    st.session_state["role"] = "annotator"
    return "annotator"

    # --- ORIGINAL password gate (kept for later; re-enable by uncommenting) --------------
    # st.title(config.STUDY_TITLE)
    # st.markdown("Please enter the access password to continue.")
    # pw = st.text_input("Access password", type="password")
    # if st.button("Enter", type="primary"):
    #     if pw == config.ADMIN_PASSWORD:
    #         st.session_state["role"] = "admin"
    #         st.rerun()
    #     elif pw == config.ANNOTATOR_PASSWORD:
    #         st.session_state["role"] = "annotator"
    #         st.rerun()
    #     else:
    #         st.error("Incorrect password.")
    # return st.session_state.get("role")
    # ------------------------------------------------------------------------------------

def logout():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()
