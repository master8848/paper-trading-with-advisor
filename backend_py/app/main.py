"""
FastAPI entry — mirrors NestJS AppModule + StockExchangeModule + StocksModule.

Run:
  uvicorn app.main:app --reload --port 3000

CORS enabled, pydantic validation, portfolio/position/trade + legacy stocks routes.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import portfolios, positions, stock_exchange, stocks, trades

# Quant module — Qlib + execution realism (Microsoft Qlib integration)
try:
    from app.quant.router import router as quant_router
except Exception:  # pragma: no cover — quant is optional if deps missing
    quant_router = None  # type: ignore

app = FastAPI(
    title="NSE Finance API",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    description=(
        "Python FastAPI replacement for NestJS 9 backend. "
        "Keeps MySQL finance_app (localhost:3306) and frontend compatibility "
        "GET /stocks?duration=... and GET /stock-exchange/Nse. "
        "New domain: portfolios / positions / trades / price_snapshots."
    ),
)

# CORS enabled — mirrors NestJS enableCors()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(portfolios.router)
app.include_router(positions.router)
app.include_router(trades.router)
app.include_router(stocks.router)
app.include_router(stock_exchange.router)
if quant_router is not None:
    app.include_router(quant_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "name": "NSE Finance API",
        "docs": "/docs",
        "health": "/health",
        "legacy": {
            "stocks": "/stocks?duration=tweek|lweek|tmonth|lmonth|tyear|lyear&load=true",
            "nse_symbols": "/stock-exchange/Nse",
            "nse_ltp": "/stock-exchange/{symbol}",
        },
        "portfolios": {
            "create": "POST /portfolios",
            "performance": "GET /portfolios/{id}/performance?normalized=true",
            "baseline": "POST /portfolios/{id}/baseline",
            "positions": "POST /positions",
            "trades": "POST /trades",
        },
    }
