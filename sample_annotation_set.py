"""Build a curation-ready candidate pool for the annotation study from the 11K judged edits.

Source: the abstract-concept judge outputs (fiction + script judged pairs). We keep only annotation-
friendly pairs (length in range, English, at least one salient edit) and attach quality signals and
the judged edits + attribution labels so a human can hand-pick a high-quality pool.

Outputs (in this folder):
  annotation_candidates.json  - ranked candidate records with metadata + platform fields
  annotation_candidates.html  - focused review gallery (pair_id easy to copy, quality signals shown)

The final selection (a list of pair_ids the user picks) is loaded into the platform with load_items.py,
which fetches the full drafts and conversation from the corpus.
"""
import json, os, html, collections

PUA = "/Users/zarreennaowalreza/Desktop/files/Independent Research/Marwa/user-writing-platform/per-user-analysis-results"
HERE = os.path.dirname(os.path.abspath(__file__))
def L(f): return json.load(open(os.path.join(PUA, f)))

# which judged genres to consider (study genres present in the 11K); script is judged but not a study genre
KEEP_GENRES = ["fiction"]
LEN_MIN, LEN_MAX = 500, 6000
MIN_MAX_SALIENCE = 4

def is_english(t):
    a = [c for c in str(t) if c.isalpha()]
    return bool(a) and sum(c.isascii() for c in a) / len(a) >= 0.9

def main():
    inputs = L("abstract_attrib_inputs.json")
    extract = L("abstract_extract.json")
    attrib = L("abstract_attrib.json")
    instr = L("abstract_instructions.json")
    ext_moves = {r["pair_id"]: r.get("moves", []) for r in extract.values()}
    attr_by_pid = {r["pair_id"]: {a.get("idx"): a for a in r.get("attributions", [])}
                   for r in attrib.values() if not r.get("error")}

    cands = []
    for pid, rec in inputs.items():
        genre = rec.get("genre")
        if genre not in KEEP_GENRES:
            continue
        human, ai = rec.get("human", ""), rec.get("ai", "")
        if not (LEN_MIN <= len(human) <= LEN_MAX and LEN_MIN <= len(ai) <= LEN_MAX):
            continue
        if not (is_english(human) and is_english(ai)):
            continue
        emoves = ext_moves.get(pid, [])
        amap = attr_by_pid.get(pid, {})
        sals = [emoves[m["idx"]].get("salience", 0) for m in rec.get("moves", []) if m["idx"] < len(emoves)]
        sals = [s for s in sals if isinstance(s, (int, float))]
        if not sals or max(sals) < MIN_MAX_SALIENCE:
            continue
        labs = collections.Counter((amap.get(m["idx"], {}) or {}).get("label") for m in rec.get("moves", []))
        edits = []
        for m in rec.get("moves", []):
            em = emoves[m["idx"]] if m["idx"] < len(emoves) else {}
            att = amap.get(m["idx"], {}) or {}
            edits.append(dict(subtype=m.get("subtype"), direction=m.get("direction"),
                              salience=em.get("salience"), label=att.get("label"),
                              concept=em.get("concept") or m.get("concept"),
                              human_evidence=m.get("human_evidence"), ai_evidence=m.get("ai_evidence")))
        cands.append(dict(
            pair_id=pid, genre=genre,
            instruction_status=instr.get(pid, {}).get("instruction_status"),
            n_moves=len(rec.get("moves", [])), max_salience=max(sals),
            mean_salience=round(sum(sals) / len(sals), 2),
            n_unsolicited=labs.get("unsolicited", 0), n_warranted=labs.get("warranted", 0),
            n_general=labs.get("general_only", 0), n_contradicts=labs.get("contradicts", 0),
            human_len=len(human), ai_len=len(ai),
            instruction_preview=(rec.get("context") or "")[:400],
            edits=edits))

    # rank: most salient + most edits + presence of not-justified moves first
    cands.sort(key=lambda c: (c["max_salience"], c["n_moves"],
                              c["n_unsolicited"] + c["n_contradicts"]), reverse=True)
    json.dump(cands, open(os.path.join(HERE, "annotation_candidates.json"), "w"),
              ensure_ascii=False, indent=1)

    # focused review HTML
    def esc(s): return html.escape(str(s or ""))
    LC = {"warranted": "#2e7d32", "general_only": "#E8A03D", "unsolicited": "#E4695A",
          "contradicts": "#B23A36", None: "#888"}
    rows = []
    for c in cands:
        elist = "".join(
            f'<div class="e"><span class="b" style="background:{LC.get(e["label"])}">{esc(e["label"])}</span> '
            f'<b>{esc(e["subtype"])}</b> <span class="s">sal {esc(e["salience"])}</span>'
            f'<div class="ev">H: {esc(e["human_evidence"])}</div>'
            f'<div class="ev">AI: {esc(e["ai_evidence"])}</div></div>' for e in c["edits"])
        rows.append(
            f'<div class="card" data-status="{esc(c["instruction_status"])}">'
            f'<div class="h"><input class="pid" value="{esc(c["pair_id"])}" readonly onclick="this.select()">'
            f'<span class="p">{esc(c["genre"])}</span>'
            f'<span class="p">max sal {c["max_salience"]}</span>'
            f'<span class="p">{c["n_moves"]} edits</span>'
            f'<span class="p">unsol {c["n_unsolicited"]} / warr {c["n_warranted"]}</span>'
            f'<span class="p">{esc(c["instruction_status"])}</span>'
            f'<span class="p">len {c["human_len"]}/{c["ai_len"]}</span></div>'
            f'<details><summary>instruction preview</summary><pre>{esc(c["instruction_preview"])}</pre></details>'
            f'<div class="moves">{elist}</div></div>')
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Annotation candidates</title>
<style>body{{font-family:-apple-system,Segoe UI,sans-serif;margin:0;background:#f4f5f7;color:#1a1a1a}}
header{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:12px 18px}}
#w{{padding:16px;display:grid;gap:12px;max-width:1000px;margin:0 auto}}
.card{{background:#fff;border:1px solid #e2e4e8;border-radius:10px;padding:10px 12px}}
.h{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.pid{{font-family:monospace;font-size:12px;border:1px solid #ccc;border-radius:6px;padding:3px 6px;width:170px}}
.p{{font-size:11px;background:#eef1f5;border-radius:10px;padding:2px 8px}}
pre{{white-space:pre-wrap;background:#f7f8fa;padding:8px;border-radius:6px;font-size:12px;max-height:200px;overflow:auto}}
.moves{{margin-top:6px;display:grid;gap:6px}}
.e{{border-left:3px solid #ccc;padding:4px 8px;background:#fafbfc;font-size:12px}}
.b{{color:#fff;font-size:10px;padding:1px 7px;border-radius:9px}} .s{{color:#777;font-size:11px}}
.ev{{color:#333;margin-top:2px}}</style></head><body>
<header><b>Annotation candidates (fiction from the 11K judged edits)</b> &middot; {len(cands):,} pairs.
Click a pair_id to select it, copy the ones you want, and put them in selected_ids.txt for load_items.py.</header>
<div id="w">{"".join(rows)}</div></body></html>"""
    open(os.path.join(HERE, "annotation_candidates.html"), "w").write(page)
    print("candidates:", len(cands), "genres:", collections.Counter(c["genre"] for c in cands))
    print("wrote annotation_candidates.json and annotation_candidates.html")

if __name__ == "__main__":
    main()
