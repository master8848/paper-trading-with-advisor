"""Database engine + session for finance_app MySQL (mirrors backend/src/app.module.ts:11)."""

from __future__ import annotations

import os
import urllib.parse
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel

# Hardcoded config from backend/src/app.module.ts:11-17 — overridable via DATABASE_URL env
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "Finance")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")
DB_NAME = os.environ.get("DB_NAME", "finance_app")

# Password contains '@' -> must be URL-encoded
_DB_PASS_ENCODED = urllib.parse.quote_plus(DB_PASSWORD)

_DEFAULT_MYSQL_URL = (
    f"mysql+pymysql://{DB_USER}:{_DB_PASS_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)

# Allow full override: DATABASE_URL=sqlite:///./finance_app.db for dev without MySQL
# QA found MySQL not running on CI/laptop hangs frontend on Loading... — fallback to SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", _DEFAULT_MYSQL_URL)

# SQLite fallback for dev when MySQL not available (set DATABASE_URL=sqlite:///./finance_app.db)
_is_sqlite = DATABASE_URL.startswith("sqlite")

# pymysql driver; pool_pre_ping handles MySQL idle disconnects; timeout fails fast (was hanging 30s)
_connect_args = {"connect_timeout": 5} if not _is_sqlite else {"check_same_thread": False}

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
