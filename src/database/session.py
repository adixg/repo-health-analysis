from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.database.models import Base

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE repositories "
                "ADD COLUMN IF NOT EXISTS issues_last_synced_at TIMESTAMPTZ"
            )
        )
        conn.execute(text("ALTER TABLE repositories ALTER COLUMN id TYPE BIGINT"))
        issues_table = conn.execute(
            text("SELECT to_regclass('public.issues') IS NOT NULL")
        ).scalar()
        if issues_table:
            conn.execute(text("ALTER TABLE issues ALTER COLUMN id TYPE BIGINT"))
            conn.execute(text("ALTER TABLE issues ALTER COLUMN repository_id TYPE BIGINT"))


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
