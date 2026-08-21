"""Alembic env — imports SQLModel metadata from app.models."""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

# Ensure project root is on sys.path so `app.*` imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import engine_from_config, pool
from alembic import context
from sqlmodel import SQLModel

# Import all models so they register with SQLModel.metadata
import app.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow DATABASE_URL env to override alembic.ini (swappable sqlite -> postgres/libsql)
import os

if os.environ.get("DATABASE_URL"):
    _url = os.environ["DATABASE_URL"]
    if _url.startswith("libsql://"):
        _url = _url.replace("libsql://", "sqlite+libsql://", 1)
    config.set_main_option("sqlalchemy.url", _url)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
