"""Per-item rendering for the three annotation stages.

Stage 1: free-form list of as many differences as the annotator can find.
Stage 2: the merged category set (common edit types + genre-specific), each rated Absent / Present /
         Very present with line-number evidence, plus a free-text catch-all.
Stage 3: the same conversation + both drafts (target draft emphasized), then the SAME categories asked
         as "asked or implied by the user" vs "not asked", given the conversation as context.

Drafts show per-line numbers in a code-editor style (A# original, B# revised). Definitions sit directly
under each category label. Categories are all visible (no collapsibles). Gray text is avoided.
"""
import html as _html
import json
import re

import streamlit as st

import db
import taxonomy

RED = "#E4695A"
# chat styling
USER_BAND, AI_BAND = "#F2F7FF", "#F0F8F2"
USER_GRAD = "linear-gradient(135deg,#5B8AD9,#3B6FB5)"
AI_GRAD = "linear-gradient(135deg,#43A06B,#2F7C4F)"
PERSON_SVG = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="#ffffff">'
              '<path d="M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5Zm0 2.2c-4.2 0-8 2.1-8 5.1V21h16v-1.7'
              'c0-3-3.8-5.1-8-5.1Z"/></svg>')

# ------------------------- shared UI helpers -------------------------
def spacer(px=18):
    st.markdown(f"<div style='height:{px}px'></div>", unsafe_allow_html=True)

def callout(text, strong=False):
    bg = "#FDEAE8" if strong else "#FFF4E5"
    st.markdown(
        f'<div style="background:{bg};border-left:7px solid {RED};padding:14px 18px;'
        f'border-radius:8px;color:#121212;font-size:1.12rem;line-height:1.5;margin:4px 0 14px 0">{text}</div>',
        unsafe_allow_html=True)

def section_header(text):
    st.markdown(f'<div style="height:26px"></div>'
                f'<div style="font-size:1.32rem;font-weight:800;color:#121212;margin-bottom:8px">{text}</div>',
                unsafe_allow_html=True)

def group_header(name):
    st.markdown(f'<div style="height:20px"></div>'
                f'<div style="font-size:1.15rem;font-weight:800;color:#121212;'
                f'padding-bottom:5px;border-bottom:2px solid {RED};margin-bottom:8px">{_html.escape(name)}</div>',
                unsafe_allow_html=True)

def to_lines(text):
    """One numbered unit per SENTENCE (split within each line), numbered before the sentence."""
    units = []
    for raw in (text or "").split("\n"):
        raw = raw.strip()
        if not raw:
            continue
        for part in re.split(r'(?<=[.!?])\s+', raw):
            part = part.strip()
            if part:
                units.append(part)
    return units

def numbered_block(text, prefix, height=320, big=False):
    fs = "1.02rem" if big else "0.95rem"
    rows = []
    for i, ln in enumerate(to_lines(text)):
        rows.append(
            f'<div style="display:flex;gap:12px;padding:3px 12px">'
            f'<span style="color:{RED};font-weight:700;min-width:38px;text-align:right;'
            f'user-select:none;font-variant-numeric:tabular-nums">{prefix}{i+1}</span>'
            f'<span style="flex:1">{_html.escape(ln)}</span></div>')
    st.markdown(
        f'<div style="border:1px solid #e2e4e8;border-radius:8px;background:#fff;padding:8px 0;'
        f'max-height:{height}px;overflow:auto;font-size:{fs};line-height:1.55">' + "".join(rows) + "</div>",
        unsafe_allow_html=True)

def draft_pair(item, big=False):
    st.markdown(f'<div style="font-size:1.0rem;color:#121212;margin-bottom:4px">Original lines are '
                f'<b style="color:{RED}">A1, A2, ...</b> and revised lines are '
                f'<b style="color:{RED}">B1, B2, ...</b></div>', unsafe_allow_html=True)
    h = 420 if big else 320
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Original draft (A)")
        numbered_block(item.original, "A", height=h, big=big)
    with c2:
        tag = ('<span style="background:%s;color:#fff;border-radius:6px;padding:2px 10px;'
               'font-size:0.9rem;margin-left:8px">judge this</span>' % RED) if big else ""
        st.markdown(f"#### Target revised draft (B){tag}", unsafe_allow_html=True)
        numbered_block(item.revised, "B", height=h, big=big)

def _lines_list(text):
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

