"""
Execution realism — "what you could actually buy/sell".

Addresses: user claims "I bought 1000 at perfect time" on illiquid name.
We fetch avgVolume 20D, delivery %, circuit limits, bid-ask spread and compute:

  feasible_qty = min(qty, avgVolume * 0.10)   # can't be >10% of daily volume
  slippage     = 0.1% + 0.5% * (qty / avgVolume)
  market_impact_pct via square-root model
  realistic prices = ideal +/- slippage+impact
  warning + illiquid_flag

Usage:
    from app.quant.execution import simulate_execution
    simulate_execution("RELIANCE", qty=1000, ideal_price=2500.0)
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import math
from typing import Any, Dict, Optional

import pandas as pd

from .data_collector import NSEDataCollector, _normalize_symbol

logger = logging.getLogger(__name__)

# Thresholds matching screener / product rules
ILLIQUID_AVG_VOL_THRESHOLD = 100_000  # 1 lakh shares
IMPACT_COST_ILLIQUID_PCT = 0.02  # 2%


@dataclasses.dataclass
class MarketMetrics:
    symbol: str
    avg_volume_20d: float
    last_close: Optional[float] = None
    delivery_pct: Optional[float] = None  # 0-100
    circuit_limit_pct: Optional[float] = None  # e.g. 5,10,20
    bid_ask_spread_pct: Optional[float] = None  # e.g. 0.05 = 5bps
    volatility_20d: Optional[float] = None  # stdev of returns
    data_points: int = 0


@dataclasses.dataclass
class ExecutionResult:
    symbol: str
    requested_qty: int
    ideal_price: float
    avg_volume_20d: float
    feasible_qty: int
    slippage_pct: float
    market_impact_pct: float
    total_cost_pct: float
    market_impact_cost: float  # in rupees (total_cost * feasible_qty * ideal_price)
    realistic_buy_price: float
    realistic_sell_price: float
    illiquid_flag: bool
    warning: Optional[str] = None
    metrics: Optional[MarketMetrics] = None

    def to_dict(self) -> Dict[str, Any]:
        try:
            return dataclasses.asdict(self)
        except Exception:
            # Fallback for mocked / non-dataclass metrics in tests
            d: Dict[str, Any] = {}
            for f in dataclasses.fields(self):
                v = getattr(self, f.name)
                if f.name == "metrics" and v is not None:
                    try:
                        v = dataclasses.asdict(v) if dataclasses.is_dataclass(v) else dict(v) if isinstance(v, dict) else str(v)
                    except Exception:
                        v = str(v)
                d[f.name] = v
            return d


class ExecutionSimulator:
    """
    Realistic execution simulator for NSE equities.
    Fetch path: yahooquery 20D history + nsepython quote for delivery/circuit.
    Falls back to heuristic estimates when live data unavailable (tests/offline).
    """

    def __init__(self, collector: Optional[NSEDataCollector] = None) -> None:
        self.collector = collector or NSEDataCollector()

    # -- market metrics --

    def get_market_metrics(self, symbol: str) -> MarketMetrics:
        raw, yahoo_sym = _normalize_symbol(symbol)
        df = self.collector.fetch_20d_history(symbol)
        avg_vol = 0.0
        last_close: Optional[float] = None
        vol_20d: Optional[float] = None

        if not df.empty:
            avg_vol = float(df["volume"].mean())
            last_close = float(df["close"].iloc[-1])
            # volatility as stdev of daily returns
            try:
                rets = df["close"].pct_change().dropna()
                vol_20d = float(rets.std()) if len(rets) > 1 else None
            except Exception:
                vol_20d = None

        delivery_pct: Optional[float] = None
        circuit_pct: Optional[float] = None
        spread_pct: Optional[float] = None

        # Try yahooquery for bid/ask and volume details
        try:
            from yahooquery import Ticker

            t = Ticker(yahoo_sym, asynchronous=False)
            # price dict contains regularMarketVolume, bid, ask etc
            price = {}
            try:
                price = t.price.get(yahoo_sym, {}) if isinstance(t.price, dict) else {}
            except Exception:
                price = {}
            # summary_detail for avg volume
            try:
                sd = t.summary_detail.get(yahoo_sym, {}) if isinstance(t.summary_detail, dict) else {}
                if sd and "averageVolume" in sd:
                    # yahoo's averageVolume is 3M avg; prefer our 20D but use as fallback
                    if avg_vol == 0:
                        avg_vol = float(sd["averageVolume"] or 0)
                if sd and "averageVolume10days" in sd and avg_vol == 0:
                    avg_vol = float(sd["averageVolume10days"] or 0)
            except Exception:
                pass
            # bid/ask spread
            try:
                bid = price.get("regularMarketBid") or price.get("bid")
                ask = price.get("regularMarketAsk") or price.get("ask")
                if bid and ask and last_close:
                    mid = (float(bid) + float(ask)) / 2
                    if mid > 0:
                        spread_pct = abs(float(ask) - float(bid)) / mid
                elif price.get("bid") and price.get("ask"):
                    mid = (float(price["bid"]) + float(price["ask"])) / 2
                    spread_pct = abs(float(price["ask"]) - float(price["bid"])) / mid if mid else None
            except Exception:
                pass
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("yahooquery metrics fallback for %s: %s", symbol, exc)

        # Try nsepython for delivery % and circuit limits
        try:
            from nsepython import nse_eq  # type: ignore

            quote = nse_eq(raw)  # type: ignore
            if quote:
                # deliveryPercentage is in securityWiseDP or priceInfo
                sec = quote.get("securityWiseDP", {}) if isinstance(quote, dict) else {}
                if sec and "deliveryQuantity" in sec and "quantityTraded" in sec:
                    try:
                        dq = float(sec["deliveryQuantity"] or 0)
                        qt = float(sec["quantityTraded"] or 0)
                        if qt > 0:
                            delivery_pct = dq / qt * 100
                    except Exception:
                        pass
                # also try direct field
                if delivery_pct is None:
                    for k in ("deliveryToTradedQuantity", "deliveryPercentage"):
                        if k in quote:
                            try:
                                delivery_pct = float(quote[k])
                                break
                            except Exception:
                                pass
                # circuit limits: priceInfo.upperCP / lowerCP or circuitFilters
                pi = quote.get("priceInfo", {}) if isinstance(quote, dict) else {}
                if pi:
                    up = pi.get("upperCP")
                    low = pi.get("lowerCP")
                    ltp = pi.get("lastPrice") or last_close
                    if up and ltp and low:
                        try:
                            # infer band ~ (upper - ltp)/ltp
                            circuit_pct = abs(float(up) - float(ltp)) / float(ltp) * 100
                        except Exception:
                            pass
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("nsepython metrics fallback for %s: %s", symbol, exc)

        # Heuristic fallbacks (so offline/tests still return plausible numbers)
        if spread_pct is None:
            # Estimate spread from volatility / liquidity
            if avg_vol and avg_vol > 1_000_000:
                spread_pct = 0.0005  # 5 bps liquid
            elif avg_vol and avg_vol > 100_000:
                spread_pct = 0.0015  # 15 bps
            else:
                spread_pct = 0.005  # 50 bps illiquid
        if circuit_pct is None:
            circuit_pct = 10.0  # most NSE stocks have 10% or 20% band
        if delivery_pct is None:
            delivery_pct = 40.0  # placeholder; real would be fetched

        return MarketMetrics(
            symbol=raw,
            avg_volume_20d=float(avg_vol) if avg_vol else 0.0,
            last_close=last_close,
            delivery_pct=delivery_pct,
            circuit_limit_pct=circuit_pct,
            bid_ask_spread_pct=spread_pct,
            volatility_20d=vol_20d,
            data_points=len(df) if not df.empty else 0,
        )

    # -- core simulation --

    def simulate(
        self,
        symbol: str,
        qty: int = 1000,
        ideal_price: Optional[float] = None,
        side: str = "buy",
    ) -> ExecutionResult:
        """
        Simulate realistic execution for `qty` shares at `ideal_price`.

        Formulas (per spec):
          feasible_qty = min(qty, avgVolume * 0.10)
          slippage     = 0.1% + 0.5% * (qty / avgVolume)
          market_impact_pct = 0.2% * sqrt(qty/avgVolume)  [square-root model]
          total_cost_pct = slippage + market_impact + 0.5*spread

        realistic_buy  = ideal * (1 + total_cost_pct)
        realistic_sell = ideal * (1 - total_cost_pct)

        Returns ExecutionResult with warning when not all shares executable.
        """
        if qty <= 0:
            raise ValueError("qty must be > 0")
        raw, _ = _normalize_symbol(symbol)
        metrics = self.get_market_metrics(symbol)
        avg_vol = metrics.avg_volume_20d

        # Edge: no volume data -> treat as highly illiquid
        if avg_vol <= 0:
            avg_vol = 1.0  # avoid div/0, but feasible will be tiny
            logger.warning("No volume data for %s, assuming illiquid", symbol)

        if ideal_price is None:
            if metrics.last_close is not None:
                ideal_price = metrics.last_close
            else:
                raise ValueError("ideal_price is required when no market price available")

        # 1. feasible qty: 10% ADV rule (common institutional constraint)
        feasible_qty = int(min(qty, math.floor(avg_vol * 0.10)))
        feasible_qty = max(feasible_qty, 0)

        # 2. participation rate
        participation = qty / avg_vol if avg_vol > 0 else 1.0
        participation_capped = min(participation, 5.0)  # cap to avoid absurd slippage

        # 3. slippage per spec: 0.1% + 0.5% * (qty/avgVolume)
        slippage_pct = 0.001 + 0.005 * participation_capped

        # 4. market impact (square-root model, Kyle / Almgren-Chriss simplified)
        # impact = eta * sqrt(participation) ; eta ~ 0.002 for NSE
        market_impact_pct = 0.002 * math.sqrt(participation_capped)
        # Add volatility adjustment: higher vol -> higher impact
        if metrics.volatility_20d:
            # vol ~ 1-2% daily; scale impact modestly
            vol_mult = 1 + min(metrics.volatility_20d * 10, 0.5)
            market_impact_pct *= vol_mult

        # 5. half-spread cost (crossing the spread)
        spread_cost_pct = (metrics.bid_ask_spread_pct or 0.001) * 0.5

        total_cost_pct = slippage_pct + market_impact_pct + spread_cost_pct

        # 6. realistic prices
        realistic_buy_price = ideal_price * (1 + total_cost_pct)
        realistic_sell_price = ideal_price * (1 - total_cost_pct)

        # Clamp to circuit limits if known
        if metrics.circuit_limit_pct and metrics.last_close:
            limit = metrics.circuit_limit_pct / 100.0
            up = metrics.last_close * (1 + limit)
            down = metrics.last_close * (1 - limit)
            realistic_buy_price = min(realistic_buy_price, up)
            realistic_sell_price = max(realistic_sell_price, down)

        # 7. rupee impact cost for feasible qty
        market_impact_cost = total_cost_pct * ideal_price * feasible_qty

        # 8. flags / warnings
        illiquid_flag = False
        warning: Optional[str] = None

        if metrics.avg_volume_20d < ILLIQUID_AVG_VOL_THRESHOLD:
            illiquid_flag = True
        if total_cost_pct > IMPACT_COST_ILLIQUID_PCT:
            illiquid_flag = True

        if feasible_qty < qty:
            pct_executable = (feasible_qty / qty * 100) if qty else 0
            move_pct = total_cost_pct * 100
            warning = (
                f"Only {feasible_qty} of {qty} executable at ~{ideal_price:.2f} "
                f"({pct_executable:.0f}% fill). Rest would move market ~{move_pct:.1f}% "
                f"(slippage {slippage_pct*100:.2f}% + impact {market_impact_pct*100:.2f}%"
                f" + spread {spread_cost_pct*100:.2f}%). "
                f"ADV 20D={avg_vol:,.0f}, feasible cap 10% ADV={avg_vol*0.10:,.0f}."
            )
            # stretch warning for extremely illiquid
            if feasible_qty == 0:
                warning = (
                    f"Zero shares feasible at this size — ADV 20D is {avg_vol:,.0f}. "
                    f"Requested {qty} is {participation*100:.0f}% of daily volume. "
                    f"Try qty <= {int(avg_vol*0.10)}."
                )
        elif illiquid_flag:
            warning = (
                f"Illiquid: ADV 20D {avg_vol:,.0f} (<1L) or cost {total_cost_pct*100:.2f}% (>2%). "
                f"Execution may be partial and price may gap beyond circuit {metrics.circuit_limit_pct}%."
            )

        return ExecutionResult(
            symbol=raw,
            requested_qty=qty,
            ideal_price=float(ideal_price),
            avg_volume_20d=float(metrics.avg_volume_20d),
            feasible_qty=feasible_qty,
            slippage_pct=float(slippage_pct),
            market_impact_pct=float(market_impact_pct),
            total_cost_pct=float(total_cost_pct),
            market_impact_cost=float(market_impact_cost),
            realistic_buy_price=float(realistic_buy_price),
            realistic_sell_price=float(realistic_sell_price),
            illiquid_flag=illiquid_flag,
            warning=warning,
            metrics=metrics,
        )


# Convenience function (matches spec description)

def simulate_execution(
    symbol: str,
    qty: int = 1000,
    ideal_price: Optional[float] = None,
    collector: Optional[NSEDataCollector] = None,
) -> Dict[str, Any]:
    """
    Functional wrapper returning dict with keys:
      ideal_price, realistic_buy_price, realistic_sell_price,
      feasible_qty, warning, illiquid_flag (+ extras)
    """
    sim = ExecutionSimulator(collector=collector)
    result = sim.simulate(symbol=symbol, qty=qty, ideal_price=ideal_price)
    d = result.to_dict()
    # Normalize metrics to dict if possible, else keep raw
    raw_metrics = d.get("metrics")
    if isinstance(raw_metrics, dict):
        metrics_val = raw_metrics
    elif raw_metrics is not None and dataclasses.is_dataclass(raw_metrics):
        metrics_val = dataclasses.asdict(raw_metrics)
    else:
        # mocked or string fallback — try dict conversion, else string
        try:
            metrics_val = dict(raw_metrics) if raw_metrics is not None else None  # type: ignore
        except Exception:
            metrics_val = str(raw_metrics) if raw_metrics is not None else None
            # if metrics is MagicMock, produce minimal dict for API consistency
            if raw_metrics is not None and hasattr(raw_metrics, "_mock_name"):
                metrics_val = {"mock": True, "repr": str(raw_metrics)}
    return {
        "symbol": d["symbol"],
        "requested_qty": d["requested_qty"],
        "ideal_price": d["ideal_price"],
        "realistic_buy_price": d["realistic_buy_price"],
        "realistic_sell_price": d["realistic_sell_price"],
        "feasible_qty": d["feasible_qty"],
        "avg_volume_20d": d["avg_volume_20d"],
        "slippage_pct": d["slippage_pct"],
        "market_impact_pct": d["market_impact_pct"],
        "total_cost_pct": d["total_cost_pct"],
        "market_impact_cost": d["market_impact_cost"],
        "illiquid_flag": d["illiquid_flag"],
        "warning": d["warning"],
        "metrics": metrics_val,
    }
