"""Full-content candidate galleries for manual curation. Shows, for each candidate pair, the FULL
instruction/conversation, the FULL human draft (A), and the FULL AI draft (B) — nothing truncated —
pulled straight from the corpus. Fiction also shows its judged edits.

Pools: fiction = all candidates (ranked by salience); academic & application = top 150 each (ranked by
draft length). Each pair is a collapsible block with a copyable pair_id.

Outputs:
  annotation_candidates_fiction_full.html
  annotation_candidates_academic_full.html
  annotation_candidates_application_full.html
"""
import json, os, glob, re, hashlib, html as _html

HERE = os.path.dirname(os.path.abspath(__file__))
PUA = "/Users/zarreennaowalreza/Desktop/files/Independent Research/Marwa/user-writing-platform/per-user-analysis-results"
ROOTP = "/Users/zarreennaowalreza/Desktop/files/Independent Research/Marwa/user-writing-platform"
ACADEMIC_APP_TOP = 150

def esc(s): return _html.escape(str(s or ""))
def brk(s): return esc(s).replace("\n", "<br>")

# ---------- pid -> (conv, user, turn_id) ----------
def fiction_index():
    ext = json.load(open(os.path.join(PUA, "abstract_extract.json")))
    instr = json.load(open(os.path.join(PUA, "abstract_instructions.json")))
    idx = {}
    for r in ext.values():
        idx[r["pair_id"]] = dict(conv=r.get("conv"), user=r.get("user"),
                                 turn_id=(instr.get(r["pair_id"], {}) or {}).get("turn_id"))
    return idx

def corpus_index():
    p = os.path.join(HERE, "corpus_pairs_index.json")
    return json.load(open(p)) if os.path.exists(p) else {}

def _find_file(user, conv):
    for base in ("wildchat", "corpus"):
        p = os.path.join(ROOTP, "convos", base, user or "", conv or "", "draft_lists.json")
        if os.path.exists(p):
            return p
    hits = glob.glob(os.path.join(ROOTP, f"convos/*/*/{conv}/draft_lists.json"))
    return hits[0] if hits else None

def resolve_full(pid, meta):
    """Return (human, ai, instruction, conversation[list]) with FULL text, or None."""
    f = _find_file(meta.get("user"), meta.get("conv"))
    if not f:
        return None
    try:
        d = json.load(open(f))
    except Exception:
        return None
    turns = {t.get("turn_id"): t for t in d.get("turns", [])}
    tid = meta.get("turn_id")
    for L in d.get("draft_lists", []):
        for v in L.get("versions", []):
            h, a = v.get("human_draft"), v.get("assistant_draft")
            if not (h and a):
                continue
            if meta["conv"][:12] + "_" + hashlib.sha1((h + a).encode()).hexdigest()[:6] != pid:
                continue
            vtid = v.get("turn_id") if tid is None else tid
            conv = []
            for t in sorted(x for x in turns if x is not None and (vtid is None or x <= vtid)):
                hc = (turns[t].get("human_content") or "").strip()
                if hc: conv.append(("human", hc))
                if vtid is not None and t < vtid:
                    ac = (turns[t].get("assistant_content") or "").strip()
                    if ac: conv.append(("ai", ac))
            conv.append(("ai", a.strip()))   # final turn's AI reply = the revised draft
            instruction = (turns.get(vtid, {}).get("human_content") or "").strip()
            return (h.strip(), a.strip(), instruction, conv)
    return None

def chat_html(conv):
    rows = []
    for role, text in conv:
        is_user = role == "human"
        bg = "#F2F7FF" if is_user else "#F0F8F2"
        who = "HUMAN" if is_user else "AI"
        col = "#2E5AA8" if is_user else "#2F7C4F"
        rows.append(f'<div style="padding:10px 12px;background:{bg};border-bottom:1px solid #e9ecf1">'
                    f'<div style="font-weight:700;font-size:12px;color:{col};margin-bottom:3px">{who}</div>'
                    f'<div style="font-size:13px;line-height:1.5">{brk(text)}</div></div>')
    return ('<div style="border:1px solid #d7dae0;border-radius:10px;overflow:auto;max-height:420px">'
            + "".join(rows) + "</div>")

def draft_html(text, label, color):
    return (f'<div style="flex:1;min-width:300px"><div style="font-weight:700;margin:6px 0;color:{color}">{label}</div>'
            f'<div style="border:1px solid #e2e4e8;border-radius:8px;background:#fff;padding:10px;'
            f'max-height:420px;overflow:auto;font-size:13px;line-height:1.55;white-space:pre-wrap">{esc(text)}</div></div>')

