"""Database engine — SQLite by default (libsql-compatible), swappable to Postgres/MySQL via DATABASE_URL.

Default: sqlite:///./finance_app.db (no creds, no server). Set DATABASE_URL to use Postgres:
  DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/finance_app
  DATABASE_URL=libsql://user:pass@host/db  (Turso)
  DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/finance_app?charset=utf8mb4

Legacy MySQL hardcoded creds removed — was leaking password in git history.
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel

# Default is SQLite (libsql-compatible) — file in repo root, no server required.
# Swappable to Postgres/libsql/MySQL by setting DATABASE_URL env.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./finance_app.db")

# Also support legacy DB_* envs for MySQL compat (no hardcoded password)
if DATABASE_URL == "sqlite:///./finance_app.db" and os.environ.get("DB_PASSWORD"):
    import urllib.parse

    _host = os.environ.get("DB_HOST", "localhost")
    _port = os.environ.get("DB_PORT", "3306")
    _user = os.environ.get("DB_USER", "Finance")
    _pass = urllib.parse.quote_plus(os.environ["DB_PASSWORD"])
    _name = os.environ.get("DB_NAME", "finance_app")
    _type = os.environ.get("DB_TYPE", "mysql")
    if _type == "mysql":
        DATABASE_URL = f"mysql+pymysql://{_user}:{_pass}@{_host}:{_port}/{_name}?charset=utf8mb4"
    elif _type == "postgres":
        DATABASE_URL = f"postgresql+psycopg://{_user}:{_pass}@{_host}:{_port}/{_name}"

_is_sqlite = DATABASE_URL.startswith("sqlite") or DATABASE_URL.startswith("libsql")

_connect_args = {"check_same_thread": False} if _is_sqlite else {"connect_timeout": 5}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=not _is_sqlite,
    pool_recycle=3600 if not _is_sqlite else -1,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_db_and_tables() -> None:
    """Create all SQLModel tables (dev convenience; production uses Alembic)."""
    SQLModel.metadata.create_all(engine)
