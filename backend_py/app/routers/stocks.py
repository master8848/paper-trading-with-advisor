"""
Stocks compatibility — keeps GET /stocks?duration=... working for frontend Home.tsx:19

Ports:
  - backend/src/stocks/stocks.service.ts:29  (duration filter via moment.startOf)
  - backend/src/stocks/stocks.service.ts:99  (?load=true enrichment with LTP/52W)
  - CRUD: POST /stocks, PATCH /stocks/:id, DELETE /stocks/:id
  - Also exposes GET /price-snapshots for new domain

Implementation uses the legacy `Stocks` table (StocksLegacy) so existing data and
frontend keep working unchanged.  Also writes through to new Portfolio/Position
domain on create for forward compatibility (best-effort, no failure propagation).

GET /stocks?duration=tweek|lweek|tmonth|lmonth|tyear|lyear&load=true
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Portfolio, Position, StocksLegacy
from app.nse import find_equity_historical_data
from app.schemas import StockCreate, StockUpdate
from app.utils.duration import duration_bounds

router = APIRouter(prefix="/stocks", tags=["stocks"])


def _row_to_dict(row: StocksLegacy) -> Dict[str, Any]:
    return {
        "id": row.id,
        "username": row.username,
        "message": row.message,
        "price": row.price,
        "stockName": row.stockName,
        "date": row.date.isoformat() if isinstance(row.date, datetime) else row.date,
        "modified": row.modified.isoformat() if isinstance(row.modified, datetime) else row.modified,
        "transactionType": row.transactionType,
        # frontend Table.tsx also reads `type` alias
        "type": row.transactionType,
        "quantity": row.quantity,
        "total": row.total,
    }


@router.get("", response_model=List[Dict[str, Any]])
def list_stocks(
    duration: Optional[str] = Query(None, description="tweek|lweek|tmonth|lmonth|tyear|lyear"),
    load: Optional[str] = Query(None, description="if 'true', enrich each row with LTP/52W"),
    session: Session = Depends(get_session),
):
    # duration filter port — backend/src/stocks/stocks.service.ts:32-95
    start, end = duration_bounds(duration)
    q = session.query(StocksLegacy)
    if start and end:
        q = q.filter(StocksLegacy.modified.between(start, end))  # lweek/lmonth/lyear
    elif start:
        q = q.filter(StocksLegacy.modified > start)  # tweek/tmonth/tyear
    try:
        rows = q.order_by(StocksLegacy.id.desc()).all()
    except Exception:
        # table not created yet (sqlite fresh) -> return empty like 500->[]
        return []
    data = [_row_to_dict(r) for r in rows]

    # enrichment — backend/src/stocks/stocks.service.ts:99-120
    # If ?load=true, fetch NSE snapshot per row (N parallel, swallow errors)
    should_load = str(load).lower() == "true" if load is not None else False
    if should_load and data:
        for element in data:
            try:
                all_price = find_equity_historical_data(element["stockName"])
                # all_price[0].data[0].CH_LAST_TRADED_PRICE etc
                if all_price and all_price[0].get("data"):
                    row0 = all_price[0]["data"][0]
                    element["lastTradedPrice"] = row0.get("CH_LAST_TRADED_PRICE")
                    element["fiftyTwoWeekLow"] = row0.get("CH_52WEEK_LOW_PRICE")
                    element["fiftyTwoWeekHigh"] = row0.get("CH_52WEEK_HIGH_PRICE")
            except Exception:
                # swallow, return original row as TS does
                pass
    return data


@router.post("", response_model=Dict[str, Any], status_code=201, summary="Create stock (legacy compat)")
def create_stock(payload: StockCreate, session: Session = Depends(get_session)):
    now = datetime.now()
    total = str(float(payload.price) * float(payload.quantity))
    row = StocksLegacy(
        username=payload.username,
        message=payload.message,
        price=payload.price,
        stockName=payload.stockName.strip().upper(),
        date=now,
        modified=now,
        transactionType=payload.type.value,
        quantity=payload.quantity,
        total=total,
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    # best-effort mirror to new domain: ensure a portfolio exists for this user, then add position
    try:
        portfolio = (
            session.query(Portfolio).filter(Portfolio.user_id == payload.username).first()
        )
        if not portfolio:
            portfolio = Portfolio(user_id=payload.username, name="Default")
            session.add(portfolio)
            session.commit()
            session.refresh(portfolio)
        # create or update position for symbol
        pos = (
            session.query(Position)
            .filter(Position.portfolio_id == portfolio.id, Position.symbol == row.stockName)
            .first()
        )
        qty_f = float(payload.quantity)
        price_f = float(payload.price)
        if pos and payload.type.value == "buy":
            # weighted avg buy price
            total_qty = float(pos.qty) + qty_f
            if total_qty:
                new_avg = (float(pos.avg_buy_price) * float(pos.qty) + price_f * qty_f) / total_qty
                pos.qty = total_qty  # type: ignore
                pos.avg_buy_price = new_avg  # type: ignore
                session.add(pos)
                session.commit()
        elif not pos:
            pos = Position(
                portfolio_id=portfolio.id,
                symbol=row.stockName,
                qty=qty_f,  # type: ignore
                avg_buy_price=price_f,  # type: ignore
            )
            session.add(pos)
            session.commit()
    except Exception:
        pass  # do not fail legacy write if new domain fails

    return _row_to_dict(row)


@router.patch("/{stock_id}", response_model=Dict[str, Any], summary="Update stock")
def update_stock(stock_id: int, payload: StockUpdate, session: Session = Depends(get_session)):
    row: Optional[StocksLegacy] = session.get(StocksLegacy, stock_id)
    if not row:
        raise HTTPException(status_code=404, detail="Stock not found")

    update_data = payload.model_dump(exclude_unset=True)
    # map `type` alias to transactionType
    if "type" in update_data and update_data["type"] is not None:
        row.transactionType = update_data["type"].value if hasattr(update_data["type"], "value") else update_data["type"]
    if "price" in update_data and update_data["price"] is not None:
        row.price = update_data["price"]
    if "quantity" in update_data and update_data["quantity"] is not None:
        row.quantity = update_data["quantity"]
    if "message" in update_data:
        row.message = update_data["message"]
    if "stockName" in update_data and update_data["stockName"]:
        row.stockName = update_data["stockName"].strip().upper()
    # recompute total and modified — mirrors StocksService.update:33
    try:
        row.total = str(float(row.price) * float(row.quantity))
    except Exception:
        pass
    row.modified = datetime.now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row_to_dict(row)


@router.delete("/{stock_id}", response_model=Dict[str, Any], summary="Delete stock")
def delete_stock(stock_id: int, session: Session = Depends(get_session)):
    row = session.get(StocksLegacy, stock_id)
    if not row:
        raise HTTPException(status_code=404, detail="Stock not found")
    session.delete(row)
    session.commit()
    return {"deleted": stock_id}
