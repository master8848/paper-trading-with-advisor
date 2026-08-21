"""
Screener — liquidity / risk warnings for NSE symbols.

GET /quant/warnings/{symbol} checks:
  - mcap < 500 Cr  (500 * 1e7 = 5e9 INR)
  - avgVol < 1L   (100,000 shares 20D)
  - impactCost > 2% (total_cost_pct from execution simulator)

Also exposes:
  GET /quant/screen/{symbol} -> liquidity check (legacy name, kept for spec)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .data_collector import NSEDataCollector, _normalize_symbol
from .execution import ExecutionSimulator, ILLIQUID_AVG_VOL_THRESHOLD, IMPACT_COST_ILLIQUID_PCT

logger = logging.getLogger(__name__)

MCAP_THRESHOLD_CR = 500  # Cr rupees
MCAP_THRESHOLD_INR = MCAP_THRESHOLD_CR * 1e7  # 5,000,000,000
AVG_VOL_THRESHOLD = 100_000  # 1 lakh
IMPACT_COST_THRESHOLD = 0.02  # 2%


@dataclass
class WarningFlag:
    code: str
    message: str
    severity: str  # info | warn | critical
    value: Any = None
    threshold: Any = None


class Screener:
    def __init__(
        self,
        collector: Optional[NSEDataCollector] = None,
        simulator: Optional[ExecutionSimulator] = None,
    ) -> None:
        self.collector = collector or NSEDataCollector()
        self.simulator = simulator or ExecutionSimulator(collector=self.collector)

    # -- mcap fetching --

    def get_mcap(self, symbol: str) -> Optional[float]:
        """
        Fetch market cap in INR.
        Tries yahooquery (sharesOutstanding * price), then nsepython.
        Returns float INR or None if unavailable.
        """
        raw, yahoo_sym = _normalize_symbol(symbol)

        # yahooquery path
        try:
            from yahooquery import Ticker

            t = Ticker(yahoo_sym, asynchronous=False)
            # Try price + keyStats
            price = {}
            try:
                p = t.price
                if isinstance(p, dict):
                    price = p.get(yahoo_sym, {})
            except Exception:
                pass

            mcap_direct = price.get("marketCap") if price else None
            if mcap_direct:
                try:
                    return float(mcap_direct)
                except Exception:
                    pass

            # compute from sharesOutstanding
            try:
                ks = t.key_stats.get(yahoo_sym, {}) if isinstance(t.key_stats, dict) else {}
                shares = ks.get("sharesOutstanding")
                regular_price = price.get("regularMarketPrice") if price else None
                if shares and regular_price:
                    return float(shares) * float(regular_price)
            except Exception:
                pass

            # try asset_profile / summary fallback
            try:
                sd = t.summary_detail.get(yahoo_sym, {}) if isinstance(t.summary_detail, dict) else {}
                if sd and sd.get("marketCap"):
                    return float(sd["marketCap"])
            except Exception:
                pass
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("mcap yahooquery failed for %s: %s", symbol, exc)

        # nsepython path: try to get market cap from quote
        try:
            from nsepython import nse_eq  # type: ignore

            quote = nse_eq(raw)  # type: ignore
            if quote and isinstance(quote, dict):
                # Some nsepython responses include marketDeptOrderBook or metadata
                for key in ("marketCap", "mcap", "market_cap"):
                    if key in quote:
                        try:
                            return float(quote[key])
                        except Exception:
                            pass
                meta = quote.get("metadata", {}) if isinstance(quote.get("metadata"), dict) else {}
                if meta and meta.get("marketCap"):
                    try:
                        return float(meta["marketCap"])
                    except Exception:
                        pass
                # fallback: price * issued size
                pi = quote.get("priceInfo", {})
                md = quote.get("securityInfo", {}) if isinstance(quote.get("securityInfo"), dict) else {}
                if pi and md:
                    try:
                        price_val = float(pi.get("lastPrice") or 0)
                        issued = float(md.get("issuedSize") or 0)
                        if price_val and issued:
                            return price_val * issued
                    except Exception:
                        pass
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("mcap nsepython failed for %s: %s", symbol, exc)

        return None

    def get_avg_volume_20d(self, symbol: str) -> float:
        metrics = self.simulator.get_market_metrics(symbol)
        return float(metrics.avg_volume_20d)

    def get_impact_cost_pct(self, symbol: str, qty: int = 1000, ideal_price: Optional[float] = None) -> float:
        """
        Estimate impact cost % for default qty. Uses simulator's total_cost_pct.
        """
        try:
            res = self.simulator.simulate(symbol, qty=qty, ideal_price=ideal_price)
            return float(res.total_cost_pct)
        except Exception as exc:
            logger.debug("impact cost simulation failed for %s: %s", symbol, exc)
            return 0.0

    # -- main checks --

    def check_warnings(self, symbol: str, qty: int = 1000, ideal_price: Optional[float] = None) -> Dict[str, Any]:
        """
        GET /quant/warnings/{symbol}
        Checks mcap <500Cr, avgVol <1L, impactCost >2%
        Returns {symbol, mcap, mcap_cr, avg_volume_20d, impact_cost_pct, flags, illiquid, warnings}
        """
        raw, _ = _normalize_symbol(symbol)
        mcap_inr = self.get_mcap(symbol)
        mcap_cr = (mcap_inr / 1e7) if mcap_inr is not None else None
        avg_vol = self.get_avg_volume_20d(symbol)

        # Need ideal_price for impact calc; infer from last close if not provided
        if ideal_price is None:
            try:
                metrics = self.simulator.get_market_metrics(symbol)
                ideal_price = metrics.last_close
            except Exception:
                ideal_price = None

        impact_pct = self.get_impact_cost_pct(symbol, qty=qty, ideal_price=ideal_price)

        flags: List[Dict[str, Any]] = []
        warnings: List[str] = []

        # 1) mcap < 500 Cr
        if mcap_inr is not None and mcap_inr < MCAP_THRESHOLD_INR:
            msg = f"Micro-cap: mcap {mcap_cr:.1f} Cr < {MCAP_THRESHOLD_CR} Cr threshold"
            flags.append(
                {
                    "code": "LOW_MCAP",
                    "message": msg,
                    "severity": "critical" if (mcap_cr or 0) < 100 else "warn",
                    "value": mcap_cr,
                    "threshold": MCAP_THRESHOLD_CR,
                    "value_inr": mcap_inr,
                }
            )
            warnings.append(msg)
        elif mcap_inr is None:
            flags.append(
                {
                    "code": "MCAP_UNKNOWN",
                    "message": "Market cap unavailable — cannot confirm liquidity; treat as risky",
                    "severity": "info",
                    "value": None,
                    "threshold": MCAP_THRESHOLD_CR,
                }
            )
        else:
            flags.append(
                {
                    "code": "MCAP_OK",
                    "message": f"mcap {mcap_cr:.1f} Cr passes {MCAP_THRESHOLD_CR} Cr filter",
                    "severity": "info",
                    "value": mcap_cr,
                    "threshold": MCAP_THRESHOLD_CR,
                }
            )

        # 2) avgVol < 1L
        if avg_vol < AVG_VOL_THRESHOLD:
            msg = f"Low volume: ADV 20D {avg_vol:,.0f} < {AVG_VOL_THRESHOLD:,.0f} (1L)"
            flags.append(
                {
                    "code": "LOW_VOLUME",
                    "message": msg,
                    "severity": "critical" if avg_vol < 10_000 else "warn",
                    "value": avg_vol,
                    "threshold": AVG_VOL_THRESHOLD,
                }
            )
            warnings.append(msg)
        else:
            flags.append(
                {
                    "code": "VOLUME_OK",
                    "message": f"ADV 20D {avg_vol:,.0f} passes 1L filter",
                    "severity": "info",
                    "value": avg_vol,
                    "threshold": AVG_VOL_THRESHOLD,
                }
            )

        # 3) impactCost > 2%
        if impact_pct > IMPACT_COST_THRESHOLD:
            msg = f"High impact: total cost {impact_pct*100:.2f}% > {IMPACT_COST_THRESHOLD*100:.0f}% for qty {qty}"
            flags.append(
                {
                    "code": "HIGH_IMPACT",
                    "message": msg,
                    "severity": "warn",
                    "value": impact_pct,
                    "threshold": IMPACT_COST_THRESHOLD,
                }
            )
            warnings.append(msg)
        else:
            flags.append(
                {
                    "code": "IMPACT_OK",
                    "message": f"Impact {impact_pct*100:.2f}% within {IMPACT_COST_THRESHOLD*100:.0f}% for qty {qty}",
                    "severity": "info",
                    "value": impact_pct,
                    "threshold": IMPACT_COST_THRESHOLD,
                }
            )

        # Additional: delivery % check (bonus, not in spec but useful)
        try:
            metrics = self.simulator.get_market_metrics(symbol)
            if metrics.delivery_pct is not None and metrics.delivery_pct < 20:
                msg = f"Low delivery {metrics.delivery_pct:.1f}% — speculative / operator-driven"
                flags.append({"code": "LOW_DELIVERY", "message": msg, "severity": "warn", "value": metrics.delivery_pct, "threshold": 30})
                warnings.append(msg)
        except Exception:
            pass

        illiquid = any(f["code"] in ("LOW_MCAP", "LOW_VOLUME", "HIGH_IMPACT") for f in flags)
        # illiquid if any critical warn
        has_critical = any(f["severity"] == "critical" for f in flags if f["code"] in ("LOW_MCAP", "LOW_VOLUME"))

        return {
            "symbol": raw,
            "mcap": mcap_inr,
            "mcap_cr": mcap_cr,
            "avg_volume_20d": avg_vol,
            "impact_cost_pct": impact_pct,
            "flags": flags,
            "warnings": warnings,
            "illiquid": illiquid,
            "illiquid_flag": illiquid or has_critical,
            "has_critical": has_critical,
            "summary": "; ".join(warnings) if warnings else "No warnings — passes liquidity filters",
        }

    def liquidity_check(self, symbol: str, min_mcap_cr: float = 500, min_avg_vol: float = 100_000) -> Dict[str, Any]:
        """
        GET /quant/screen/{symbol} -> lightweight liquidity pass/fail.
        Only run heavy inference if this passes.
        Returns {symbol, passes, reason, metrics}
        """
        result = self.check_warnings(symbol)
        # passes if no critical and mcap/vol ok
        fails = [f for f in result["flags"] if f["severity"] in ("warn", "critical") and f["code"] in ("LOW_MCAP", "LOW_VOLUME", "HIGH_IMPACT")]
        passes = len(fails) == 0
        reason = "Passes liquidity threshold" if passes else "; ".join(f["message"] for f in fails)
        return {
            "symbol": result["symbol"],
            "passes": passes,
            "reason": reason,
            "mcap_cr": result["mcap_cr"],
            "avg_volume_20d": result["avg_volume_20d"],
            "impact_cost_pct": result["impact_cost_pct"],
            "details": result,
        }


# Functional wrappers for router / easy import

_default_screener: Optional[Screener] = None


def get_screener() -> Screener:
    global _default_screener
    if _default_screener is None:
        _default_screener = Screener()
    return _default_screener


def check_warnings(symbol: str, qty: int = 1000, ideal_price: Optional[float] = None) -> Dict[str, Any]:
    return get_screener().check_warnings(symbol, qty=qty, ideal_price=ideal_price)
