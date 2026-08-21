"""Position endpoints: POST /positions"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Portfolio, Position
from app.schemas import PositionCreate, PositionRead

router = APIRouter(prefix="/positions", tags=["positions"])


@router.post("", response_model=PositionRead, status_code=201)
def create_position(payload: PositionCreate, session: Session = Depends(get_session)):
    port = session.get(Portfolio, payload.portfolio_id)
    if not port:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    # normalize symbol
    payload.symbol = payload.symbol.strip().upper()
    pos = Position(**payload.model_dump())
    session.add(pos)
    session.commit()
    session.refresh(pos)
    return pos


@router.get("", response_model=List[PositionRead])
def list_positions(
    portfolio_id: int | None = None, session: Session = Depends(get_session)
):
    q = session.query(Position)
    if portfolio_id is not None:
        q = q.filter(Position.portfolio_id == portfolio_id)
    return q.order_by(Position.id).all()


@router.get("/{position_id}", response_model=PositionRead)
def get_position(position_id: int, session: Session = Depends(get_session)):
    pos = session.get(Position, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    return pos
