"""
FastAPI router for /quant/*

Endpoints per spec:
  POST /quant/predict        {symbol, horizon:5d} -> {score, expected_return, confidence}
  POST /quant/backtest       {symbol, start, end}
  GET  /quant/screen/{symbol}   -> liquidity check
  GET  /quant/warnings/{symbol} -> mcap<500Cr, avgVol<1L, impact>2% flags
  POST /quant/execution/simulate -> execution realism

All endpoints handle qlib missing gracefully (fallback mode).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .execution import ExecutionSimulator
from .qlib_service import get_qlib_service
from .screener import get_screener

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quant", tags=["quant"])


# -- schemas --


class PredictRequest(BaseModel):
    symbol: str = Field(..., description="NSE symbol, e.g. RELIANCE or RELIANCE.NS", examples=["RELIANCE"])
    horizon: str = Field(default="5d", description="Prediction horizon, e.g. 5d, 10d, 1d", examples=["5d"])


class PredictResponse(BaseModel):
    symbol: str
    horizon: str
    horizon_days: int
    score: float
    expected_return: float
    confidence: float
    gated: bool
    model_used: str
    gate_reason: Optional[str] = None
    warning: Optional[str] = None
    message: Optional[str] = None
    warnings: Optional[list] = None


class BacktestRequest(BaseModel):
    symbol: str = Field(..., examples=["RELIANCE"])
    start: str = Field(..., description="YYYY-MM-DD", examples=["2024-01-01"])
    end: str = Field(..., description="YYYY-MM-DD", examples=["2024-06-01"])


class ExecutionRequest(BaseModel):
    symbol: str = Field(..., examples=["RELIANCE"])
    qty: int = Field(default=1000, ge=1, description="Requested quantity")
    ideal_price: Optional[float] = Field(default=None, description="Ideal price; if null uses last close")
    side: str = Field(default="buy", description="buy or sell")


class BacktestResponse(BaseModel):
    symbol: str
    start: str
    end: str
    cumulative_return: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    trades: Optional[int] = None
    message: Optional[str] = None
    gated: Optional[bool] = None
    warning: Optional[str] = None


class ScreenResponse(BaseModel):
    symbol: str
    liquid: bool
    mcap: Optional[float] = None
    avg_volume: Optional[float] = None
    warnings: Optional[list] = None
    reason: Optional[str] = None


class WarningsResponse(BaseModel):
    symbol: str
    illiquid: bool
    warnings: Optional[list] = None
    flags: Optional[Dict[str, Any]] = None


class ExecutionResponse(BaseModel):
    symbol: str
    qty: int
    feasible_qty: Optional[int] = None
    ideal_price: Optional[float] = None
    realistic_price: Optional[float] = None
    slippage: Optional[float] = None
    market_impact: Optional[float] = None
    warning: Optional[str] = None
    illiquid: Optional[bool] = None


class QuantHealthResponse(BaseModel):
    status: str
    qlib_available: bool
    provider_uri: str
    initialized: bool


# -- endpoints --


@router.post("/predict", response_model=PredictResponse, summary="Qlib prediction")
def predict(req: PredictRequest):
    """
    POST /quant/predict {symbol, horizon}
    Returns score in [-1,1], expected_return, confidence in [0,1].
    Heavy inference is gated behind liquidity check (mcap/volume).
    """
    if not req.symbol or not req.symbol.strip():
        raise HTTPException(status_code=422, detail="symbol is required")
    try:
        svc = get_qlib_service()
        result = svc.predict(symbol=req.symbol.strip(), horizon=req.horizon)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("predict failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/backtest", response_model=Dict[str, Any], summary="Qlib backtest")
def backtest(req: BacktestRequest):
    """
    POST /quant/backtest {symbol, start, end}
    Returns cumulative_return, sharpe, max_drawdown, trades, etc.
    """
    if not req.symbol or not req.symbol.strip():
        raise HTTPException(status_code=422, detail="symbol is required")
    try:
        svc = get_qlib_service()
        result = svc.backtest(symbol=req.symbol.strip(), start=req.start, end=req.end)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("backtest failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/screen/{symbol}", response_model=Dict[str, Any], summary="Liquidity screen (gate for inference)")
def screen(symbol: str):
    """
    GET /quant/screen/{symbol} -> liquidity check.
    Only run heavy inference if this passes (mcap >=500Cr, vol >=1L).
    """
    if not symbol or not symbol.strip():
        raise HTTPException(status_code=422, detail="symbol is required")
    try:
        screener = get_screener()
        return screener.liquidity_check(symbol.strip())
    except Exception as exc:
        logger.exception("screen failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/warnings/{symbol}", response_model=Dict[str, Any], summary="Screener warnings: mcap, volume, impact")
def warnings(
    symbol: str,
    qty: int = Query(default=1000, ge=1, description="Quantity to estimate impact for"),
    ideal_price: Optional[float] = Query(default=None, description="Ideal price for impact calc"),
):
    """
    GET /quant/warnings/{symbol}?qty=1000
    Checks:
      - mcap < 500Cr
      - avgVol 20D < 1L (100k)
      - impactCost > 2%
    Returns flags, warnings, illiquid flag.
    """
    if not symbol or not symbol.strip():
        raise HTTPException(status_code=422, detail="symbol is required")
    try:
        screener = get_screener()
        return screener.check_warnings(symbol.strip(), qty=qty, ideal_price=ideal_price)
    except Exception as exc:
        logger.exception("warnings failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/execution/simulate", response_model=Dict[str, Any], summary="Realistic execution simulation")
def execution_simulate(req: ExecutionRequest):
    """
    POST /quant/execution/simulate {symbol, qty, ideal_price}

    Simulates what you could actually buy/sell:
      feasible_qty = min(qty, avgVolume*0.1)
      slippage = 0.1% + 0.5%*(qty/avgVolume)
      market_impact via sqrt model
    Returns ideal vs realistic prices, feasible_qty, warning, illiquid_flag.
    """
    if not req.symbol or not req.symbol.strip():
        raise HTTPException(status_code=422, detail="symbol is required")
    try:
        sim = ExecutionSimulator()
        result = sim.simulate(symbol=req.symbol.strip(), qty=req.qty, ideal_price=req.ideal_price, side=req.side)
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("execution simulate failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/health", response_model=Dict[str, Any], summary="Quant module health")
def health():
    svc = get_qlib_service()
    qlib_available = svc._check_qlib_available()
    return {
        "status": "ok",
        "qlib_available": qlib_available,
        "provider_uri": str(svc.provider_uri),
        "initialized": svc._initialized,
    }
