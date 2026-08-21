"""
NSE helper — Python port of backend/src/stock-exchange/stock-exchange.service.ts

Original TS:
  findStock() -> nseIndia().getAllStockSymbols()
  findEquityHistoricalData(sym) -> nseIndia().getEquityHistoricalData(sym, {start: moment()-4d, end: now})
  findLastTradedPrice(sym) -> {lastTradedPrice, fiftyTwoWeekLow, fiftyTwoWeekHigh}

Python port:
  - Primary: yfinance (reliable, no NSE cookie handshake)
  - Fallback: nsepython (if installed)
  - Reuses backend_py/app/quant/data_collector.py when available
  - TTL cache for stock list (mirrors NestJS CacheInterceptor on GET /stock-exchange/Nse)

Reference kept: backend/src/stock-exchange/stock-exchange.service.ts:15
and backend/src/stocks/stocks.service.ts:99-120 for enrichment.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to reuse existing collector; fall back to inline yfinance logic
try:
    from app.quant.data_collector import default_collector  # type: ignore

    _HAS_COLLECTOR = True
except Exception:
    default_collector = None  # type: ignore
    _HAS_COLLECTOR = False


# ---------------------------------------------------------------------------
# Simple TTL cache — no extra deps, avoids adding cachetools unless present
# ---------------------------------------------------------------------------
_cache: Dict[str, Any] = {}
_cache_ts: Dict[str, float] = {}
TTL_SECONDS = 60 * 60  # 1h for symbol list


def _cache_get(key: str) -> Optional[Any]:
    ts = _cache_ts.get(key)
    if ts is None:
        return None
    if time.time() - ts > TTL_SECONDS:
        _cache.pop(key, None)
        _cache_ts.pop(key, None)
        return None
    return _cache.get(key)


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = value
    _cache_ts[key] = time.time()


# ---------------------------------------------------------------------------
# Public API matching TS service
# ---------------------------------------------------------------------------

def get_all_stock_symbols() -> List[str]:
    """Port of StockExchangeService.findStock() -> getAllStockSymbols()."""
    cached = _cache_get("all_symbols")
    if cached is not None:
        return cached

    # try collector's underlying list? collector doesn't expose symbol list,
    # so fetch via yfinance/nsepython or return NSE top list
    symbols: List[str] = []

    # Attempt yfinance via known NSE list scraping — fallback to static Nifty 50
    # plus fetch via nsepython if available
    try:
        from nsepython import nse_eq_symbols  # type: ignore
        # nsepython may not have this, try alternative
        symbols = nse_eq_symbols()  # type: ignore
    except Exception:
        pass

    if not symbols:
        try:
            import httpx

            # NSE publishes symbol list; try hitting nseIndia endpoint via httpx
            # If network unavailable, fall back to static list
            resp = httpx.get(
                "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
                timeout=5,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                lines = resp.text.splitlines()
                # CSV header: SYMBOL,NAME OF COMPANY,...
                for line in lines[1:]:
                    parts = line.split(",")
                    if parts and parts[0].strip():
                        symbols.append(parts[0].strip().upper())
                symbols = symbols[:500]  # cap
        except Exception as exc:
            logger.debug("get_all_stock_symbols httpx fallback failed: %s", exc)

    if not symbols:
        # Static Nifty 50 + Next 50 as reasonable offline fallback (keeps frontend working)
        symbols = [
            "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL",
            "ITC", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "BAJFINANCE",
            "HCLTECH", "WIPRO", "SUNPHARMA", "ULTRACEMCO", "TITAN", "NESTLEIND",
            "POWERGRID", "NTPC", "ONGC", "COALINDIA", "TATASTEEL", "JSWSTEEL",
            "HINDALCO", "ADANIENT", "ADANIPORTS", "GRASIM", "CIPLA", "DRREDDY",
            "DIVISLAB", "EICHERMOT", "BAJAJFINSV", "BAJAJ-AUTO", "HEROMOTOCO",
            "M&M", "TECHM", "INDUSINDBK", "BRITANNIA", "SHREECEM", "UPL", "HINDUNILVR",
            "APOLLOHOSP", "LTIM", "SBILIFE", "HDFCLIFE", "BPCL",
        ]

    _cache_set("all_symbols", symbols)
    return symbols


def find_equity_historical_data(symbol: str) -> List[Dict[str, Any]]:
    """
    Port of StockExchangeService.findEquityHistoricalData.
    Returns list shaped like stock-nse-india: [ { data: [ {CH_LAST_TRADED_PRICE,..} ] } ]
    so callers in stocks.service.ts:106 can read .[0].data[0].CH_LAST_TRADED_PRICE
    """
    if not symbol:
        return []

    if _HAS_COLLECTOR and default_collector is not None:
        try:
            df = default_collector.find_equity_historical_data(symbol)
            if not df.empty:
                last = df.iloc[-1]
                df_year = default_collector.find_equity_historical_data(
                    symbol,
                    start=dt.date.today() - dt.timedelta(days=365),
                    end=dt.date.today(),
                )
                low52 = float(df_year["low"].min()) if not df_year.empty else None
                high52 = float(df_year["high"].max()) if not df_year.empty else None
                # shape to match TS expectation
                return [
                    {
                        "data": [
                            {
                                "CH_LAST_TRADED_PRICE": float(last["close"]),
                                "CH_52WEEK_LOW_PRICE": low52,
                                "CH_52WEEK_HIGH_PRICE": high52,
                                "CH_OPENING_PRICE": float(last["open"]),
                                "CH_TRADE_HIGH_PRICE": float(last["high"]),
                                "CH_TRADE_LOW_PRICE": float(last["low"]),
                                "CH_CLOSING_PRICE": float(last["close"]),
                                "CH_TOT_TRADED_QTY": int(last["volume"]),
                            }
                        ]
                    }
                ]
        except Exception as exc:
            logger.debug("collector path failed for %s: %s", symbol, exc)

    # Fallback inline yfinance (no collector)
    try:
        import yfinance as yf  # type: ignore

        sym = symbol.strip().upper()
        yahoo_sym = sym if sym.endswith(".NS") else f"{sym}.NS"
        ticker = yf.Ticker(yahoo_sym)
        hist = ticker.history(period="5d")
        if hist is None or hist.empty:
            return []
        last = hist.iloc[-1]
        hist_1y = ticker.history(period="1y")
        low52 = float(hist_1y["Low"].min()) if hist_1y is not None and not hist_1y.empty else None
        high52 = float(hist_1y["High"].max()) if hist_1y is not None and not hist_1y.empty else None
        return [
            {
                "data": [
                    {
                        "CH_LAST_TRADED_PRICE": float(last["Close"]),
                        "CH_52WEEK_LOW_PRICE": low52,
                        "CH_52WEEK_HIGH_PRICE": high52,
                        "CH_OPENING_PRICE": float(last["Open"]),
                        "CH_TRADE_HIGH_PRICE": float(last["High"]),
                        "CH_TRADE_LOW_PRICE": float(last["Low"]),
                        "CH_CLOSING_PRICE": float(last["Close"]),
                        "CH_TOT_TRADED_QTY": int(last["Volume"]),
                    }
                ]
            }
        ]
    except Exception as exc:
        logger.debug("yfinance fallback failed for %s: %s", symbol, exc)

    # Also try yahooquery if yfinance missing
    try:
        from yahooquery import Ticker  # type: ignore

        sym = symbol.strip().upper()
        yahoo_sym = sym if sym.endswith(".NS") else f"{sym}.NS"
        t = Ticker(yahoo_sym, asynchronous=False)
        end = dt.date.today()
        start = end - dt.timedelta(days=5)
        hist = t.history(start=start.isoformat(), end=(end + dt.timedelta(days=1)).isoformat())
        if hist is None or hist.empty:
            return []
        # handle MultiIndex
        import pandas as pd  # type: ignore

        if isinstance(hist.index, pd.MultiIndex):
            try:
                hist = hist.xs(yahoo_sym, level=0)
            except Exception:
                hist = hist.droplevel(0)
        hist = hist.rename(columns={c: c.lower() for c in hist.columns})
        last = hist.iloc[-1]
        return [
            {
                "data": [
                    {
                        "CH_LAST_TRADED_PRICE": float(last["close"]),
                        "CH_52WEEK_LOW_PRICE": None,
                        "CH_52WEEK_HIGH_PRICE": None,
                        "CH_OPENING_PRICE": float(last.get("open", last["close"])),
                        "CH_TRADE_HIGH_PRICE": float(last.get("high", last["close"])),
                        "CH_TRADE_LOW_PRICE": float(last.get("low", last["close"])),
                        "CH_CLOSING_PRICE": float(last["close"]),
                        "CH_TOT_TRADED_QTY": int(last.get("volume", 0)),
                    }
                ]
            }
        ]
    except Exception as exc:
        logger.debug("yahooquery fallback failed for %s: %s", symbol, exc)

    return []


def find_last_traded_price(symbol: str) -> Dict[str, Any]:
    """Port of StockExchangeService.findLastTradedPrice."""
    if not symbol:
        return {}
    try:
        data = find_equity_historical_data(symbol)
        if not data or not data[0].get("data"):
            return {}
        row = data[0]["data"][0]
        return {
            "lastTradedPrice": row.get("CH_LAST_TRADED_PRICE"),
            "fiftyTwoWeekLow": row.get("CH_52WEEK_LOW_PRICE"),
            "fiftyTwoWeekHigh": row.get("CH_52WEEK_HIGH_PRICE"),
        }
    except Exception:
        return {}
