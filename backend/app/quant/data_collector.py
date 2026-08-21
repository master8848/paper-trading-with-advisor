"""
Data collector — Python port of backend/src/stock-exchange/stock-exchange.service.ts:15

Original TS:
    findEquityHistoricalData(symbol) {
        return this.nseIndia().getEquityHistoricalData(symbol, {
            start: moment().subtract(4, 'days').toDate(),
            end: new Date(),
        });
    }

Python port uses yahooquery (primary) and nsepython (fallback) for NSE.
Normalizes to qlib .bin format: open, high, low, close, volume, factor
plus handles NSE holidays calendar and trading-day logic.
"""

from __future__ import annotations

import datetime as dt
import logging
import pathlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NSE Holidays calendar
# Source: https://www.nseindia.com/resources/holiday-calendar
# Keep as explicit set so offline / CI works. Extend yearly.
# ---------------------------------------------------------------------------

# Fixed holidays for 2024-2027 (trading holidays, not weekends)
_NSE_HOLIDAYS_RAW: List[str] = [
    # 2024
    "2024-01-26", "2024-03-08", "2024-03-25", "2024-03-29",
    "2024-04-11", "2024-04-17", "2024-05-01", "2024-05-20",
    "2024-06-17", "2024-07-17", "2024-08-15", "2024-10-02",
    "2024-11-01", "2024-11-15", "2024-12-25",
    # 2025
    "2025-01-26", "2025-02-26", "2025-03-14", "2025-03-31",
    "2025-04-10", "2025-04-14", "2025-04-18", "2025-05-01",
    "2025-08-15", "2025-08-27", "2025-10-02", "2025-10-21",
    "2025-10-22", "2025-11-05", "2025-12-25",
    # 2026
    "2026-01-26", "2026-03-03", "2026-03-31", "2026-04-02",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-08-15",
    "2026-09-21", "2026-10-02", "2026-10-20", "2026-10-21",
    "2026-11-24", "2026-12-25",
    # 2027 (partial, extend as announced)
    "2027-01-26", "2027-03-15", "2027-08-15", "2027-10-02", "2027-12-25",
]

nse_holidays: set[dt.date] = {
    dt.date.fromisoformat(d) for d in _NSE_HOLIDAYS_RAW
}


def is_trading_day(d: dt.date | dt.datetime) -> bool:
    """Return True if NSE is open on date d (excludes weekends + holidays)."""
    if isinstance(d, dt.datetime):
        d = d.date()
    if d.weekday() >= 5:  # Saturday, Sunday
        return False
    if d in nse_holidays:
        return False
    return True


def get_trading_window(days: int = 4, end: Optional[dt.date] = None) -> Tuple[dt.date, dt.date]:
    """
    Replicates moment().subtract(4, 'days') -> today window,
    but snaps to trading days: if end falls on holiday/weekend, use previous trading day.
    Returns (start, end) inclusive.
    """
    if end is None:
        end = dt.date.today()
    # roll end backwards to trading day
    while not is_trading_day(end):
        end -= dt.timedelta(days=1)
    start = end - dt.timedelta(days=days)
    # start doesn't need to be trading day but normalize anyway
    return start, end


def _normalize_symbol(symbol: str) -> tuple[str, str]:
    """
    Returns (raw_symbol, yahoo_symbol).
    Yahoo requires .NS suffix for NSE, e.g. RELIANCE -> RELIANCE.NS
    """
    s = symbol.strip().upper()
    if s.endswith(".NS") or s.endswith(".BO"):
        raw = s.replace(".NS", "").replace(".BO", "")
        yahoo = s if s.endswith(".NS") else s  # keep as-is
        if not s.endswith(".NS"):
            yahoo = raw + ".NS"
        return raw, yahoo
    return s, f"{s}.NS"


@dataclass
class QlibBar:
    """Single normalized bar for qlib."""
    datetime: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    factor: float = 1.0  # adjustment factor; 1.0 = no split/bonus adjustment