def edits_html(edits):
    if not edits:
        return ""
    LC = {"warranted": "#2e7d32", "general_only": "#E8A03D", "unsolicited": "#E4695A", "contradicts": "#B23A36"}
    out = []
    for e in edits:
        lab = e.get("label")
        out.append(f'<div style="border-left:3px solid #ccc;padding:4px 8px;margin:4px 0;background:#fafbfc;font-size:12px">'
                   f'<span style="background:{LC.get(lab,"#888")};color:#fff;border-radius:9px;padding:1px 7px;font-size:10px">{esc(lab)}</span> '
                   f'<b>{esc(e.get("subtype"))}</b> <span style="color:#777">sal {esc(e.get("salience"))}</span>'
                   f'<div>H: {esc(e.get("human_evidence"))}</div><div>AI: {esc(e.get("ai_evidence"))}</div></div>')
    return '<div style="margin-top:8px"><b style="font-size:13px">Judged edits</b>' + "".join(out) + "</div>"

def build_page(title, note, entries):
    cards = []
    for e in entries:
        signals = e["signals"]
        cards.append(
            f'<details style="background:#fff;border:1px solid #e2e4e8;border-radius:10px;margin:10px 0;padding:6px 12px">'
            f'<summary style="font-size:14px;font-weight:700;cursor:pointer">'
            f'{esc(e["pair_id"])} &nbsp;<span style="font-weight:400;color:#555">{esc(signals)}</span></summary>'
            f'<div style="padding:8px 2px">'
            f'<input value="{esc(e["pair_id"])}" readonly onclick="this.select()" '
            f'style="font-family:monospace;font-size:13px;border:1px solid #ccc;border-radius:6px;padding:4px 8px;width:220px">'
            f'<div style="font-weight:700;margin:10px 0 4px">Conversation (full)</div>{e["chat"]}'
            f'<div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:8px">{e["drafts"]}</div>'
            f'{e["edits"]}</div></details>')
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{esc(title)}</title>'
            f'<style>body{{font-family:-apple-system,Segoe UI,sans-serif;margin:0;background:#f4f5f7;color:#1a1a1a}}'
            f'header{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:12px 18px}}'
            f'#w{{padding:16px;max-width:1100px;margin:0 auto}}</style></head><body>'
            f'<header><b>{esc(title)}</b> &middot; {esc(note)} &middot; click a pair_id to copy it into selected_ids.txt</header>'
            f'<div id="w">{"".join(cards)}</div></body></html>')

def build_genre(genre, cand_file, index, limit, rank_key):
    cands = json.load(open(os.path.join(HERE, cand_file)))
    cands = sorted(cands, key=rank_key, reverse=True)
    if limit:
        cands = cands[:limit]
    entries, missing = [], 0
    for c in cands:
        pid = c["pair_id"]
        meta = index.get(pid)
        res = resolve_full(pid, meta) if meta else None
        if not res:
            missing += 1
            continue
        human, ai, instr, conv = res
        drafts = draft_html(human, "Original draft (A)", "#333") + draft_html(ai, "Target revised draft (B)", "#B23A36")
        if genre == "fiction":
            sig = f'{c.get("n_moves",0)} edits · max salience {c.get("max_salience","")} · {c.get("instruction_status","")}'
            ed = edits_html(c.get("edits"))
        else:
            sig = f'human {c.get("human_len","")} / AI {c.get("ai_len","")} chars'
            ed = ""
        entries.append(dict(pair_id=pid, signals=sig, chat=chat_html(conv), drafts=drafts, edits=ed))
    out = os.path.join(HERE, f"annotation_candidates_{genre}_full.html")
    note = f"{len(entries)} candidates (full content)"
    open(out, "w").write(build_page(f"{genre.capitalize()} candidates", note, entries))
    print(f"{genre}: wrote {len(entries)} (missing {missing}) -> {os.path.basename(out)} "
          f"({os.path.getsize(out)/1e6:.1f} MB)")

def main():
    fic_idx = fiction_index()
    corp_idx = corpus_index()
    build_genre("fiction", "annotation_candidates.json", fic_idx, None,
                rank_key=lambda c: (c.get("max_salience", 0), c.get("n_moves", 0)))
    build_genre("academic", "annotation_candidates_academic.json", corp_idx, ACADEMIC_APP_TOP,
                rank_key=lambda c: c.get("human_len", 0) + c.get("ai_len", 0))
    build_genre("application", "annotation_candidates_application.json", corp_idx, ACADEMIC_APP_TOP,
                rank_key=lambda c: c.get("human_len", 0) + c.get("ai_len", 0))

if __name__ == "__main__":
    main()