def category_label(label, help_text, extra=""):
    st.markdown(
        f'<div style="font-size:1.05rem;font-weight:700;color:#121212;margin-top:10px">{_html.escape(label)}{extra}</div>'
        f'<div style="font-size:0.9rem;color:#333;margin:1px 0 4px 0">{_html.escape(help_text)}</div>',
        unsafe_allow_html=True)

# ------------------------------- Stage 1 -------------------------------
def render_stage1(ann_id, item, is_preview):
    callout("List <b>as many differences as you can find</b> between the original and the revised draft. "
            "Write <b>one difference per line</b>. Look closely and be thorough; describe what changed "
            "without worrying about categories yet.")
    draft_pair(item)
    section_header("Differences (one per line)")
    saved = db.get_response(ann_id, item.pair_id, "stage1") or {}
    key = f"s1_{item.pair_id}"
    default = "\n".join(saved.get("differences", []))
    txt = st.text_area("Differences (one per line)", value=default, key=key, height=220,
                       label_visibility="collapsed",
                       placeholder="e.g.\nThe revision adds a hopeful ending\nThe tone is more formal\n"
                                   "A new character is introduced in B4\n...")
    if st.button("Save and continue", key=f"save_{key}", type="primary"):
        diffs = _lines_list(txt)
        if not diffs and not is_preview:
            st.warning("Please list at least one difference before continuing.")
            return False
        db.save_response(ann_id, item.pair_id, "stage1", {"differences": diffs}, is_preview=is_preview)
        db.log_event(ann_id, "save", item.pair_id, "stage1")
        return True
    return False

# ------------------------------- Stage 2 -------------------------------
def render_stage2(ann_id, item, is_preview):
    callout("For each category, say how present it is in the <b>revised draft (B)</b> "
            "(<b>Absent / Present / Very present</b>) and list the "
            f"<b style='color:{RED}'>line numbers</b> where you see evidence (for example "
            "<b>B2, B5</b> or <b>A3</b>). Definitions are shown under each category.")
    draft_pair(item)
    spacer(20)
    saved = db.get_response(ann_id, item.pair_id, "stage2") or {}
    saved_cats = saved.get("categories", {})
    opts = taxonomy.PRESENCE_OPTIONS

    cats = {}
    for group, items in taxonomy.categories_for(item.genre):
        group_header(group)
        for cid, label, hlp in items:
            prev = saved_cats.get(cid, {})
            category_label(label, hlp)
            c1, c2 = st.columns([3, 2])
            with c1:
                cur = prev.get("presence")
                val = st.radio(label, opts, index=opts.index(cur) if cur in opts else None,
                               horizontal=True, key=f"s2r_{item.pair_id}_{cid}",
                               label_visibility="collapsed")
            with c2:
                lines = st.text_input("Line numbers", value=prev.get("lines", ""),
                                      key=f"s2l_{item.pair_id}_{cid}",
                                      placeholder="line numbers, e.g. B2, B5",
                                      label_visibility="collapsed")
            cats[cid] = {"presence": val, "lines": lines.strip()}

    section_header("What other kinds of edits do you see that are not covered above? Type N/A if none.")
    other = st.text_area("Other edits", value=saved.get("other", ""), key=f"s2o_{item.pair_id}",
                         height=90, label_visibility="collapsed",
                         placeholder="Describe any other changes you notice.")

    if st.button("Save and continue", key=f"save_s2_{item.pair_id}", type="primary"):
        unanswered = [cid for cid, v in cats.items() if v["presence"] is None]
        if unanswered and not is_preview:
            st.warning(f"Please choose Absent, Present, or Very present for every category before "
                       f"continuing. {len(unanswered)} still unanswered.")
            return False
        db.save_response(ann_id, item.pair_id, "stage2",
                         {"categories": cats, "other": other.strip()}, is_preview=is_preview)
        db.log_event(ann_id, "save", item.pair_id, "stage2")
        return True
    return False

