"""
Tests stub for app/quant — covers execution realism, screener, data collector, qlib service.

Run: pytest -q
All tests are offline-safe (no network required) via monkeypatching.
"""

import datetime as dt
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(rows=25, volume=50000, close_start=100.0) -> pd.DataFrame:
    idx = pd.date_range(end=dt.date.today(), periods=rows, freq="B")
    closes = [close_start + i * 0.5 for i in range(rows)]
    df = pd.DataFrame(
        {
            "open": [c - 0.2 for c in closes],
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "volume": [volume] * rows,
            "factor": [1.0] * rows,
        },
        index=idx,
    )
    df.index.name = "datetime"
    return df


# ---------------------------------------------------------------------------
# data_collector
# ---------------------------------------------------------------------------

class TestDataCollector:
    def test_normalize_to_qlib(self):
        from app.quant.data_collector import NSEDataCollector

        raw = pd.DataFrame(
            {"open": [100], "high": [105], "low": [99], "close": [103], "volume": [50000]},
            index=[pd.Timestamp("2024-01-02")],
        )
        out = NSEDataCollector.normalize_to_qlib(raw)
        assert list(out.columns) == ["open", "high", "low", "close", "volume", "factor"]
        assert out["factor"].iloc[0] == 1.0

    def test_is_trading_day_weekend(self):
        from app.quant.data_collector import is_trading_day

        assert is_trading_day(dt.date(2024, 1, 6)) is False  # Saturday
        assert is_trading_day(dt.date(2024, 1, 8)) is True  # Monday

    def test_is_trading_day_holiday(self):
        from app.quant.data_collector import is_trading_day, nse_holidays

        # Pick a known holiday
        h = next(iter(nse_holidays))
        assert is_trading_day(h) is False

    def test_get_trading_window(self):
        from app.quant.data_collector import get_trading_window

        s, e = get_trading_window(days=4)
        assert (e - s).days == 4
        # e should be trading day
        from app.quant.data_collector import is_trading_day as is_td

        assert is_td(e)

    def test_find_equity_historical_data_uses_yahooquery(self):
        from app.quant.data_collector import NSEDataCollector

        coll = NSEDataCollector()
        fake_df = _make_ohlcv(rows=5, volume=100000)
        # patch yahooquery path to return fake
        with patch.object(coll, "_fetch_via_yahooquery", return_value=fake_df):
            out = coll.find_equity_historical_data("RELIANCE")
            assert not out.empty
            assert "close" in out.columns

    def test_save_to_qlib_bin(self, tmp_path):
        from app.quant.data_collector import NSEDataCollector

        coll = NSEDataCollector()
        df = _make_ohlcv(rows=10)
        p = coll.save_to_qlib_bin(df, "RELIANCE", provider_uri=tmp_path / "qlib_data")
        assert p.exists()
        assert p.suffix == ".csv"


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------

