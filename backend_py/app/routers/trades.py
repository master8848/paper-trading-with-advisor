"""Trade endpoints — paper trade with LTP snapshot.

POST /trades
  Body: { symbol, qty, type: buy|sell, position_id?, price_snapshot? }
  If price_snapshot omitted, server fetches current LTP via NSE logic
  (port of stock-nse-india to yfinance/nsepython, see app/nse.py).

Also persists to PriceSnapshot-like enrichment: ltp / 52W low/high.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Position, Trade
from app.nse import find_last_traded_price
from app.schemas import TradeCreate, TradeRead

router = APIRouter(prefix="/trades", tags=["trades"])


@router.post("", response_model=TradeRead, status_code=201)
def create_trade(payload: TradeCreate, session: Session = Depends(get_session)):
    symbol = payload.symbol.strip().upper()

    # snapshot current LTP if caller didn't provide price_snapshot
    price_snapshot = payload.price_snapshot
    ltp_data = find_last_traded_price(symbol)
    ltp_val = ltp_data.get("lastTradedPrice")
    fifty_low = ltp_data.get("fiftyTwoWeekLow")
    fifty_high = ltp_data.get("fiftyTwoWeekHigh")

    if price_snapshot is None:
        if ltp_val is not None:
            price_snapshot = Decimal(str(ltp_val))
        else:
            raise HTTPException(
                status_code=502,
                detail=f"Could not snapshot LTP for symbol {symbol}; provide price_snapshot explicitly",
            )

    # validate position if provided
    if payload.position_id is not None:
        pos = session.get(Position, payload.position_id)
        if not pos:
            raise HTTPException(status_code=404, detail="Position not found")
        # optionally enforce symbol match
        if pos.symbol.upper() != symbol:
            raise HTTPException(status_code=400, detail="Trade symbol must match position symbol")

    trade = Trade(
        position_id=payload.position_id,
        symbol=symbol,
        price_snapshot=price_snapshot,
        qty=payload.qty,
        type=payload.type,
        ltp=Decimal(str(ltp_val)) if ltp_val is not None else None,
        fiftyTwoWeekLow=Decimal(str(fifty_low)) if fifty_low is not None else None,
        fiftyTwoWeekHigh=Decimal(str(fifty_high)) if fifty_high is not None else None,
    )
    session.add(trade)
    session.commit()
    session.refresh(trade)
    return trade


@router.get("", response_model=List[TradeRead])
def list_trades(
    position_id: int | None = None,
    symbol: str | None = None,
    session: Session = Depends(get_session),
):
    q = session.query(Trade)
    if position_id is not None:
        q = q.filter(Trade.position_id == position_id)
    if symbol is not None:
        q = q.filter(Trade.symbol == symbol.strip().upper())
    return q.order_by(Trade.traded_at.desc()).all()


@router.get("/{trade_id}", response_model=TradeRead)
def get_trade(trade_id: int, session: Session = Depends(get_session)):
    t = session.get(Trade, trade_id)
    if not t:
        raise HTTPException(status_code=404, detail="Trade not found")
    return t
