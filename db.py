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

# ------------------------- helpers -------------------------
_ALPHABET = string.ascii_uppercase + string.digits

def _new_id():
    return "WM-" + "".join(secrets.choice(_ALPHABET) for _ in range(4))

def create_annotator(name, role="annotator", is_preview=False):
    with SessionLocal() as s:
        aid = _new_id()
        while s.get(Annotator, aid):
            aid = _new_id()
        a = Annotator(id=aid, name=name.strip()[:200], role=role, is_preview=is_preview)
        s.add(a); s.commit()
        return aid

def get_annotator(aid):
    with SessionLocal() as s:
        return s.get(Annotator, aid)

def assign_items(annotator_id, per_genre=None, genres=None, seed=None):
    """Assign per_genre active items from each studied genre to an annotator. Sampling is seeded by the
    annotator id, so different annotators get different (overlapping, non-identical) sets. Same set is
    reused across all stages. Idempotent: skips if already assigned."""
    import random
    per_genre = per_genre if per_genre is not None else config.PER_GENRE
    genres = genres if genres is not None else config.STUDY_GENRES
    with SessionLocal() as s:
        existing = s.scalars(select(Assignment).where(Assignment.annotator_id == annotator_id)).all()
        if existing:
            return len(existing)
        rng = random.Random(seed if seed is not None else annotator_id)
        chosen = []
        for g in genres:
            ids = list(s.scalars(select(Item.pair_id).where(Item.active == True, Item.genre == g)).all())
            rng.shuffle(ids)
            chosen.extend(ids[:per_genre])
        rng.shuffle(chosen)  # interleave genres in display order
        for pos, iid in enumerate(chosen):
            s.add(Assignment(annotator_id=annotator_id, item_id=iid, position=pos))
        s.commit()
        return len(chosen)

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
                annotator_id=ann.id, role=ann.role, is_preview=resp.is_preview,
                item_id=item.pair_id, genre=item.genre, stage=resp.stage,
                payload=resp.payload, updated_at=resp.updated_at.isoformat()))
        return out