class TestExecution:
    def test_feasible_qty_10pct_rule(self):
        from app.quant.execution import ExecutionSimulator

        sim = ExecutionSimulator()
        # Mock metrics: avg_vol 200k -> feasible 20k? but qty 1000 => feasible 1000
        mock_metrics = MagicMock()
        mock_metrics.avg_volume_20d = 200_000
        mock_metrics.last_close = 100.0
        mock_metrics.bid_ask_spread_pct = 0.0005
        mock_metrics.volatility_20d = 0.01
        mock_metrics.circuit_limit_pct = 10.0
        with patch.object(sim, "get_market_metrics", return_value=mock_metrics):
            res = sim.simulate("RELIANCE", qty=1000, ideal_price=100.0)
            assert res.feasible_qty == 1000  # 10% of 200k = 20k > 1000
            assert res.illiquid_flag is False

    def test_illiquid_feasible_capped(self):
        from app.quant.execution import ExecutionSimulator

        sim = ExecutionSimulator()
        mock_metrics = MagicMock()
        mock_metrics.avg_volume_20d = 2_000  # illiquid
        mock_metrics.last_close = 50.0
        mock_metrics.bid_ask_spread_pct = 0.005
        mock_metrics.volatility_20d = 0.02
        mock_metrics.circuit_limit_pct = 5.0
        with patch.object(sim, "get_market_metrics", return_value=mock_metrics):
            res = sim.simulate("ILLIQUID", qty=1000, ideal_price=50.0)
            assert res.feasible_qty == 200  # 10% of 2000
            assert res.illiquid_flag is True
            assert res.warning is not None
            assert "Only 200 of 1000" in res.warning

    def test_slippage_formula(self):
        from app.quant.execution import ExecutionSimulator

        sim = ExecutionSimulator()
        mock_metrics = MagicMock()
        mock_metrics.avg_volume_20d = 100_000
        mock_metrics.last_close = 100.0
        mock_metrics.bid_ask_spread_pct = 0.0
        mock_metrics.volatility_20d = None
        mock_metrics.circuit_limit_pct = 20.0
        with patch.object(sim, "get_market_metrics", return_value=mock_metrics):
            res = sim.simulate("TEST", qty=1000, ideal_price=100.0)
            # slippage = 0.001 + 0.005 * (1000/100000)=0.001+0.00005=0.00105
            assert abs(res.slippage_pct - 0.00105) < 1e-6
            assert res.realistic_buy_price > 100.0
            assert res.realistic_sell_price < 100.0

    def test_simulate_execution_function(self):
        from app.quant.execution import simulate_execution

        with patch("app.quant.execution.ExecutionSimulator.get_market_metrics") as m:
            mm = MagicMock()
            mm.avg_volume_20d = 500_000
            mm.last_close = 200.0
            mm.bid_ask_spread_pct = 0.0005
            mm.volatility_20d = 0.015
            mm.circuit_limit_pct = 10.0
            m.return_value = mm
            d = simulate_execution("TCS", qty=1000, ideal_price=200.0)
            assert "realistic_buy_price" in d
            assert "feasible_qty" in d
            assert "warning" in d


# ---------------------------------------------------------------------------
# screener
# ---------------------------------------------------------------------------

class TestScreener:
    def test_warnings_low_volume(self):
        from app.quant.screener import Screener

        s = Screener()
        with patch.object(s, "get_mcap", return_value=1_000 * 1e7):  # 1000 Cr
            with patch.object(s, "get_avg_volume_20d", return_value=50_000):
                with patch.object(s, "get_impact_cost_pct", return_value=0.01):
                    with patch.object(s.simulator, "get_market_metrics") as mm:
                        m = MagicMock()
                        m.delivery_pct = 40.0
                        mm.return_value = m
                        res = s.check_warnings("TEST")
                        assert res["illiquid"] is True
                        assert any(f["code"] == "LOW_VOLUME" for f in res["flags"])

    def test_warnings_all_pass(self):
        from app.quant.screener import Screener

        s = Screener()
        with patch.object(s, "get_mcap", return_value=5_000 * 1e7):
            with patch.object(s, "get_avg_volume_20d", return_value=2_000_000):
                with patch.object(s, "get_impact_cost_pct", return_value=0.005):
                    with patch.object(s.simulator, "get_market_metrics") as mm:
                        m = MagicMock()
                        m.delivery_pct = 50.0
                        mm.return_value = m
                        res = s.check_warnings("RELIANCE")
                        assert res["illiquid"] is False
                        assert res["warnings"] == []

    def test_liquidity_check(self):
        from app.quant.screener import Screener

        s = Screener()
        with patch.object(s, "check_warnings", return_value={"flags": [{"code": "MCAP_OK", "severity": "info"}, {"code": "VOLUME_OK", "severity": "info"}, {"code": "IMPACT_OK", "severity": "info"}], "warnings": [], "symbol": "RELIANCE", "mcap_cr": 1000, "avg_volume_20d": 1_000_000, "impact_cost_pct": 0.005}):
            res = s.liquidity_check("RELIANCE")
            assert res["passes"] is True


