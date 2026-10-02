"""Password gate with two roles. Sets st.session_state['role'] to 'annotator' or 'admin'."""
import streamlit as st
import config

def check_password():
    """Render the password gate. Returns the role once authenticated, else None."""
    if st.session_state.get("role"):
        return st.session_state["role"]

    st.title(config.STUDY_TITLE)
    st.markdown("Please enter the access password to continue.")
    pw = st.text_input("Access password", type="password")
    if st.button("Enter", type="primary"):
        if pw == config.ADMIN_PASSWORD:
            st.session_state["role"] = "admin"
            st.rerun()
        elif pw == config.ANNOTATOR_PASSWORD:
            st.session_state["role"] = "annotator"
            st.rerun()
        else:
            st.error("Incorrect password.")
    return st.session_state.get("role")

def logout():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()
