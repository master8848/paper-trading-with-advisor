"""Database engine — SQLite/libSQL by default, swappable to Postgres/MySQL via DATABASE_URL.

Default: sqlite:///./finance_app.db — file is libSQL-compatible (Turso's SQLite fork).
  Works with pysqlite locally; same file can be replicated to Turso/sqld.

Swappable:
  DATABASE_URL=sqlite:///./finance_app.db                          # local file (default, libsql-compatible)
  DATABASE_URL=sqlite+libsql://user:token@host:8080/db?secure=true # Turso / self-hosted sqld (via sqlalchemy-libsql)
  DATABASE_URL=libsql://user:token@host:8080/db?secure=true        # alias, auto-normalized to sqlite+libsql://
  DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/finance_app
  DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/finance_app?charset=utf8mb4

Self-host libSQL (Turso) later:
  docker run -p 8080:8080 ghcr.io/tursodatabase/libsql-server:latest sqld --http-listen-addr 0.0.0.0:8080 /data/libsql.db
  # or: docker compose -f docker-compose.libsql.yml up

Legacy MySQL hardcoded creds removed — was leaking password in git history.
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel

# Default is SQLite file — libSQL-compatible, no server required.
_raw_url = os.environ.get("DATABASE_URL", "sqlite:///./finance_app.db")

# Normalize libsql:// → sqlite+libsql:// for SQLAlchemy dialect (sqlalchemy-libsql)
if _raw_url.startswith("libsql://"):
    DATABASE_URL = _raw_url.replace("libsql://", "sqlite+libsql://", 1)
else:
    DATABASE_URL = _raw_url

# Also support legacy DB_* envs (no hardcoded password) for MySQL compat
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

_is_sqlite = DATABASE_URL.startswith("sqlite")  # covers sqlite:// and sqlite+libsql://
_is_libsql = "libsql" in DATABASE_URL

# libsql remote needs no check_same_thread; local sqlite needs it False; mysql/postgres need timeout
if _is_libsql:
    _connect_args: dict = {}
elif _is_sqlite:
    _connect_args = {"check_same_thread": False}
else:
    _connect_args = {"connect_timeout": 5}

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
