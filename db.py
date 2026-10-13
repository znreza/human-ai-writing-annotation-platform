"""Storage layer (SQLAlchemy ORM). Portable across SQLite (local) and Postgres (Supabase).

JSON payloads are stored as TEXT (json-encoded) to avoid dialect differences, so the same models
run unchanged on both backends. Switch backends by changing config.DATABASE_URL only.
"""
import json, secrets, string, datetime as dt
from sqlalchemy import (create_engine, String, Integer, Text, DateTime, Boolean, ForeignKey, select, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship

import config

class Base(DeclarativeBase):
    pass

def _now():
    return dt.datetime.utcnow()

# ------------------------- models -------------------------
class Annotator(Base):
    __tablename__ = "annotators"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))            # kept separate from responses
    role: Mapped[str] = mapped_column(String(16), default="annotator")  # annotator | admin
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False)    # admin/demo sessions
    prolific_pid: Mapped[str] = mapped_column(String(64), nullable=True, index=True)  # Prolific participant id
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)

class Item(Base):
    __tablename__ = "items"
    pair_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    genre: Mapped[str] = mapped_column(String(32))
    original: Mapped[str] = mapped_column(Text)
    revised: Mapped[str] = mapped_column(Text)
    instruction: Mapped[str] = mapped_column(Text, default="")
    prior_conversation: Mapped[str] = mapped_column(Text, default="")
    conversation: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of {role, text} turns
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    annotator_id: Mapped[str] = mapped_column(ForeignKey("annotators.id"))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.pair_id"))
    position: Mapped[int] = mapped_column(Integer)           # display order for this annotator

class Response(Base):
    """One row per (annotator, item, stage). payload holds the stage-specific answer as JSON text."""
    __tablename__ = "responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    annotator_id: Mapped[str] = mapped_column(ForeignKey("annotators.id"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.pair_id"), index=True)
    stage: Mapped[str] = mapped_column(String(16), index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    annotator_id: Mapped[str] = mapped_column(String(16), index=True)
    item_id: Mapped[str] = mapped_column(String(64), default="")
    stage: Mapped[str] = mapped_column(String(16), default="")
    action: Mapped[str] = mapped_column(String(32))
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)

# ------------------------- engine -------------------------
_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
if config.DATABASE_URL.startswith("sqlite"):
    # make sure the local db directory exists and is writable (avoids first-run write errors)
    import os as _os
    _p = config.DATABASE_URL.replace("sqlite:///", "")
    _os.makedirs(_os.path.dirname(_p) or ".", exist_ok=True)
engine = create_engine(config.DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

def init_db():
    Base.metadata.create_all(engine)
    _ensure_schema_migrations()

def _ensure_schema_migrations():
    """Lightweight additive migrations for tables that already exist (create_all never ALTERs).
    Adds columns introduced after the first deploy. Safe to run every startup; no-ops when current."""
    from sqlalchemy import inspect, text
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("annotators")}
    except Exception:
        return  # table not created yet (first run handles it via create_all above)
    if "prolific_pid" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE annotators ADD COLUMN prolific_pid VARCHAR(64)"))

# ------------------------- helpers -------------------------
_ALPHABET = string.ascii_uppercase + string.digits

def _new_id():
    return "WM-" + "".join(secrets.choice(_ALPHABET) for _ in range(4))

def create_annotator(name, role="annotator", is_preview=False, prolific_pid=None):
    with SessionLocal() as s:
        aid = _new_id()
        while s.get(Annotator, aid):
            aid = _new_id()
        a = Annotator(id=aid, name=name.strip()[:200], role=role, is_preview=is_preview,
                      prolific_pid=(prolific_pid.strip()[:64] if prolific_pid else None))
        s.add(a); s.commit()
        return aid

def get_annotator(aid):
    with SessionLocal() as s:
        return s.get(Annotator, aid)

def get_annotator_by_prolific(pid):
    """Return the existing annotator for a Prolific participant id, or None. Lets a returning
    participant resume automatically from the same Prolific link. Ignores preview rows."""
    if not pid:
        return None
    with SessionLocal() as s:
        return s.scalar(select(Annotator).where(
            Annotator.prolific_pid == pid.strip(), Annotator.is_preview == False))

