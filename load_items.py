"""Load a curated set of pairs into the platform database (config.DATABASE_URL: SQLite locally,
Supabase Postgres in production). For each selected pair_id it fetches the full human draft, AI draft,
operative instruction, and turn-by-turn conversation from the corpus, then upserts an Item.

Usage:
  python load_items.py selected_ids.txt        # one pair_id per line (# comments allowed)
  python load_items.py --deactivate-others selected_ids.txt   # also mark all other items inactive

Selected pair_ids come from annotation_candidates.html / .json (the sampler output).
"""
import sys, os, glob, json, re, hashlib
import config, db

PUA = "/Users/zarreennaowalreza/Desktop/files/Independent Research/Marwa/user-writing-platform/per-user-analysis-results"
ROOTP = "/Users/zarreennaowalreza/Desktop/files/Independent Research/Marwa/user-writing-platform"
HERE = os.path.dirname(os.path.abspath(__file__))
MSG_CAP = 6000

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

def _pid_index():
    """pair_id -> (conv, user, turn_id, genre) from the judge outputs (fiction/script) and, if present,
    the corpus index built by sample_corpus_genres.py (academic/application)."""
    ext = json.load(open(os.path.join(PUA, "abstract_extract.json")))
    instr = json.load(open(os.path.join(PUA, "abstract_instructions.json")))
    idx = {}
    for r in ext.values():
        idx[r["pair_id"]] = dict(conv=r.get("conv"), user=r.get("user"), genre=r.get("genre"),
                                 turn_id=(instr.get(r["pair_id"], {}) or {}).get("turn_id"))
    corpus_idx = os.path.join(HERE, "corpus_pairs_index.json")
    if os.path.exists(corpus_idx):
        idx.update(json.load(open(corpus_idx)))
    return idx

def _find_file(user, conv):
    for base in ("wildchat", "corpus"):
        p = os.path.join(ROOTP, "convos", base, user or "", conv or "", "draft_lists.json")
        if os.path.exists(p):
            return p
    # fallback: glob by conv
    hits = glob.glob(os.path.join(ROOTP, f"convos/*/*/{conv}/draft_lists.json"))
    return hits[0] if hits else None

def _build_record(pid, meta):
    f = _find_file(meta.get("user"), meta.get("conv"))
    if not f:
        return None
    d = json.load(open(f))
    turns = {t.get("turn_id"): t for t in d.get("turns", [])}
    tid = meta.get("turn_id")
    for L in d.get("draft_lists", []):
        for v in L.get("versions", []):
            h, a = v.get("human_draft"), v.get("assistant_draft")
            if not (h and a):
                continue
            cand = (meta["conv"][:12] + "_" + hashlib.sha1((h + a).encode()).hexdigest()[:6])
            if cand != pid:
                continue
            vtid = v.get("turn_id") if tid is None else tid
            conversation = []
            for t in sorted(x for x in turns if x is not None and (vtid is None or x <= vtid)):
                hc = clean_draft(turns[t].get("human_content"))
                if hc: conversation.append({"role": "human", "text": hc[:MSG_CAP]})
                if vtid is not None and t < vtid:
                    ac = clean_draft(turns[t].get("assistant_content"))
                    if ac: conversation.append({"role": "ai", "text": ac[:MSG_CAP]})
            return dict(pair_id=pid, genre=meta.get("genre", ""), original=clean_draft(h), revised=clean_draft(a),
                        instruction=norm(turns.get(vtid, {}).get("human_content"))[:1000],
                        conversation=conversation, active=True)
    return None

def main():
    args = [a for a in sys.argv[1:]]
    deactivate = "--deactivate-others" in args
    args = [a for a in args if not a.startswith("--")]
    if not args:
        print("usage: python load_items.py [--deactivate-others] selected_ids.txt"); return
    ids = []
    for ln in open(args[0]):
        ln = ln.split("#")[0].strip()
        if ln: ids.append(ln)
    print("selected pair_ids:", len(ids))

    db.init_db()
    idx = _pid_index()
    records, missing = [], []
    for pid in ids:
        meta = idx.get(pid)
        rec = _build_record(pid, meta) if meta else None
        (records if rec else missing).append(rec or pid)
    n = db.upsert_items(records) if records else 0
    print("loaded/updated items:", n)
    if missing:
        print("could NOT resolve %d pair_ids (not found in corpus):" % len(missing))
        for m in missing[:20]:
            print("  -", m)

    if deactivate and records:
        from sqlalchemy import update
        keep = {r["pair_id"] for r in records}
        with db.SessionLocal() as s:
            for it in s.query(db.Item).all():
                it.active = it.pair_id in keep
            s.commit()
        print("marked non-selected items inactive; active items:",
              db.SessionLocal().query(db.Item).filter(db.Item.active == True).count())
    print("DB:", config.DATABASE_URL)

if __name__ == "__main__":
    main()
