"""
Database engine and session management.

Uses `config.settings.Config.DATABASE_URL`. Render injects DATABASE_URL
automatically when you attach a Postgres instance to this service (see
render.yaml). Locally, with no DATABASE_URL set, this falls back to a
SQLite file so you can run the app without provisioning Postgres first.
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config.settings import config

# Render's DATABASE_URL sometimes starts with postgres:// ; SQLAlchemy 2.x
# requires postgresql://
_db_url = config.DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}

engine = create_engine(_db_url, connect_args=_connect_args, pool_pre_ping=True)
# expire_on_commit=False: routes query objects inside `with get_session()`
# and then hand them to a Jinja template *after* the session has closed
# (e.g. admin/routes.py). Without this, SQLAlchemy expires every loaded
# attribute on commit, and touching one after the session is closed raises
# DetachedInstanceError. This keeps already-loaded values usable post-close.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

Base = declarative_base()


def init_db():
    """Create all tables that don't exist yet. Safe to call on every boot."""
    import database.models  # noqa: F401  (ensure models are registered on Base)
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """Usage: `with get_session() as session: ...`"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
