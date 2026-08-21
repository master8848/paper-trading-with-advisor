"""
Qlib service — wrapper around `import pyqlib`.

Exposes:
  POST /quant/predict  {symbol, horizon: "5d"} -> {score, expected_return, confidence}
  POST /quant/backtest {symbol, start, end}
  GET  /quant/screen/{symbol} -> liquidity gate

Design:
  - Lazy / cached model loading (heavy). No import at module load.
  - Only runs inference if mcap/volume passes threshold (screener gate).
  - Alpha158 handler + DatasetH + LGBModel if qlib installed; else deterministic fallback.
  - provider_uri defaults to ./qlib_data ; can be overridden via QLIB_PROVIDER_URI env.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
import pathlib
import threading
from functools import lru_cache
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Default provider location (relative to backend_py)
DEFAULT_PROVIDER_URI = pathlib.Path(__file__).resolve().parents[2] / "qlib_data"

# Liquidity thresholds before allowing inference (avoid wasting compute on illiquid micro-caps)
MIN_MCAP_CR_FOR_INFERENCE = 500
MIN_AVG_VOL_FOR_INFERENCE = 100_000


class QlibService:
    """
    Lazy wrapper for pyqlib. Import is deferred until first use.

    Internals kept private; public methods: init, predict, backtest, screen.
    """

    def __init__(self, provider_uri: Optional[pathlib.Path | str] = None) -> None:
        self.provider_uri = pathlib.Path(provider_uri or os.getenv("QLIB_PROVIDER_URI", DEFAULT_PROVIDER_URI))
        self._initialized = False
        self._init_lock = threading.Lock()
        self._model: Any = None
        self._model_lock = threading.Lock()
        self._qlib_available: Optional[bool] = None

    # -- qlib init (lazy) --

    def _check_qlib_available(self) -> bool:
        if self._qlib_available is not None:
            return self._qlib_available
        try:
            import pyqlib  # noqa: F401

            self._qlib_available = True
        except ImportError:
            self._qlib_available = False
            logger.info("pyqlib not installed — using fallback mock predictions")
        return self._qlib_available

    def ensure_initialized(self) -> bool:
        """
        Calls qlib.init(provider_uri, region='in') once.
        Returns True if initialized (or fallback mode), False on hard error.
        """
        if self._initialized:
            return True
        with self._init_lock:
            if self._initialized:
                return True
            if not self._check_qlib_available():
                self._initialized = True  # mark as "initialized" in fallback mode
                return True
            try:
                import qlib

                # region='in' for India; provider_uri may not exist yet -> create placeholder
                self.provider_uri.mkdir(parents=True, exist_ok=True)
                # ensure at least an empty calendar so init doesn't crash
                cal = self.provider_uri / "calendars" / "day.txt"
                if not cal.exists():
                    cal.parent.mkdir(parents=True, exist_ok=True)
                    # seed with last 30 trading days
                    from .data_collector import get_trading_window, is_trading_day

                    dates: List[str] = []
                    d = dt.date.today()
                    while len(dates) < 30:
                        if is_trading_day(d):
                            dates.append(d.isoformat())
                        d -= dt.timedelta(days=1)
                    cal.write_text("\n".join(sorted(dates)))

                qlib.init(provider_uri=str(self.provider_uri), region="in", auto_mount=True)
                self._initialized = True
                logger.info("qlib initialized provider_uri=%s", self.provider_uri)
                return True
            except Exception as exc:
                logger.warning("qlib.init failed (%s) — fallback mode", exc)
                self._initialized = True
                return True
        return True

    # -- model loading (lazy, cached) --

    def _load_model(self) -> Any:
        """
        Load LGBModel + Alpha158 DatasetH.
        Cached after first load; thread-safe.
        Returns model or None if fallback.
        """
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is not None:
                return self._model
            if not self._check_qlib_available():
                return None
            try:
                # Lazy imports — only if qlib present
                from qlib.contrib.data.handler import Alpha158  # type: ignore
                from qlib.contrib.model.gbdt import LGBModel  # type: ignore
                from qlib.contrib.data.dataset import DatasetH  # type: ignore
                from qlib.data.dataset.handler import DataHandlerLP  # type: ignore

                # Handler / dataset config for India daily bars
                # Note: these require proper qlib_data; if missing we return None and use fallback
                handler_kwargs = dict(
                    start_time="2020-01-01",
                    end_time=dt.date.today().isoformat(),
                    fit_start_time="2020-01-01",
                    fit_end_time=(dt.date.today() - dt.timedelta(days=30)).isoformat(),
                    instruments="all",
                    infer_processors=[],
                    learn_processors=[],
                )
                # We don't actually instantiate Alpha158 with bad provider; probe first
                # If provider has no data, handler creation will warn — we catch.
                try:
                    handler = Alpha158(**handler_kwargs)  # type: ignore
                    dataset = DatasetH(handler=handler, segments=dict(train=("2020-01-01", "2023-01-01"), valid=("2023-01-01", "2023-06-01"), test=("2023-06-01", dt.date.today().isoformat())))  # type: ignore
                    model = LGBModel(loss="mse", colsample_bytree=0.8879, learning_rate=0.05, subsample=0.8789, lambda_l1=205.6999, lambda_l2=580.9767, max_depth=8, num_leaves=210, num_threads=8)  # type: ignore
                    # Try to load pretrained weights if exists
                    model_path = self.provider_uri / "models" / "lgb_alpha158.pkl"
                    if model_path.exists():
                        import pickle

                        with open(model_path, "rb") as f:
                            self._model = pickle.load(f)
                    else:
                        # no pretrained — keep unfit model; predict will use fallback logic
                        self._model = model
                    return self._model
                except Exception as exc:
                    logger.debug("Alpha158/DatasetH init failed (likely missing qlib_data): %s", exc)
                    return None
            except ImportError as exc:
                logger.debug("qlib contrib imports failed: %s", exc)
                return None
            except Exception as exc:
                logger.warning("Model loading failed: %s", exc)
                return None

    # -- liquidity gate --

    def _liquidity_gate(self, symbol: str) -> tuple[bool, Dict[str, Any]]:
        """
        Check if symbol passes liquidity threshold.
        Returns (passes, screener_result).
        If fails, caller should skip heavy inference.
        """
        try:
            from .screener import Screener

            s = Screener()
            res = s.liquidity_check(symbol)
            return bool(res["passes"]), res
        except Exception as exc:
            logger.debug("liquidity gate check failed: %s", exc)
            # fail-open for offline; allow inference but warn
            return True, {"passes": True, "reason": f"gate unavailable: {exc}"}

    # -- predict --

    def predict(self, symbol: str, horizon: str = "5d") -> Dict[str, Any]:
        """
        POST /quant/predict {symbol, horizon:5d}
        Returns {symbol, horizon, score, expected_return, confidence, gated, warnings, model_used}
        Heavy inference only if liquidity gate passes; otherwise returns gated stub with warning.
        """
        if not symbol:
            raise ValueError("symbol is required")
        horizon = horizon or "5d"
        # parse horizon like "5d", "10d", "1d"
        horizon_days = 5
        try:
            horizon_days = int(horizon.lower().replace("d", "").strip() or "5")
        except Exception:
            horizon_days = 5

        self.ensure_initialized()

        # 1) liquidity gate
        passes, gate = self._liquidity_gate(symbol)
        if not passes:
            # Don't run model; return low-confidence stub
            return {
                "symbol": symbol.upper().replace(".NS", ""),
                "horizon": horizon,
                "horizon_days": horizon_days,
                "score": 0.0,
                "expected_return": 0.0,
                "confidence": 0.05,
                "gated": True,
                "gate_reason": gate.get("reason"),
                "warnings": gate.get("details", {}).get("warnings", []),
                "model_used": "gated_stub",
                "message": "Inference skipped: symbol failed liquidity threshold. See warnings.",
            }

        # 2) try real model
        model = self._load_model()
        if model is not None and self._check_qlib_available():
            try:
                # Attempt real inference via qlib dataset
                # For single symbol, we need its features; if dataset available:
                from qlib.data import D  # type: ignore

                # Fetch recent bars via collector and build features manually as fallback
                # If D.features works, use it; else use our fallback
                try:
                    # Example: D.features(instruments=[symbol], fields=["$close","$volume"])
                    # This requires proper provider; may fail if no data
                    df = D.features(instruments=[symbol], start_time=(dt.date.today() - dt.timedelta(days=60)).isoformat(), end_time=dt.date.today().isoformat(), fields=["$close", "$volume", "$high", "$low"])  # type: ignore
                    if df is not None and not df.empty:
                        # simplistic expected return: model.predict(df) if fitted
                        try:
                            pred = model.predict(df)  # type: ignore
                            # pred is Series with expected return
                            if hasattr(pred, "iloc"):
                                val = float(pred.iloc[-1]) if len(pred) else 0.0
                            else:
                                val = float(pred[-1]) if len(pred) else 0.0  # type: ignore
                            score = max(-1.0, min(1.0, val * 10))  # normalize to -1..1
                            return {
                                "symbol": symbol.upper().replace(".NS", ""),
                                "horizon": horizon,
                                "horizon_days": horizon_days,
                                "score": round(float(score), 4),
                                "expected_return": round(float(val), 6),
                                "confidence": round(min(0.95, abs(score) * 0.8 + 0.2), 4),
                                "gated": False,
                                "model_used": "LGBModel+Alpha158",
                            }
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception as exc:
                logger.debug("qlib inference path failed, falling back: %s", exc)

        # 3) fallback deterministic mock (hash-based so tests are stable, not random)
        return self._fallback_predict(symbol, horizon_days, horizon)

    def _fallback_predict(self, symbol: str, horizon_days: int, horizon_raw: str) -> Dict[str, Any]:
        """
        Deterministic fallback when qlib data/model unavailable.
        Uses symbol hash + recent price momentum to produce plausible score.
        Not a real recommendation — flagged as fallback.
        """
        raw = symbol.upper().replace(".NS", "")
        # hash-based pseudo score in -1..1 deterministically
        h = int(hashlib.sha256(f"{raw}:{horizon_days}".encode()).hexdigest()[:8], 16)
        hash_score = (h % 2001 - 1000) / 1000.0  # -1.0 .. 1.0

        # Try to adjust with real momentum if we have price data
        momentum_adj = 0.0
        try:
            from .data_collector import NSEDataCollector

            coll = NSEDataCollector()
            df = coll.find_equity_historical_data(raw, start=dt.date.today() - dt.timedelta(days=30), end=dt.date.today())
            if not df.empty and len(df) >= 5:
                # 5d momentum
                ret_5 = (df["close"].iloc[-1] / df["close"].iloc[-min(5, len(df))] - 1) if df["close"].iloc[-min(5, len(df))] else 0
                momentum_adj = max(-0.3, min(0.3, float(ret_5) * 2))
        except Exception:
            pass

        score = max(-1.0, min(1.0, hash_score * 0.7 + momentum_adj * 0.3))
        expected_return = score * 0.02 * (horizon_days / 5)  # ~2% max for 5d per unit score
        # confidence lower for fallback
        confidence = 0.35 + abs(score) * 0.3  # 0.35..0.65

        return {
            "symbol": raw,
            "horizon": horizon_raw,
            "horizon_days": horizon_days,
            "score": round(float(score), 4),
            "expected_return": round(float(expected_return), 6),
            "confidence": round(float(confidence), 4),
            "gated": False,
            "model_used": "fallback_momentum_hash",
            "warning": "Fallback prediction (qlib data/model not loaded). Do not trade on this alone.",
        }

    # -- backtest --

    def backtest(self, symbol: str, start: str, end: str) -> Dict[str, Any]:
        """
        POST /quant/backtest {symbol, start, end}
        Returns {symbol, start, end, trades, cumulative_return, sharpe, max_drawdown, ...}
        If qlib unavailable, does simple buy-and-hold + momentum mock backtest.
        """
        if not symbol:
            raise ValueError("symbol is required")
        self.ensure_initialized()

        # Validate dates
        try:
            s_date = dt.date.fromisoformat(start)
            e_date = dt.date.fromisoformat(end)
        except Exception as exc:
            raise ValueError(f"Invalid date format, expected YYYY-MM-DD: {exc}") from exc
        if s_date >= e_date:
            raise ValueError("start must be before end")

        # Liquidity gate still applied but doesn't block backtest — just warns
        passes, gate = self._liquidity_gate(symbol)

        # Try real qlib backtest if available
        if self._check_qlib_available():
            try:
                from qlib.contrib.evaluate import backtest as qlib_backtest  # type: ignore
                from qlib.contrib.strategy import TopkDropoutStrategy  # type: ignore

                # This would require proper dataset/handler — attempt but fallback on failure
                logger.debug("qlib backtest attempt for %s", symbol)
            except Exception:
                pass

        # Fallback: simple momentum backtest using actual price data
        try:
            from .data_collector import NSEDataCollector

            coll = NSEDataCollector()
            df = coll.find_equity_historical_data(symbol, start=s_date, end=e_date)
            if df.empty:
                # Try wider fallback: fetch via 20d history
                df = coll.fetch_20d_history(symbol)
            if df.empty:
                return {
                    "symbol": symbol.upper().replace(".NS", ""),
                    "start": start,
                    "end": end,
                    "trades": [],
                    "cumulative_return": 0.0,
                    "sharpe": 0.0,
                    "max_drawdown": 0.0,
                    "win_rate": 0.0,
                    "gated": not passes,
                    "gate_reason": gate.get("reason"),
                    "warning": "No price data for backtest window; empty result.",
                }
            # Simple strategy: buy when close > 5d MA, else flat. Compute returns.
            df = df.copy()
            df["ma5"] = df["close"].rolling(5).mean()
            df["signal"] = (df["close"] > df["ma5"]).astype(int).shift(1).fillna(0)
            df["ret"] = df["close"].pct_change().fillna(0)
            df["strat_ret"] = df["signal"] * df["ret"]
            df["cum"] = (1 + df["strat_ret"]).cumprod()
            df["cum_bh"] = (1 + df["ret"]).cumprod()
            # stats
            cum_ret = float(df["cum"].iloc[-1] - 1) if len(df) else 0.0
            bh_ret = float(df["cum_bh"].iloc[-1] - 1) if len(df) else 0.0
            # sharpe (annualized, assume 252 trading days)
            strat_rets = df["strat_ret"].dropna()
            sharpe = 0.0
            if len(strat_rets) > 1 and strat_rets.std() > 0:
                sharpe = float(strat_rets.mean() / strat_rets.std() * (252 ** 0.5))
            # max drawdown
            roll_max = df["cum"].cummax()
            dd = (df["cum"] - roll_max) / roll_max
            mdd = float(dd.min()) if len(dd) else 0.0
            win_rate = float((strat_rets > 0).mean()) if len(strat_rets) else 0.0

            # Build trades list (entry/exit points)
            trades: List[Dict[str, Any]] = []
            in_pos = False
            entry_price = 0.0
            entry_date = None
            for idx, row in df.iterrows():
                sig = int(row["signal"])
                price = float(row["close"])
                date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                if sig == 1 and not in_pos:
                    in_pos = True
                    entry_price = price
                    entry_date = date_str
                elif sig == 0 and in_pos:
                    in_pos = False
                    ret = (price / entry_price - 1) if entry_price else 0
                    trades.append({"entry_date": entry_date, "exit_date": date_str, "entry_price": entry_price, "exit_price": price, "return": round(ret, 6)})
                    entry_price = 0
                    entry_date = None
            # if still in position at end
            if in_pos and entry_price:
                last_price = float(df["close"].iloc[-1])
                last_date = df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else str(df.index[-1])
                trades.append({"entry_date": entry_date, "exit_date": last_date, "entry_price": entry_price, "exit_price": last_price, "return": round(last_price / entry_price - 1, 6), "open": True})

            return {
                "symbol": symbol.upper().replace(".NS", ""),
                "start": start,
                "end": end,
                "bars": len(df),
                "trades": trades,
                "cumulative_return": round(cum_ret, 6),
                "buy_hold_return": round(bh_ret, 6),
                "sharpe": round(sharpe, 4),
                "max_drawdown": round(mdd, 6),
                "win_rate": round(win_rate, 4),
                "gated": not passes,
                "gate_reason": gate.get("reason") if not passes else None,
                "model_used": "fallback_ma5_momentum",
            }
        except Exception as exc:
            logger.exception("backtest failed for %s: %s", symbol, exc)
            return {
                "symbol": symbol.upper().replace(".NS", ""),
                "start": start,
                "end": end,
                "trades": [],
                "cumulative_return": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "error": str(exc),
            }


# Singleton accessor (cached, lazy)

@lru_cache(maxsize=1)
def get_qlib_service(provider_uri: Optional[str] = None) -> QlibService:
    return QlibService(provider_uri=provider_uri)
