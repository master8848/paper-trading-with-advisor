"""Pydantic v2 request/response schemas (Validation via pydantic)."""

from __future__ import annotations

from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.enums import TransactionType


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------
class PortfolioCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    baseline_value: Decimal = Field(default=Decimal("100"), gt=0)


class PortfolioRead(BaseModel):
    id: int
    user_id: str
    name: str
    baseline_value: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------
class PositionCreate(BaseModel):
    portfolio_id: int
    symbol: str = Field(..., min_length=1, max_length=64)
    qty: Decimal = Field(..., gt=0)
    avg_buy_price: Decimal = Field(..., gt=0)
    baseline_price: Optional[Decimal] = Field(default=None, gt=0)


class PositionRead(BaseModel):
    id: int
    portfolio_id: int
    symbol: str
    qty: Decimal
    avg_buy_price: Decimal
    baseline_price: Optional[Decimal]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Trade (paper trade)
# ---------------------------------------------------------------------------
class TradeCreate(BaseModel):
    position_id: Optional[int] = None
    symbol: str = Field(..., min_length=1, max_length=64)
    qty: Decimal = Field(..., gt=0)
    type: TransactionType
    # if omitted, server snapshots current LTP via NSE logic
    price_snapshot: Optional[Decimal] = Field(default=None, gt=0)


class TradeRead(BaseModel):
    id: int
    position_id: Optional[int]
    symbol: str
    price_snapshot: Decimal
    qty: Decimal
    type: TransactionType
    traded_at: datetime
    ltp: Optional[Decimal]
    fiftyTwoWeekLow: Optional[Decimal]
    fiftyTwoWeekHigh: Optional[Decimal]

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# PriceSnapshot
# ---------------------------------------------------------------------------
class PriceSnapshotCreate(BaseModel):
    symbol: str
    date: date_type
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    delivery_volume: Optional[int] = None
    market_cap: Optional[Decimal] = None


class PriceSnapshotRead(BaseModel):
    id: int
    symbol: str
    date: date_type
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    delivery_volume: Optional[int]
    market_cap: Optional[Decimal]

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Legacy Stocks compatibility (frontend Home.tsx / Form.tsx still POST /stocks)
# ---------------------------------------------------------------------------
class StockCreate(BaseModel):
    username: str = Field(..., min_length=1)
    stockName: str = Field(..., min_length=1)
    price: str = Field(..., min_length=1)
    quantity: str = Field(..., min_length=1)
    type: TransactionType = Field(..., description="buy | sell")
    message: Optional[str] = None


class StockUpdate(BaseModel):
    price: Optional[str] = None
    quantity: Optional[str] = None
    type: Optional[TransactionType] = None
    message: Optional[str] = None
    stockName: Optional[str] = None


class PerformancePoint(BaseModel):
    symbol: str
    qty: Decimal
    avg_buy_price: Decimal
    current_price: Optional[Decimal]
    pnl: Optional[Decimal]
    pnl_normalized: Optional[Decimal]  # vs baseline_value=100
    baseline_price: Optional[Decimal]
