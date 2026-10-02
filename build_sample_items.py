"""Regenerate sample_items.json for the THREE studied genres (fiction, academic, application),
each with a turn-based conversation (human + AI) for the Stage 3 chat view. Builds a pool larger than
PER_GENRE so annotators get different (overlapping, non-identical) sets. Demo only; the real study
builder will sample a larger pool from the corpus. Run:  python build_sample_items.py
"""
import glob, json, re, hashlib, random

ROOTP = "/Users/zarreennaowalreza/Desktop/files/Independent Research/Marwa/user-writing-platform"
OUT = "/Users/zarreennaowalreza/Desktop/files/Independent Research/Marwa/annotation-platform/sample_items.json"
STUDY_GENRES = ["fiction", "academic", "application"]
POOL_PER_GENRE = 8          # > PER_GENRE (4) so assigned sets vary across annotators
MSG_CAP = 6000

def genre_of(d):
    return d.get('genre') or next((L.get('genre') for L in (d.get('draft_lists') or []) if L.get('genre')), None)
def norm(s): return re.sub(r'\s+', ' ', s or '').strip()
def clean_draft(s):
    """Collapse spaces/tabs but PRESERVE line breaks, so drafts can be numbered per line."""
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in s.split("\n")]
    out, blank = [], 0
    for ln in lines:
        if ln == "":
            blank += 1
            if blank <= 1: out.append("")
        else:
            blank = 0; out.append(ln)
    return "\n".join(out).strip()

def build():
    files = glob.glob(ROOTP + "/convos/wildchat/*/*/draft_lists.json")
    random.Random(7).shuffle(files)
    picks = {g: [] for g in STUDY_GENRES}
    seen = set()
    for f in files:
        if all(len(picks[g]) >= POOL_PER_GENRE for g in STUDY_GENRES):
            break
        try: d = json.load(open(f))
        except Exception: continue
        g = genre_of(d)
        if g not in STUDY_GENRES or len(picks[g]) >= POOL_PER_GENRE:
            continue
        conv = d.get('conversation_id') or f.split('/')[-2]
        turns = {t.get('turn_id'): t for t in d.get('turns', [])}
        for L in d.get('draft_lists', []):
            for v in L.get('versions', []):
                h, a = v.get('human_draft'), v.get('assistant_draft')
                if not (h and a) or len(h) < 400 or len(a) < 400: continue
                tid = v.get('turn_id')
                if tid is None or tid < 1: continue
                key = hashlib.md5((h[:200] + a[:200]).encode()).hexdigest()
                if key in seen: continue
                seen.add(key)
                conversation = []
                for t in sorted(x for x in turns if x is not None and x <= tid):
                    hc = clean_draft(turns[t].get('human_content'))
                    if hc: conversation.append({"role": "human", "text": hc[:MSG_CAP]})
                    if t < tid:
                        ac = clean_draft(turns[t].get('assistant_content'))
                        if ac: conversation.append({"role": "ai", "text": ac[:MSG_CAP]})
                if len(conversation) < 2:
                    continue
                pid = conv[:12] + '_' + hashlib.sha1((h + a).encode()).hexdigest()[:6]
                picks[g].append(dict(pair_id=pid, genre=g, original=clean_draft(h), revised=clean_draft(a),
                                     instruction=norm(turns[tid].get('human_content'))[:1000],
                                     conversation=conversation))
                break
            if len(picks[g]) >= POOL_PER_GENRE:
                break
    out = [it for g in STUDY_GENRES for it in picks[g]]
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("wrote", len(out), "items;", {g: len(picks[g]) for g in STUDY_GENRES})

if __name__ == '__main__':
    build()