def assign_items(annotator_id, per_genre=None, genres=None, seed=None):
    """Assign the SHARED fixed set to an annotator: EVERY annotator sees ALL active items, in one
    stable order (same for everyone). Curate the shown set by choosing which items are active (see
    load_items.py --deactivate-others). Idempotent: skips if already assigned.

    (Previously each annotator got a per-genre random sample — different, overlapping sets. That
    behaviour is kept commented below for easy restore.)"""
    with SessionLocal() as s:
        existing = s.scalars(select(Assignment).where(Assignment.annotator_id == annotator_id)).all()
        if existing:
            return len(existing)
        # fixed shared order: by study-genre rank, then pair_id — deterministic and identical per user
        rank = {g: i for i, g in enumerate(config.STUDY_GENRES)}
        rows = s.execute(select(Item.pair_id, Item.genre).where(Item.active == True)).all()
        chosen = [pid for pid, _ in sorted(rows, key=lambda r: (rank.get(r[1], 99), r[0]))]
        for pos, iid in enumerate(chosen):
            s.add(Assignment(annotator_id=annotator_id, item_id=iid, position=pos))
        s.commit()
        return len(chosen)

        # --- DISABLED (kept for later): per-annotator random sample of per_genre items per genre ---
        # import random
        # per_genre = per_genre if per_genre is not None else config.PER_GENRE
        # genres = genres if genres is not None else config.STUDY_GENRES
        # rng = random.Random(seed if seed is not None else annotator_id)
        # chosen = []
        # for g in genres:
        #     ids = list(s.scalars(select(Item.pair_id).where(Item.active == True, Item.genre == g)).all())
        #     rng.shuffle(ids)
        #     chosen.extend(ids[:per_genre])
        # rng.shuffle(chosen)  # interleave genres in display order
        # for pos, iid in enumerate(chosen):
        #     s.add(Assignment(annotator_id=annotator_id, item_id=iid, position=pos))
        # s.commit()
        # return len(chosen)

def get_assignment(annotator_id):
    """Return ordered list of Item objects assigned to this annotator."""
    with SessionLocal() as s:
        rows = s.execute(
            select(Item, Assignment.position)
            .join(Assignment, Assignment.item_id == Item.pair_id)
            .where(Assignment.annotator_id == annotator_id)
            .order_by(Assignment.position)
        ).all()
        return [r[0] for r in rows]

def save_response(annotator_id, item_id, stage, payload, is_preview=False):
    with SessionLocal() as s:
        row = s.scalar(select(Response).where(
            Response.annotator_id == annotator_id,
            Response.item_id == item_id,
            Response.stage == stage))
        if row is None:
            row = Response(annotator_id=annotator_id, item_id=item_id, stage=stage, is_preview=is_preview)
            s.add(row)
        row.payload = json.dumps(payload, ensure_ascii=False)
        row.is_preview = is_preview
        s.commit()

def get_response(annotator_id, item_id, stage):
    with SessionLocal() as s:
        row = s.scalar(select(Response).where(
            Response.annotator_id == annotator_id,
            Response.item_id == item_id,
            Response.stage == stage))
        return json.loads(row.payload) if row else None

def stage_completed_count(annotator_id, stage):
    with SessionLocal() as s:
        return s.scalar(select(func.count()).select_from(Response).where(
            Response.annotator_id == annotator_id, Response.stage == stage)) or 0

def log_event(annotator_id, action, item_id="", stage=""):
    with SessionLocal() as s:
        s.add(Event(annotator_id=annotator_id, action=action, item_id=item_id, stage=stage))
        s.commit()

# ------------------------- item loading + admin export -------------------------
def upsert_items(items):
    """items: list of dicts with pair_id, genre, original, revised, instruction, prior_conversation."""
    n = 0
    with SessionLocal() as s:
        for it in items:
            row = s.get(Item, it["pair_id"])
            if row is None:
                row = Item(pair_id=it["pair_id"]); s.add(row)
            row.genre = it.get("genre", "")
            row.original = it.get("original", "")
            row.revised = it.get("revised", "")
            row.instruction = it.get("instruction", "")
            row.prior_conversation = it.get("prior_conversation", "")
            conv = it.get("conversation", [])
            row.conversation = conv if isinstance(conv, str) else json.dumps(conv, ensure_ascii=False)
            row.active = it.get("active", True)
            n += 1
        s.commit()
    return n

def counts():
    with SessionLocal() as s:
        return dict(
            items=s.scalar(select(func.count()).select_from(Item)) or 0,
            annotators=s.scalar(select(func.count()).select_from(Annotator).where(Annotator.is_preview == False)) or 0,
            responses=s.scalar(select(func.count()).select_from(Response).where(Response.is_preview == False)) or 0,
        )

def export_rows(include_preview=False):
    """Flat list of response rows joined with annotator + item metadata, for CSV export."""
    with SessionLocal() as s:
        q = select(Response, Annotator, Item).join(
            Annotator, Annotator.id == Response.annotator_id).join(
            Item, Item.pair_id == Response.item_id)
        if not include_preview:
            q = q.where(Response.is_preview == False)
        out = []
        for resp, ann, item in s.execute(q).all():
            out.append(dict(
                annotator_id=ann.id, prolific_pid=ann.prolific_pid or "", role=ann.role,
                is_preview=resp.is_preview, item_id=item.pair_id, genre=item.genre, stage=resp.stage,
                payload=resp.payload, updated_at=resp.updated_at.isoformat()))
        return out
