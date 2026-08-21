"""
Stock-exchange proxy — GET /stock-exchange/Nse (cached) + GET /stock-exchange/:id

Mirrors backend/src/stock-exchange/stock-exchange.controller.ts:18-26
  @UseInterceptors(CacheInterceptor) on GET Nse

Python: simple in-memory TTL cache via app.nse (1h). Also supports per-symbol LTP
for frontend Form.tsx:102  GET /stock-exchange/<SYMBOL>
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.nse import find_last_traded_price, get_all_stock_symbols

router = APIRouter(prefix="/stock-exchange", tags=["stock-exchange"])


@router.get("/Nse", response_model=List[str])
def get_nse_symbols():
    """Cached list of NSE symbols — mirrors StockExchangeController.getStockExchange()."""
    return get_all_stock_symbols()


# Alias lowercase for robustness (frontend uses /Nse exactly, but handle /nse)
@router.get("/nse", response_model=List[str])
def get_nse_symbols_lower():
    return get_all_stock_symbols()


@router.get("/{symbol}", response_model=Dict[str, Any])
def get_last_traded_price(symbol: str):
    """Mirrors StockExchangeController.getLastTradedPriceOfStock(:id)."""
    data = find_last_traded_price(symbol.strip().upper())
    # Return empty dict shape like TS when missing, so frontend select doesn't crash
    return data if data else {}
