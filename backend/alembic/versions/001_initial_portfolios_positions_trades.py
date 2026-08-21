"""initial: portfolios, positions, trades, price_snapshots

Revision ID: 001_initial
Revises:
Create Date: 2026-08-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # portfolios
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=255), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("baseline_value", sa.Numeric(precision=20, scale=4), nullable=False, server_default="100.0000"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    # positions
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("symbol", sa.String(length=64), nullable=False, index=True),
        sa.Column("qty", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("avg_buy_price", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("baseline_price", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    # trades
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("symbol", sa.String(length=64), nullable=False, index=True),
        sa.Column("price_snapshot", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("qty", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("type", sa.Enum("buy", "sell", name="transactiontype"), nullable=False),
        sa.Column("traded_at", sa.DateTime(), nullable=False),
        sa.Column("ltp", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("fiftyTwoWeekLow", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("fiftyTwoWeekHigh", sa.Numeric(precision=20, scale=4), nullable=True),
    )
    # price_snapshots
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=64), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("open", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("delivery_volume", sa.BigInteger(), nullable=True),
        sa.Column("market_cap", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.UniqueConstraint("symbol", "date", name="uq_price_snapshots_symbol_date"),
    )
    # Note: legacy `Stocks` table is NOT created here — it already exists via NestJS TypeORM migrationsRun:true


def downgrade() -> None:
    op.drop_table("price_snapshots")
    op.drop_table("trades")
    op.drop_table("positions")
    op.drop_table("portfolios")
    # do not drop Stocks
    try:
        sa.Enum(name="transactiontype").drop(op.get_bind(), checkfirst=True)
    except Exception:
        pass