# ---------------------------------------------------------------------------
# qlib_service
# ---------------------------------------------------------------------------

class TestQlibService:
    def test_predict_gated_when_illiquid(self):
        from app.quant.qlib_service import QlibService

        svc = QlibService(provider_uri="/tmp/test_qlib")
        with patch.object(svc, "_liquidity_gate", return_value=(False, {"reason": "LOW_VOLUME", "details": {"warnings": ["Low volume"]}})):
            res = svc.predict("ILLIQUID", horizon="5d")
            assert res["gated"] is True
            assert res["score"] == 0.0

    def test_predict_fallback_deterministic(self):
        from app.quant.qlib_service import QlibService

        svc = QlibService(provider_uri="/tmp/test_qlib")
        with patch.object(svc, "_liquidity_gate", return_value=(True, {"reason": "ok"})):
            with patch.object(svc, "_load_model", return_value=None):
                r1 = svc.predict("RELIANCE", horizon="5d")
                r2 = svc.predict("RELIANCE", horizon="5d")
                assert r1["score"] == r2["score"]  # deterministic
                assert -1 <= r1["score"] <= 1
                assert 0 <= r1["confidence"] <= 1

    def test_backtest_returns_structure(self):
        from app.quant.qlib_service import QlibService

        svc = QlibService(provider_uri="/tmp/test_qlib")
        fake_df = _make_ohlcv(rows=30, volume=80000, close_start=150)
        with patch("app.quant.data_collector.NSEDataCollector.find_equity_historical_data", return_value=fake_df):
            res = svc.backtest("RELIANCE", start="2024-01-01", end="2024-02-15")
            assert "cumulative_return" in res
            assert "sharpe" in res
            assert "max_drawdown" in res
            assert "trades" in res


# ---------------------------------------------------------------------------
# router (FastAPI integration)
# ---------------------------------------------------------------------------

def _quant_client():
    """Isolated FastAPI client with only quant router — avoids pulling main's DB deps."""
    from fastapi import FastAPI

    from app.quant.router import router as quant_router

    _app = FastAPI()
    _app.include_router(quant_router)
    return TestClient(_app)


class TestRouter:
    def test_health(self):
        c = _quant_client()
        r = c.get("/quant/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_predict_endpoint(self):
        c = _quant_client()
        with patch("app.quant.router.get_qlib_service") as mock_get:
            msvc = MagicMock()
            msvc.predict.return_value = {"symbol": "RELIANCE", "horizon": "5d", "horizon_days": 5, "score": 0.42, "expected_return": 0.008, "confidence": 0.6, "gated": False, "model_used": "fallback"}
            mock_get.return_value = msvc
            r = c.post("/quant/predict", json={"symbol": "RELIANCE", "horizon": "5d"})
            assert r.status_code == 200
            assert r.json()["symbol"] == "RELIANCE"

    def test_warnings_endpoint(self):
        c = _quant_client()
        with patch("app.quant.router.get_screener") as mock_get:
            ms = MagicMock()
            ms.check_warnings.return_value = {"symbol": "TEST", "illiquid": True, "warnings": ["Low volume"]}
            mock_get.return_value = ms
            r = c.get("/quant/warnings/TEST")
            assert r.status_code == 200

    def test_execution_endpoint(self):
        c = _quant_client()
        with patch("app.quant.execution.ExecutionSimulator.get_market_metrics") as m:
            mm = MagicMock()
            mm.avg_volume_20d = 300_000
            mm.last_close = 100.0
            mm.bid_ask_spread_pct = 0.001
            mm.volatility_20d = 0.01
            mm.circuit_limit_pct = 10.0
            m.return_value = mm
            r = c.post("/quant/execution/simulate", json={"symbol": "RELIANCE", "qty": 1000, "ideal_price": 100})
            assert r.status_code == 200
            assert "feasible_qty" in r.json()
