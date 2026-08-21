"""Database engine + session for finance_app MySQL (mirrors backend/src/app.module.ts:11)."""

from __future__ import annotations

import urllib.parse
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel

# Hardcoded config from backend/src/app.module.ts:11-17
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "Finance"
DB_PASSWORD = "***REDACTED***"
DB_NAME = "finance_app"

# Password contains '@' -> must be URL-encoded
_DB_PASS_ENCODED = urllib.parse.quote_plus(DB_PASSWORD)

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{_DB_PASS_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)

# pymysql driver; pool_pre_ping handles MySQL idle disconnects
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
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
