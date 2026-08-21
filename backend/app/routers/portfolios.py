"""Portfolio endpoints.

POST /portfolios
GET  /portfolios/{id}/performance?normalized=true
POST /portfolios/{id}/baseline
GET  /portfolios
"""

from __future__ import annotations

from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Portfolio, Position
from app.schemas import PerformancePoint, PortfolioCreate, PortfolioRead

from app.nse import find_last_traded_price

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.post("", response_model=PortfolioRead, status_code=201)
def create_portfolio(payload: PortfolioCreate, session: Session = Depends(get_session)):
    port = Portfolio(**payload.model_dump())
    session.add(port)
    session.commit()
    session.refresh(port)
    return port


@router.get("", response_model=List[PortfolioRead])
def list_portfolios(session: Session = Depends(get_session)):
    return session.query(Portfolio).order_by(Portfolio.id).all()


@router.get("/{portfolio_id}", response_model=PortfolioRead)
def get_portfolio(portfolio_id: int, session: Session = Depends(get_session)):
    port = session.get(Portfolio, portfolio_id)
    if not port:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return port


@router.post("/{portfolio_id}/baseline", response_model=PortfolioRead)
def set_baseline(
    portfolio_id: int,
    baseline_value: Decimal = Query(..., gt=0, description="New baseline value, e.g. 100"),
    baseline_price: Decimal | None = Query(None, gt=0, description="Optional baseline price for positions"),
    session: Session = Depends(get_session),
):
    port = session.get(Portfolio, portfolio_id)
    if not port:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    port.baseline_value = baseline_value
    session.add(port)
    # optionally propagate baseline_price to positions lacking one
    if baseline_price is not None:
        positions = session.query(Position).filter(Position.portfolio_id == portfolio_id).all()
        for p in positions:
            if p.baseline_price is None:
                p.baseline_price = baseline_price
                session.add(p)
    session.commit()
    session.refresh(port)
    return port


@router.get("/{portfolio_id}/performance", response_model=List[PerformancePoint])
def portfolio_performance(
    portfolio_id: int,
    normalized: bool = Query(True, description="If true, pnl_normalized = pnl / baseline_value * 100"),
    session: Session = Depends(get_session),
):
    port = session.get(Portfolio, portfolio_id)
    if not port:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    positions = session.query(Position).filter(Position.portfolio_id == portfolio_id).all()
    points: List[PerformancePoint] = []
    for pos in positions:
        ltp_data = find_last_traded_price(pos.symbol)
        current = ltp_data.get("lastTradedPrice")
        current_dec = Decimal(str(current)) if current is not None else None
        pnl: Decimal | None = None
        pnl_norm: Decimal | None = None
        if current_dec is not None:
            pnl = (current_dec - pos.avg_buy_price) * pos.qty
            if normalized and port.baseline_value and port.baseline_value != 0:
                pnl_norm = (pnl / port.baseline_value) * Decimal("100")
        points.append(
            PerformancePoint(
                symbol=pos.symbol,
                qty=pos.qty,
                avg_buy_price=pos.avg_buy_price,
                current_price=current_dec,
                pnl=pnl,
                pnl_normalized=pnl_norm,
                baseline_price=pos.baseline_price,
            )
        )
    return points
