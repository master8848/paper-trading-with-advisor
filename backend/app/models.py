"""SQLModel table definitions.

Covers new portfolio domain plus legacy Stocks compatibility.
Mirrors backend/src/stocks/entities/FinanceData.ts:8 for migration path:
  username -> user_id, stockName -> symbol, price -> avg_buy_price, etc.
"""

from __future__ import annotations

from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Column, Enum, String
from sqlmodel import Field, SQLModel

from app.enums import TransactionType


# ---------------------------------------------------------------------------
# Legacy table — existing `Stocks` entity (backend/src/stocks/entities/FinanceData.ts:8)
# Kept verbatim so Alembic migration can copy data without dropping the table.
# ---------------------------------------------------------------------------
class StocksLegacy(SQLModel, table=True):
    __tablename__ = "Stocks"  # TypeORM default: @Entity({ name: 'Stocks' })

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(255)))
    message: Optional[str] = Field(default=None, sa_column=Column(String(1024), nullable=True))
    price: str = Field(sa_column=Column(String(64)))
    stockName: str = Field(sa_column=Column(String(64)))
    date: datetime = Field(sa_column=Column(String(64)))  # stored as DATETIME in MySQL
    modified: datetime
    transactionType: str = Field(
        default=TransactionType.buy.value,
        sa_column=Column(Enum(TransactionType), nullable=False),
    )
    quantity: str = Field(sa_column=Column(String(64)))
    total: str = Field(sa_column=Column(String(64)))


# ---------------------------------------------------------------------------
# New domain — portfolios / positions / trades / price_snapshots
# ---------------------------------------------------------------------------
class Portfolio(SQLModel, table=True):
    __tablename__ = "portfolios"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True, max_length=255, description="migrated from Stocks.username")
    name: str = Field(max_length=255)
    baseline_value: Decimal = Field(default=Decimal("100"), max_digits=20, decimal_places=4)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Position(SQLModel, table=True):
    __tablename__ = "positions"

    id: Optional[int] = Field(default=None, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolios.id", index=True)
    symbol: str = Field(index=True, max_length=64, description="migrated from Stocks.stockName")
    qty: Decimal = Field(max_digits=20, decimal_places=4, description="migrated from Stocks.quantity")
    avg_buy_price: Decimal = Field(max_digits=20, decimal_places=4, description="migrated from Stocks.price")
    baseline_price: Optional[Decimal] = Field(default=None, max_digits=20, decimal_places=4)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Trade(SQLModel, table=True):
    __tablename__ = "trades"

    id: Optional[int] = Field(default=None, primary_key=True)
    position_id: Optional[int] = Field(default=None, foreign_key="positions.id", index=True)
    symbol: str = Field(index=True, max_length=64)
    price_snapshot: Decimal = Field(max_digits=20, decimal_places=4, description="price at trade time")
    qty: Decimal = Field(max_digits=20, decimal_places=4)
    type: TransactionType = Field(sa_column=Column(Enum(TransactionType), nullable=False))
    traded_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    # snapshot fields populated by paper-trade flow (via NSE LTP)
    ltp: Optional[Decimal] = Field(default=None, max_digits=20, decimal_places=4)
    fiftyTwoWeekLow: Optional[Decimal] = Field(default=None, max_digits=20, decimal_places=4)
    fiftyTwoWeekHigh: Optional[Decimal] = Field(default=None, max_digits=20, decimal_places=4)


class PriceSnapshot(SQLModel, table=True):
    __tablename__ = "price_snapshots"
    __table_args__ = {"comment": "Daily OHLCV snapshots per symbol"}

    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, max_length=64)
    date: date_type = Field(index=True)
    open: Decimal = Field(max_digits=20, decimal_places=4)
    high: Decimal = Field(max_digits=20, decimal_places=4)
    low: Decimal = Field(max_digits=20, decimal_places=4)
    close: Decimal = Field(max_digits=20, decimal_places=4)
    volume: int = Field(sa_column=Column(BigInteger, nullable=False))
    delivery_volume: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    market_cap: Optional[Decimal] = Field(default=None, max_digits=20, decimal_places=4)

    class Config:
        # composite uniqueness enforced via Alembic unique constraint
        pass