# ------------------------------- Stage 3 -------------------------------
def _bubble(is_user, text):
    band = USER_BAND if is_user else AI_BAND
    grad = USER_GRAD if is_user else AI_GRAD
    inner = PERSON_SVG if is_user else '<span style="color:#fff;font-weight:800;font-size:0.82rem">AI</span>'
    body = _html.escape(text or "").replace("\n", "<br>")
    return (f'<div style="display:flex;gap:14px;padding:18px 20px;background:{band};'
            f'border-bottom:1px solid #e9ecf1">'
            f'<div style="flex:0 0 38px;height:38px;border-radius:50%;background:{grad};'
            f'display:flex;align-items:center;justify-content:center;'
            f'box-shadow:0 1px 4px rgba(0,0,0,.20)">{inner}</div>'
            f'<div style="flex:1;font-size:1.0rem;line-height:1.6;color:#121212;'
            f'align-self:center">{body}</div></div>')

def render_chat(item):
    try:
        conv = json.loads(item.conversation or "[]")
    except Exception:
        conv = []
    if not conv:
        conv = [{"role": "human", "text": item.instruction or "(no instruction recorded)"}]
    bubbles = [_bubble(m.get("role") == "human", m.get("text", "")) for m in conv]
    # complete the final turn: the AI's response is the target revised draft (B)
    if item.revised and (not conv or conv[-1].get("role") == "human"):
        bubbles.append(_bubble(False, item.revised))
    st.markdown(
        f'<div style="border:1px solid #d7dae0;border-radius:14px;overflow:auto;max-height:420px;'
        f'background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.06)">' + "".join(bubbles) + "</div>",
        unsafe_allow_html=True)

def render_stage3(ann_id, item, is_preview):
    callout("Below is a conversation between a <b>human</b> and an <b>AI</b> on a writing task. You are "
            "shown the <b>final turn</b> of that conversation, including the human's instruction and the "
            "AI's reply. Given the conversation as context, assess <b>ONLY the target revised draft (B)</b>: "
            "for each category, say whether that change was <b>asked or implied</b> by the user or "
            "<b>not asked</b>.", strong=True)

    section_header("Conversation between the human and the AI")
    render_chat(item)

    section_header("The two drafts — judge the revised draft (B)")
    draft_pair(item, big=True)

    s2 = db.get_response(ann_id, item.pair_id, "stage2") or {}
    s2cats = s2.get("categories", {})
    saved = db.get_response(ann_id, item.pair_id, "stage3") or {}
    saved_cats = saved.get("categories", {})
    opts = taxonomy.JUSTIFY_OPTIONS

    section_header("For each category: was it asked or implied by the user?")
    cats = {}
    for group, items in taxonomy.categories_for(item.genre):
        group_header(group)
        for cid, label, hlp in items:
            prev = saved_cats.get(cid, {})
            pres = (s2cats.get(cid, {}) or {}).get("presence")
            note = (f'  <span style="background:#eef1f5;border-radius:8px;padding:1px 8px;'
                    f'font-size:0.82rem;color:#121212">you marked: {pres}</span>') if pres and pres != "Absent" else ""
            category_label(label, hlp, extra=note)
            cur = prev.get("justify")
            val = st.radio(label, opts, index=opts.index(cur) if cur in opts else None,
                           horizontal=True, key=f"s3r_{item.pair_id}_{cid}",
                           label_visibility="collapsed")
            cats[cid] = {"justify": val}

    section_header("Any additional remarks about this pair (optional)")
    remarks = st.text_area("Remarks", value=saved.get("remarks", ""), key=f"s3rm_{item.pair_id}",
                           height=90, label_visibility="collapsed", placeholder="Anything else worth noting.")

    section_header("If this were your own draft, how satisfied would you be with the revision? (optional)")
    satisfaction = st.text_area("Satisfaction", value=saved.get("satisfaction", ""),
                                key=f"s3s_{item.pair_id}", height=80, label_visibility="collapsed",
                                placeholder="Describe how satisfied you would be and why.")

    if st.button("Save and continue", key=f"save_s3_{item.pair_id}", type="primary"):
        unanswered = [cid for cid, v in cats.items() if v["justify"] is None]
        if unanswered and not is_preview:
            st.warning(f"Please choose an option for every category before continuing. "
                       f"{len(unanswered)} still unanswered.")
            return False
        db.save_response(ann_id, item.pair_id, "stage3",
                         {"categories": cats, "remarks": remarks.strip(),
                          "satisfaction": satisfaction.strip()}, is_preview=is_preview)
        db.log_event(ann_id, "save", item.pair_id, "stage3")
        return True
    return False

RENDERERS = {"stage1": render_stage1, "stage2": render_stage2, "stage3": render_stage3}
