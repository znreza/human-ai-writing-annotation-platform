"""Sample academic and application candidate pairs directly from the WildChat corpus (these genres are
not in the abstract-judge 11K). Same annotation-friendly quality filters as the fiction sampler:
length in range, English, human-authored draft, and a genuine AI revision.

Outputs (in this folder):
  annotation_candidates_academic.json, annotation_candidates_application.json  - curation metadata
  annotation_candidates_corpus.html                                            - review gallery
  corpus_pairs_index.json  - pair_id -> {conv,user,turn_id,genre} so load_items.py can rebuild them
"""
import glob, json, os, re, hashlib, html, collections

ROOTP = "/Users/zarreennaowalreza/Desktop/files/Independent Research/Marwa/user-writing-platform"
HERE = os.path.dirname(os.path.abspath(__file__))
GENRES = ["academic", "application"]
LEN_MIN, LEN_MAX = 500, 6000
MAX_PER_GENRE = 400

def genre_of(d):
    return d.get('genre') or next((L.get('genre') for L in (d.get('draft_lists') or []) if L.get('genre')), None)
def norm(s): return re.sub(r'\s+', ' ', s or '').strip()
def is_english(t):
    a = [c for c in str(t) if c.isalpha()]
    return bool(a) and sum(c.isascii() for c in a) / len(a) >= 0.9

def main():
    files = glob.glob(ROOTP + "/convos/wildchat/*/*/draft_lists.json") + \
            glob.glob(ROOTP + "/convos/corpus/*/*/draft_lists.json")
    import random; random.Random(11).shuffle(files)
    cands = {g: [] for g in GENRES}
    index = {}
    seen = set()
    for f in files:
        if all(len(cands[g]) >= MAX_PER_GENRE for g in GENRES):
            break
        try: d = json.load(open(f))
        except Exception: continue
        g = genre_of(d)
        if g not in GENRES or len(cands[g]) >= MAX_PER_GENRE:
            continue
        conv = d.get('conversation_id') or f.split('/')[-2]
        user = d.get('user_id') or f.split('/')[-3]
        turns = {t.get('turn_id'): t for t in d.get('turns', [])}
        for L in d.get('draft_lists', []):
            for v in L.get('versions', []):
                h, a = v.get('human_draft'), v.get('assistant_draft')
                if not (h and a): continue
                if not (LEN_MIN <= len(h) <= LEN_MAX and LEN_MIN <= len(a) <= LEN_MAX): continue
                if v.get('human_draft_provenance') != 'human_authored': continue
                if norm(h)[:200] == norm(a)[:200]: continue          # not a no-op
                if not (is_english(h) and is_english(a)): continue
                key = hashlib.md5((h[:200] + a[:200]).encode()).hexdigest()
                if key in seen: continue
                seen.add(key)
                tid = v.get('turn_id')
                instr = norm(turns.get(tid, {}).get('human_content'))
                pid = conv[:12] + '_' + hashlib.sha1((h + a).encode()).hexdigest()[:6]
                cands[g].append(dict(pair_id=pid, genre=g, instruction_status="corpus",
                                     human_len=len(h), ai_len=len(a),
                                     instruction_preview=instr[:400],
                                     human_head=norm(h)[:300], ai_head=norm(a)[:300]))
                index[pid] = dict(conv=conv, user=user, turn_id=tid, genre=g)
                if len(cands[g]) >= MAX_PER_GENRE: break
            if len(cands[g]) >= MAX_PER_GENRE: break

    for g in GENRES:
        cands[g].sort(key=lambda c: c["human_len"], reverse=True)
        json.dump(cands[g], open(os.path.join(HERE, f"annotation_candidates_{g}.json"), "w"),
                  ensure_ascii=False, indent=1)
    # merge into a shared corpus index (keep any existing entries)
    idx_path = os.path.join(HERE, "corpus_pairs_index.json")
    existing = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    existing.update(index)
    json.dump(existing, open(idx_path, "w"), ensure_ascii=False)

    # review HTML
    def esc(s): return html.escape(str(s or ""))
    rows = []
    for g in GENRES:
        for c in cands[g]:
            rows.append(
                f'<div class="card" data-genre="{g}"><div class="h">'
                f'<input class="pid" value="{esc(c["pair_id"])}" readonly onclick="this.select()">'
                f'<span class="p">{g}</span><span class="p">len {c["human_len"]}/{c["ai_len"]}</span></div>'
                f'<details><summary>instruction preview</summary><pre>{esc(c["instruction_preview"])}</pre></details>'
                f'<div class="two"><div><b>Human</b><div class="t">{esc(c["human_head"])}...</div></div>'
                f'<div><b>AI</b><div class="t">{esc(c["ai_head"])}...</div></div></div></div>')
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Corpus candidates (academic + application)</title>
<style>body{{font-family:-apple-system,Segoe UI,sans-serif;margin:0;background:#f4f5f7;color:#1a1a1a}}
header{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:12px 18px}}
#w{{padding:16px;display:grid;gap:12px;max-width:1000px;margin:0 auto}}
.card{{background:#fff;border:1px solid #e2e4e8;border-radius:10px;padding:10px 12px}}
.h{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.pid{{font-family:monospace;font-size:12px;border:1px solid #ccc;border-radius:6px;padding:3px 6px;width:170px}}
.p{{font-size:11px;background:#eef1f5;border-radius:10px;padding:2px 8px}}
pre{{white-space:pre-wrap;background:#f7f8fa;padding:8px;border-radius:6px;font-size:12px;max-height:160px;overflow:auto}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:6px}}
.t{{font-size:12px;color:#333;background:#fafbfc;padding:8px;border-radius:6px}}</style>
<script>function fg(g){{for(const c of document.querySelectorAll('.card'))c.style.display=(!g||c.dataset.genre===g)?'':'none'}}</script>
</head><body>
<header><b>Corpus candidates: academic + application</b> &middot; academic {len(cands['academic'])}, application {len(cands['application'])}.
Filter: <button onclick="fg('')">all</button> <button onclick="fg('academic')">academic</button>
<button onclick="fg('application')">application</button> &middot; click a pair_id to copy it into selected_ids.txt.</header>
<div id="w">{"".join(rows)}</div></body></html>"""
    open(os.path.join(HERE, "annotation_candidates_corpus.html"), "w").write(page)
    print("candidates:", {g: len(cands[g]) for g in GENRES}, "| index entries:", len(existing))
    print("wrote annotation_candidates_academic.json, annotation_candidates_application.json, "
          "annotation_candidates_corpus.html, corpus_pairs_index.json")

if __name__ == "__main__":
    main()
