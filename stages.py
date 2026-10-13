"""Per-item rendering for the two annotation stages.

Stage 1: free-form list of as many differences as the annotator can find.
Stage 2: the conversation + both drafts (target draft emphasized), then the merged category set
         (common edit types + genre-specific) asked as "asked or implied by the user" vs "not asked",
         given the conversation as context. (Saved under the DB stage key "stage2".)

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

def instruction_box(item):
    """Clearly-marked box showing the user's latest instruction for this draft, above the drafts.
    If there is no recorded instruction, the box is shown but left empty."""
    instr = (item.instruction or "").strip()
    body = (_html.escape(instr) if instr else
            '<span style="color:#8a8f98;font-style:italic">(no explicit instruction recorded for this draft)</span>')
    st.markdown(
        f'<div style="border:2px solid {RED};border-radius:10px;background:#FFF4E5;'
        f'padding:12px 16px;margin:4px 0 14px 0">'
        f'<div style="font-weight:800;color:{RED};font-size:0.92rem;letter-spacing:.4px;'
        f'margin-bottom:6px">LATEST INSTRUCTION FROM THE USER</div>'
        f'<div style="color:#121212;font-size:1.02rem;line-height:1.5;white-space:pre-wrap">{body}</div></div>',
        unsafe_allow_html=True)

def _lines_list(text):
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

def category_label(label, help_text, extra=""):
    st.markdown(
        f'<div style="font-size:1.05rem;font-weight:700;color:#121212;margin-top:10px">{_html.escape(label)}{extra}</div>'
        f'<div style="font-size:0.9rem;color:#333;margin:1px 0 4px 0">{_html.escape(help_text)}</div>',
        unsafe_allow_html=True)

# ------------------------------- Stage 1 -------------------------------
def render_stage1(ann_id, item, is_preview):
    callout("Find the differences between the original and the revised draft. For <b>each</b> difference, "
            "click <b>+ Add difference</b>, then fill in <b>both</b> boxes: the <b>difference</b> on the "
            "left, and your <b>reasoning and the line numbers</b> that show it (e.g. B2, B5) on the right. "
            "Add as many as you can find. <b>All boxes are required to continue.</b>")
    draft_pair(item)
    section_header("Differences")

    saved = (db.get_response(ann_id, item.pair_id, "stage1") or {}).get("differences", [])
    saved = [d if isinstance(d, dict) else {"difference": str(d), "reasoning": ""} for d in saved]
    nkey = f"s1n_{item.pair_id}"
    if nkey not in st.session_state:
        st.session_state[nkey] = max(1, len(saved))
    n = st.session_state[nkey]

    rows = []
    for i in range(n):
        prev = saved[i] if i < len(saved) else {}
        st.markdown(f'<div style="font-weight:700;margin-top:10px">Difference {i+1}</div>',
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            d = st.text_area("Difference", value=prev.get("difference", ""),
                             key=f"s1d_{item.pair_id}_{i}", height=110, label_visibility="collapsed",
                             placeholder="What changed between the drafts?")
        with c2:
            r = st.text_area("Reasoning and line numbers", value=prev.get("reasoning", ""),
                             key=f"s1r_{item.pair_id}_{i}", height=110, label_visibility="collapsed",
                             placeholder="Why is this a difference, and which lines show it? e.g. B2, B5")
        rows.append({"difference": d.strip(), "reasoning": r.strip()})

    a1, a2, _ = st.columns([1, 1, 4])
    if a1.button("➕ Add difference", key=f"s1add_{item.pair_id}"):
        st.session_state[nkey] = n + 1
        st.rerun()
    if a2.button("➖ Remove last", key=f"s1del_{item.pair_id}", disabled=(n <= 1)):
        st.session_state[nkey] = max(1, n - 1)
        st.rerun()

    if st.button("Save and continue", key=f"save_s1_{item.pair_id}", type="primary"):
        if not is_preview:
            incomplete = [i + 1 for i, rw in enumerate(rows) if not (rw["difference"] and rw["reasoning"])]
            if incomplete:
                st.warning("Please fill in both boxes for every difference (or remove empty rows with "
                           f"'Remove last'). Incomplete: difference {', '.join(map(str, incomplete))}.")
                return False
        cleaned = [rw for rw in rows if rw["difference"] and rw["reasoning"]]
        db.save_response(ann_id, item.pair_id, "stage1", {"differences": cleaned}, is_preview=is_preview)
        db.log_event(ann_id, "save", item.pair_id, "stage1")
        return True
    return False

# ============================================================================================
# DISABLED (kept for later) — original Stage 2: presence ratings (Absent / Present / Very present)
# with required line-number evidence for the key categories. Commented out while the study runs
# with two stages. To re-enable a three-stage flow:
#   1. Uncomment render_stage2 below.
#   2. Rename the ACTIVE render_stage2 (the asked/implied judgement, further down) back to
#      render_stage3 and change its DB stage key from "stage2" to "stage3".
#   3. Restore config.STAGES / STAGE_TITLES to include "stage3" and add it to RENDERERS.
#
# def render_stage2(ann_id, item, is_preview):
#     callout("For each category, say how present it is in the <b>revised draft (B)</b> "
#             "(<b>Absent / Present / Very present</b>). For some categories you will also be asked to add "
#             "<b>details, evidence, or remarks referring to line numbers</b> (for example <b>B2, B5</b> or "
#             f"<b>A3</b>) — <b style='color:{RED}'>required</b> where marked with a "
#             f"<b style='color:{RED}'>*</b>, optional for the rest. Definitions are shown under each category.")
#     draft_pair(item)
#     spacer(20)
#     saved = db.get_response(ann_id, item.pair_id, "stage2") or {}
#     saved_cats = saved.get("categories", {})
#     opts = taxonomy.PRESENCE_OPTIONS
#
#     cats = {}
#     required_ids = set()
#     for group, items in taxonomy.categories_for(item.genre):
#         # warm notice introducing the sections that require written evidence
#         if group == "Style and register":
#             callout("For the sections below, please add <b>details, evidence, or remarks referring to "
#                     "specific line numbers</b> (for example <b>B2, B5</b>). Where a category is marked "
#                     f"with a <b style='color:{RED}'>*</b>, this is <b>required</b> whenever you mark it "
#                     "<b>Present</b> or <b>Very present</b>; for the others it is optional but encouraged.")
#         group_header(group)
#         for cid, label, hlp in items:
#             prev = saved_cats.get(cid, {})
#             req = taxonomy.detail_required(group, cid)
#             if req:
#                 required_ids.add(cid)
#             star = f' <span style="color:{RED};font-weight:800">*</span>' if req else ""
#             category_label(label, hlp, extra=star)
#             c1, c2 = st.columns([3, 2])
#             with c1:
#                 cur = prev.get("presence")
#                 val = st.radio(label, opts, index=opts.index(cur) if cur in opts else None,
#                                horizontal=True, key=f"s2r_{item.pair_id}_{cid}",
#                                label_visibility="collapsed")
#             with c2:
#                 ph = ("details and line numbers, e.g. B2, B5 (required)" if req
#                       else "optional: details or remarks, line numbers e.g. B2, B5")
#                 lines = st.text_input("Details and line numbers", value=prev.get("lines", ""),
#                                       key=f"s2l_{item.pair_id}_{cid}",
#                                       placeholder=ph, label_visibility="collapsed")
#             cats[cid] = {"presence": val, "lines": lines.strip()}
#
#     section_header("What other kinds of edits do you see that are not covered above? Type N/A if none.")
#     other = st.text_area("Other edits", value=saved.get("other", ""), key=f"s2o_{item.pair_id}",
#                          height=90, label_visibility="collapsed",
#                          placeholder="Describe any other changes you notice.")
#
#     if st.button("Save and continue", key=f"save_s2_{item.pair_id}", type="primary"):
#         unanswered = [cid for cid, v in cats.items() if v["presence"] is None]
#         if unanswered and not is_preview:
#             st.warning(f"Please choose Absent, Present, or Very present for every category before "
#                        f"continuing. {len(unanswered)} still unanswered.")
#             return False
#         missing_detail = [cid for cid in required_ids
#                           if cats[cid]["presence"] in ("Present", "Very present") and not cats[cid]["lines"]]
#         if missing_detail and not is_preview:
#             labels = ", ".join(taxonomy.CATEGORY_LOOKUP.get(cid, (cid,))[0] for cid in missing_detail)
#             st.warning("For the categories marked with * that you rated Present or Very present, please add "
#                        f"details, evidence, or remarks referring to line numbers. Still needed: {labels}.")
#             return False
#         db.save_response(ann_id, item.pair_id, "stage2",
#                          {"categories": cats, "other": other.strip()}, is_preview=is_preview)
#         db.log_event(ann_id, "save", item.pair_id, "stage2")
#         return True
#     return False
# ============================================================================================

# ------------------------------- Stage 2 (conversation + asked/implied judgement) -------------------------------
# (Previously Stage 3; now the second and final stage, saved under the DB stage key "stage2".)
def _bubble(is_user, text):
    grad = USER_GRAD if is_user else AI_GRAD
    bub = "#E8F0FE" if is_user else "#E7F5EA"
    inner = PERSON_SVG if is_user else '<span style="color:#fff;font-weight:800;font-size:0.8rem">AI</span>'
    body = _html.escape(text or "").replace("\n", "<br>")
    avatar = (f'<div style="flex:0 0 36px;width:36px;height:36px;border-radius:50%;background:{grad};'
              f'display:flex;align-items:center;justify-content:center;'
              f'box-shadow:0 1px 4px rgba(0,0,0,.22)">{inner}</div>')
    bubble = (f'<div style="max-width:82%;background:{bub};border:1px solid rgba(0,0,0,.07);'
              f'border-radius:16px;padding:12px 16px;font-size:1.0rem;line-height:1.6;'
              f'color:#121212">{body}</div>')
    return (f'<div style="display:flex;gap:12px;align-items:flex-start;margin:12px 14px">'
            f'{avatar}{bubble}</div>')

def render_chat(item):
    try:
        conv = json.loads(item.conversation or "[]")
    except Exception:
        conv = []
    if not conv:
        conv = [{"role": "human", "text": item.instruction or "(no instruction recorded)"}]
    bubbles = [_bubble(m.get("role") == "human", m.get("text", "")) for m in conv]
    # conversation already includes the final turn's full AI reply (verbatim), so nothing is appended
    st.markdown(
        f'<div style="border:1px solid #d7dae0;border-radius:14px;overflow:auto;max-height:440px;'
        f'background:#fafbfc;padding:6px 0">' + "".join(bubbles) + "</div>",
        unsafe_allow_html=True)

def render_stage2(ann_id, item, is_preview):
    callout("Below is the conversation between a <b>human</b> and an <b>AI</b>, the user's latest "
            "instruction, and the two drafts. For <b>each difference you identified in Stage 1</b>, "
            "decide — given the conversation and instruction as context — whether that change was "
            "<b>asked</b>, <b>implied</b>, or <b>not asked or implied</b> by the user.", strong=True)

    section_header("Conversation between the human and the AI")
    render_chat(item)

    section_header("The two drafts — judge the revised draft (B)")
    instruction_box(item)
    draft_pair(item, big=True)

    opts = taxonomy.JUSTIFY_OPTIONS
    saved = db.get_response(ann_id, item.pair_id, "stage2") or {}
    saved_diffs = saved.get("differences", [])

    # The differences the annotator listed in Stage 1 become the rated items here.
    s1 = db.get_response(ann_id, item.pair_id, "stage1") or {}
    diffs = [d for d in s1.get("differences", [])
             if isinstance(d, dict) and d.get("difference")]

    section_header("For each difference you listed in Stage 1: was it asked or implied by the user?")
    answers = []
    if not diffs:
        st.info("No differences from Stage 1 are available for this pair yet."
                + ("  In admin preview, complete Stage 1 for this pair first to populate them."
                   if is_preview else ""))
    for i, d in enumerate(diffs):
        prev = saved_diffs[i] if i < len(saved_diffs) else {}
        reason = d.get("reasoning", "")
        st.markdown(
            f'<div style="font-size:1.05rem;font-weight:700;color:#121212;margin-top:12px">'
            f'Difference {i+1}: {_html.escape(d.get("difference",""))}</div>'
            + (f'<div style="font-size:0.9rem;color:#333;margin:1px 0 4px 0">'
               f'Your reasoning / lines: {_html.escape(reason)}</div>' if reason else ""),
            unsafe_allow_html=True)
        cur = prev.get("justify")
        val = st.radio(f"diff{i}", opts, index=opts.index(cur) if cur in opts else None,
                       horizontal=True, key=f"s2j_{item.pair_id}_{i}", label_visibility="collapsed")
        answers.append({"difference": d.get("difference", ""), "reasoning": reason, "justify": val})

    # ---- DISABLED (kept for later): rate the fixed taxonomy categories for asked/implied.
    # To re-enable, uncomment this block and save it alongside (or instead of) `differences`.
    # saved_cats = saved.get("categories", {})
    # cats = {}
    # for group, items in taxonomy.categories_for(item.genre):
    #     group_header(group)
    #     for cid, label, hlp in items:
    #         prev = saved_cats.get(cid, {})
    #         category_label(label, hlp)
    #         cur = prev.get("justify")
    #         val = st.radio(label, opts, index=opts.index(cur) if cur in opts else None,
    #                        horizontal=True, key=f"s2jc_{item.pair_id}_{cid}",
    #                        label_visibility="collapsed")
    #         cats[cid] = {"justify": val}
    # ------------------------------------------------------------------------------------

    section_header("Any additional remarks about this pair (optional)")
    remarks = st.text_area("Remarks", value=saved.get("remarks", ""), key=f"s2rm_{item.pair_id}",
                           height=90, label_visibility="collapsed", placeholder="Anything else worth noting.")

    section_header("If this were your own draft, how satisfied would you be with the revision? (optional)")
    satisfaction = st.text_area("Satisfaction", value=saved.get("satisfaction", ""),
                                key=f"s2s_{item.pair_id}", height=80, label_visibility="collapsed",
                                placeholder="Describe how satisfied you would be and why.")

    if st.button("Save and continue", key=f"save_s2_{item.pair_id}", type="primary"):
        unanswered = [i + 1 for i, a in enumerate(answers) if a["justify"] is None]
        if unanswered and not is_preview:
            st.warning("Please choose an option for every difference before continuing. "
                       f"Unanswered: difference {', '.join(map(str, unanswered))}.")
            return False
        db.save_response(ann_id, item.pair_id, "stage2",
                         {"differences": answers, "remarks": remarks.strip(),
                          "satisfaction": satisfaction.strip()}, is_preview=is_preview)
        db.log_event(ann_id, "save", item.pair_id, "stage2")
        return True
    return False

RENDERERS = {"stage1": render_stage1, "stage2": render_stage2}
