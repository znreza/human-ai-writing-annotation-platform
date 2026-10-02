"""Admin dashboard: progress counts, item inventory, and CSV export. Reached with the admin password."""
import io, csv, json
import streamlit as st
import db, config

def render_dashboard():
    st.header("Admin dashboard")
    c = db.counts()
    m1, m2, m3 = st.columns(3)
    m1.metric("Items loaded", c["items"])
    m2.metric("Annotators (real)", c["annotators"])
    m3.metric("Responses (real)", c["responses"])

    st.divider()
    st.subheader("Export")
    include_preview = st.checkbox("Include admin/preview rows", value=False)
    rows = db.export_rows(include_preview=include_preview)
    if rows:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
        st.download_button("Download responses CSV", buf.getvalue(),
                           file_name="annotations.csv", mime="text/csv")
        st.caption(f"{len(rows)} response rows. The `payload` column holds the stage answer as JSON.")
    else:
        st.caption("No responses yet.")

    st.divider()
    st.subheader("Per-annotator progress")
    from sqlalchemy import select, func
    with db.SessionLocal() as s:
        anns = s.scalars(select(db.Annotator).where(db.Annotator.is_preview == False)).all()
        if not anns:
            st.caption("No annotators have registered yet.")
        for a in anns:
            counts = {}
            for stg in config.STAGES:
                counts[stg] = s.scalar(select(func.count()).select_from(db.Response).where(
                    db.Response.annotator_id == a.id, db.Response.stage == stg)) or 0
            st.write(f"**{a.id}** ({a.name}) — "
                     + " · ".join(f"{stg}: {counts[stg]}" for stg in config.STAGES))