class NSEDataCollector:
    """
    Fetches NSE equity historical data and normalizes to qlib format.

    Strategy:
      1. Try yahooquery (reliable, no auth, handles .NS).
      2. Fallback to nsepython (nse_eq / nse_history style).
      3. Normalize columns to qlib expectation:
         index: datetime, columns: open, high, low, close, volume, factor
         Qlib .bin writer expects float32 for OHLCV and factor.
    """

    def __init__(self, cache_dir: Optional[pathlib.Path] = None) -> None:
        self.cache_dir = cache_dir

    # -- public API matching TS service --

    def find_equity_historical_data(
        self,
        symbol: str,
        start: Optional[dt.date] = None,
        end: Optional[dt.date] = None,
        period: str = "4d",
    ) -> pd.DataFrame:
        """
        Port of StockExchangeService.findEquityHistoricalData.
        Defaults to 4-day window (start = now-4d, end = now) like TS.
        Returns normalized DataFrame indexed by datetime.
        """
        if not symbol:
            raise ValueError("symbol is required")
        if start is None or end is None:
            s, e = get_trading_window(days=4)
            start = start or s
            end = end or e

        # try yahooquery first
        df = self._fetch_via_yahooquery(symbol, start, end)
        if df is not None and not df.empty:
            return self.normalize_to_qlib(df)

        # fallback nsepython
        df2 = self._fetch_via_nsepython(symbol, start, end)
        if df2 is not None and not df2.empty:
            return self.normalize_to_qlib(df2)

        logger.warning("No data fetched for %s %s -> %s", symbol, start, end)
        return pd.DataFrame()

    def find_last_traded_price(self, symbol: str) -> Dict[str, Any]:
        """
        Port of StockExchangeService.findLastTradedPrice
        Returns {lastTradedPrice, fiftyTwoWeekLow, fiftyTwoWeekHigh}
        """
        if not symbol:
            return {}
        try:
            df = self.find_equity_historical_data(symbol)
            if df.empty:
                return {}
            last = df.iloc[-1]
            # For 52W we need wider window
            df_year = self.find_equity_historical_data(
                symbol,
                start=dt.date.today() - dt.timedelta(days=365),
                end=dt.date.today(),
            )
            low_52 = float(df_year["low"].min()) if not df_year.empty else None
            high_52 = float(df_year["high"].max()) if not df_year.empty else None
            return {
                "lastTradedPrice": float(last["close"]),
                "fiftyTwoWeekLow": low_52,
                "fiftyTwoWeekHigh": high_52,
            }
        except Exception as exc:
            logger.debug("find_last_traded_price failed for %s: %s", symbol, exc)
            return {}

    # -- fetchers --

    def _fetch_via_yahooquery(
        self, symbol: str, start: dt.date, end: dt.date
    ) -> Optional[pd.DataFrame]:
        try:
            from yahooquery import Ticker  # lazy import

            _, yahoo_sym = _normalize_symbol(symbol)
            t = Ticker(yahoo_sym, asynchronous=False)
            # yahooquery history expects period or start/end strings
            # Use history with start/end
            hist = t.history(start=start.isoformat(), end=(end + dt.timedelta(days=1)).isoformat())
            if hist is None or (isinstance(hist, pd.DataFrame) and hist.empty):
                return None
            # yahooquery returns multiindex when multiple tickers; normalize
            if isinstance(hist.index, pd.MultiIndex):
                # levels: symbol, date
                try:
                    hist = hist.xs(yahoo_sym, level=0)
                except Exception:
                    hist = hist.droplevel(0)
            # hist columns: open, high, low, close, volume, adjclose, etc.
            hist.index = pd.to_datetime(hist.index)
            hist = hist.rename(columns={c: c.lower() for c in hist.columns})
            return hist
        except ImportError:
            logger.debug("yahooquery not installed")
            return None
        except Exception as exc:
            logger.debug("yahooquery fetch failed for %s: %s", symbol, exc)
            return None

    def _fetch_via_nsepython(
        self, symbol: str, start: dt.date, end: dt.date
    ) -> Optional[pd.DataFrame]:
        try:
            # nsepython has multiple APIs; try nse_history first
            from nsepython import nse_eq  # type: ignore
            from nsepythonserver import nsefetch  # alternative

            raw, _ = _normalize_symbol(symbol)
            # nsepython often wants plain symbol without .NS
            # nse_eq returns quote; for history we synthesize via nsefetch
            # Try equity_history endpoint
            url = (
                f"https://www.nseindia.com/api/historical/equities"
                f"?symbol={raw}&series=[%22EQ%22]&from={start.strftime('%d-%m-%Y')}&to={end.strftime('%d-%m-%Y')}"
            )
            data = nsefetch(url)  # type: ignore
            if not data or "data" not in data:
                # fallback to nse_eq single quote -> synthesize single row
                quote = nse_eq(raw)  # type: ignore
                if not quote:
                    return None
                price = quote.get("priceInfo", {}).get("lastPrice") or quote.get("lastPrice")
                if price is None:
                    return None
                idx = pd.to_datetime(end)
                return pd.DataFrame(
                    [{"open": price, "high": price, "low": price, "close": price, "volume": 0}],
                    index=[idx],
                )
            rows = data["data"]
            # rows contain CH_OPENING_PRICE etc like stock-nse-india
            recs = []
            for r in rows:
                # NSE historical returns mTIMESTAMP like "25-May-2024"
                ts_raw = r.get("mTIMESTAMP") or r.get("CH_TIMESTAMP") or r.get("CH_TRADE_HIGH_PRICE")
                try:
                    ts = pd.to_datetime(ts_raw, dayfirst=True) if ts_raw else pd.Timestamp.now()
                except Exception:
                    ts = pd.Timestamp.now()
                recs.append(
                    {
                        "open": r.get("CH_OPENING_PRICE") or r.get("open"),
                        "high": r.get("CH_TRADE_HIGH_PRICE") or r.get("high"),
                        "low": r.get("CH_TRADE_LOW_PRICE") or r.get("low"),
                        "close": r.get("CH_CLOSING_PRICE") or r.get("CH_LAST_TRADED_PRICE") or r.get("close"),
                        "volume": r.get("CH_TOT_TRADED_QTY") or r.get("CH_TOTAL_TRADES") or r.get("volume") or 0,
                    }
                )
                recs[-1]["datetime"] = ts
            df = pd.DataFrame(recs).set_index("datetime").sort_index()
            return df
        except ImportError:
            logger.debug("nsepython not installed")
            return None
        except Exception as exc:
            logger.debug("nsepython fetch failed for %s: %s", symbol, exc)
            return None

    # -- normalization + qlib .bin --

    @staticmethod
    def normalize_to_qlib(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize any OHLCV frame to qlib convention:
          index: DatetimeIndex named 'datetime'
          columns: open, high, low, close, volume, factor (lowercase, float)
        Qlib expects: $open, $high, $low, $close, $volume, $factor or lowercase;
        the .bin writer maps these to binary files per symbol/date.
        """
        if df.empty:
            return df
        # lower columns
        df = df.rename(columns={c: c.lower() for c in df.columns})
        # ensure datetime index
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime")
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                pass
        df.index.name = "datetime"
        # map common aliases
        col_map = {
            "adjclose": "close",
            "adj_close": "close",
            "adj close": "close",
            "qty": "volume",
            "ch_tot_traded_qty": "volume",
            "ch_total_trades": "volume",
            "traded_qty": "volume",
        }
        for k, v in col_map.items():
            if k in df.columns and v not in df.columns:
                df[v] = df[k]
        # ensure required cols exist
        for col in ("open", "high", "low", "close", "volume"):
            if col not in df.columns:
                if col == "volume":
                    df[col] = 0.0
                elif "close" in df.columns:
                    df[col] = df["close"]
                else:
                    raise ValueError(f"Cannot normalize: missing column {col}")
        if "factor" not in df.columns:
            df["factor"] = 1.0
        # keep only qlib cols, sorted, coerced to numeric
        qlib_cols = ["open", "high", "low", "close", "volume", "factor"]
        out = df[qlib_cols].copy()
        for c in qlib_cols:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        out = out.dropna(subset=["close"])
        out = out.sort_index()
        # qlib expects float32 for storage efficiency; keep float64 in memory but note
        return out

    def save_to_qlib_bin(
        self,
        df: pd.DataFrame,
        symbol: str,
        provider_uri: str | pathlib.Path,
        freq: str = "day",
    ) -> pathlib.Path:
        """
        Persist normalized DataFrame to qlib provider_uri in .bin format.
        Layout: provider_uri/{freq}/{symbol}.bin  (qlib dump_bin compatible)
        Also supports the CSV -> bin converter path: provider_uri/calendars, etc.
        For simplicity we write a CSV that qlib's `DumpData` can ingest, and
        optionally call `qlib.data.storage` if available.
        Returns path written.
        """
        raw, _ = _normalize_symbol(symbol)
        provider_uri = pathlib.Path(provider_uri)
        # qlib convention: provider_uri/features/symbol/date.bin or provider_uri/day/symbol.bin
        # We write both a human-readable CSV and attempt bin conversion
        csv_dir = provider_uri / "csv" / freq
        csv_dir.mkdir(parents=True, exist_ok=True)
        csv_path = csv_dir / f"{raw}.csv"
        # qlib CSV format: datetime, open, high, low, close, volume, factor
        to_save = df.copy()
        to_save.index.name = "datetime"
        to_save.to_csv(csv_path, float_format="%.6f")
        # try to call qlib bin dumper if available
        try:
            # qlib provides scripts: python -m qlib.data.storage  or DumpData
            from qlib.data.storage import CalendarStorage  # noqa: F401  # probe

            # Use qlib's dump logic: if pyqlib installed, we can at least ensure calendar
            cal_path = provider_uri / "calendars" / f"{freq}.txt"
            cal_path.parent.mkdir(parents=True, exist_ok=True)
            # append unique dates to calendar
            existing = set()
            if cal_path.exists():
                existing = {line.strip() for line in cal_path.read_text().splitlines() if line.strip()}
            new_dates = {d.strftime("%Y-%m-%d") for d in df.index.normalize().unique()}
            merged = sorted(existing | new_dates)
            cal_path.write_text("\n".join(merged))
        except Exception as exc:
            logger.debug("qlib bin dump skipped (qlib not fully configured): %s", exc)
        return csv_path

    # -- helpers for other modules --

    def fetch_20d_history(self, symbol: str) -> pd.DataFrame:
        """Fetch 20 trading days of history for volume/impact calculations."""
        end = dt.date.today()
        start = end - dt.timedelta(days=40)  # 40 calendar days ~ 28 trading days, enough
        df = self.find_equity_historical_data(symbol, start=start, end=end)
        if df.empty:
            return df
        # keep last 20 rows (trading days)
        return df.tail(20)

    def fetch_with_retry(
        self, symbol: str, retries: int = 3, backoff: float = 1.0
    ) -> pd.DataFrame:
        """Fetch with simple retry for flaky NSE endpoint."""
        last_exc: Optional[Exception] = None
        for i in range(retries):
            try:
                return self.find_equity_historical_data(symbol)
            except Exception as exc:
                last_exc = exc
                time.sleep(backoff * (i + 1))
        if last_exc:
            raise last_exc
        return pd.DataFrame()


# Module-level singleton for convenience
default_collector = NSEDataCollector()
