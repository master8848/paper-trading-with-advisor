# backend_py — FastAPI

FastAPI replacement for `backend/` (NestJS 9 + TypeORM). SQLite/libSQL `finance_app.db` by default (libsql-compatible, swappable to Postgres), same frontend contract, plus portfolio/positions/trades and Qlib quant.

## Setup

```bash
cd backend_py

# with uv (recommended)
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# with pip
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

SQLite needs no server — `alembic upgrade head` creates `finance_app.db`. For Postgres/MySQL set DATABASE_URL env (no hardcoded creds). `python -m py_compile` is sufficient for syntax checks without a DB.

### Tooling

```bash
cd backend_py
ruff check .            # lint
ruff format .           # format
ty check                # type check (ty)
pytest -q               # tests
pytest --cov=app tests/ # coverage
alembic revision --autogenerate -m "msg"  # new migration
alembic upgrade head && alembic current && alembic history
```

## Project Layout

```
backend_py/
  app/
    main.py                 # FastAPI app, CORS, router wiring
    database.py             # SQLAlchemy engine (finance_app)
    models.py               # SQLModel tables
    schemas.py              # pydantic v2 request/response
    enums.py                # TransactionType
    nse.py                  # NSE helper (yfinance/nsepython, TTL cache)
    utils/duration.py       # moment.startOf port (duration filter)
    routers/
      portfolios.py
      positions.py
      trades.py             # paper trade with LTP snapshot
      stocks.py             # legacy compat + duration + ?load enrichment
      stock_exchange.py     # cached /Nse + /:symbol LTP
    quant/
      router.py             # /quant/* endpoints
      qlib_service.py       # lazy pyqlib wrapper (Alpha158 + LGBM, fallback mock)
      data_collector.py     # yahooquery/nsepython OHLCV → qlib normalization
      execution.py          # realistic execution simulator
      screener.py           # liquidity / screener warnings
  alembic/
    env.py
    versions/
      001_initial_portfolios_positions_trades.py
      002_migrate_stocks_to_portfolios.py
  alembic.ini
  requirements.txt
```

## Endpoints

Base `http://localhost:8000`. Swagger at `/docs`, OpenAPI at `/openapi.json`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness |
| `GET` | `/` | Index with route map |
| `POST` | `/portfolios` | Create portfolio `{user_id, name, baseline_value?}` |
| `GET` | `/portfolios` | List portfolios |
| `GET` | `/portfolios/{id}` | Detail |
| `POST` | `/portfolios/{id}/baseline?baseline_value=&baseline_price=` | Update baseline; propagates `baseline_price` to positions lacking it |
| `GET` | `/portfolios/{id}/performance?normalized=true` | PnL per position; `pnl_normalized = pnl / baseline_value * 100`; current price via LTP fetch |
| `POST` | `/positions` | Create position `{portfolio_id, symbol, qty, avg_buy_price, baseline_price?}` |
| `GET` | `/positions?portfolio_id=` | List positions |
| `POST` | `/trades` | Paper trade `{symbol, qty, type: buy|sell, position_id?, price_snapshot?}` — snapshots LTP if `price_snapshot` omitted; stores `ltp/52W` |
| `GET` | `/trades?position_id=&symbol=` | List trades |
| `GET` | `/trades/{id}` | Detail |
| `GET` | `/stocks?duration=&load=` | Legacy compat — mirrors `StocksService.findAll()`. `duration` = `tweek|lweek|tmonth|lmonth|tyear|lyear`. `load=true` enriches with `lastTradedPrice/52W` (N LTP calls, errors swallowed) |
| `POST` | `/stocks` | Legacy create (also mirrors to portfolios/positions best-effort) |
| `PATCH` | `/stocks/{id}` | Legacy update |
| `DELETE` | `/stocks/{id}` | Legacy delete |
| `GET` | `/stock-exchange/Nse` | Cached (1h TTL) NSE symbol list — mirrors `CacheInterceptor` |
| `GET` | `/stock-exchange/{symbol}` | `{lastTradedPrice, fiftyTwoWeekLow, fiftyTwoWeekHigh}` |
| `POST` | `/quant/predict` | `{symbol, horizon: "5d"}` → `{score, expected_return, confidence, gated, model_used}` |
| `POST` | `/quant/backtest` | `{symbol, start: YYYY-MM-DD, end: YYYY-MM-DD}` → `{cumulative_return, sharpe, max_drawdown, trades}` |
| `GET` | `/quant/screen/{symbol}` | Liquidity gate `{passes, reason, mcap_cr, avg_volume_20d}` |
| `GET` | `/quant/warnings/{symbol}?qty=&ideal_price=` | Flags for mcap/vol/impact |
| `POST` | `/quant/execution/simulate` | `{symbol, qty, ideal_price?, side: buy|sell}` → `{feasible_qty, realistic_buy_price, realistic_sell_price, slippage, market_impact, warning}` |
| `GET` | `/quant/health` | `{qlib_available, provider_uri, initialized}` |

## Qlib Usage

- Lazy import — `import pyqlib` only inside `QlibService.ensure_initialized()` / `_load_model()` (`app/quant/qlib_service.py`). If `pyqlib` is missing the router still mounts and returns fallback predictions.
- `provider_uri` defaults to `backend_py/qlib_data` (`QLIB_PROVIDER_URI` env overrides). `ensure_initialized()` calls `qlib.init(provider_uri, region="in")` once and seeds `calendars/day.txt` with the last 30 trading days if absent.
- Pipeline when data is present: `Alpha158` handler + `DatasetH` + `LGBModel` (`app/quant/qlib_service.py:128`). Pretrained weights at `qlib_data/models/lgb_alpha158.pkl` are loaded if present; otherwise an unfit `LGBModel` is kept and fallback is used.
- `predict` is **gated** by liquidity: `Screener.liquidity_check()` must pass (mcap ≥ 500 Cr, ADV 20D ≥ 1 L); if gated the response is `{score:0, expected_return:0, confidence:0.05, gated:true}`.
- Fallback when qlib/model/data unavailable: deterministic `sha256(symbol:horizon) → score in [-1,1]` plus 5-day momentum adjustment via `NSEDataCollector`; `expected_return = score * 0.02 * (horizon_days/5)`, confidence `0.35 + |score|*0.3` (`qlib_service.py:272`).
- Data ingest: `NSEDataCollector` (`app/quant/data_collector.py`) fetches OHLCV via `yahooquery` (primary) then `nsepython`, normalizes to qlib columns `open/high/low/close/volume/factor` with `DatetimeIndex` named `datetime`, and can persist to `provider_uri/csv/day/<SYMBOL>.csv` + calendar (`data_collector.py:345`).

## Execution Realism

Simulator `app/quant/execution.py:225` — answers "what could you actually buy/sell at price X".

```
feasible_qty = min(qty, floor(avgVolume_20D * 0.10))   # 10% ADV cap
participation = qty / avgVolume_20D   (capped at 5.0)
slippage_pct  = 0.1% + 0.5% * participation
              = 0.001 + 0.005 * participation_capped
market_impact_pct = 0.2% * sqrt(participation_capped)  # square-root / Kyle
                    × (1 + min(vol_20D*10, 0.5))       # vol adjustment
                    # vol_20D = stdev of daily returns
half_spread = 0.5 * bid_ask_spread_pct                 # 5 bps liquid, 15 bps mid, 50 bps illiquid (heuristic)
total_cost_pct = slippage_pct + market_impact_pct + half_spread
realistic_buy  = ideal * (1 + total_cost_pct)
realistic_sell = ideal * (1 - total_cost_pct)
# clamped to circuit band if known: last_close * (1 ± circuit_limit_pct)
market_impact_cost = total_cost_pct * ideal_price * feasible_qty
```

`MarketMetrics` are fetched from `yahooquery` (bid/ask, avg volume) + `nsepython` (delivery %, circuit `upperCP/lowerCP`) + 20D history (`execution.py:95`). Missing fields use heuristics. `illiquid_flag` is set if `avgVolume_20D < 1L` or `total_cost_pct > 2%`; a `warning` string is returned when `feasible_qty < qty` or illiquid (`execution.py:304`).

## Screener Thresholds

`app/quant/screener.py:24`:

| Flag | Threshold | Code |
|------|-----------|------|
| Market cap | `< 500 Cr` (`500 * 1e7 = 5e9 INR`) | `LOW_MCAP` (critical if < 100 Cr else warn) |
| ADV 20D | `< 1 L` (`100,000 shares`) | `LOW_VOLUME` (critical if < 10k) |
| Impact cost | `> 2%` (`total_cost_pct` from simulator) | `HIGH_IMPACT` |
| Delivery % | `< 20%` (bonus) | `LOW_DELIVERY` |

`mcap` is fetched via `yahooquery` (`marketCap` or `sharesOutstanding * regularMarketPrice`) then `nsepython` (`metadata.marketCap` or `priceInfo.lastPrice * securityInfo.issuedSize`) (`screener.py:50`). Unknown mcap emits `MCAP_UNKNOWN` (info) and does not block; `illiquid = LOW_MCAP || LOW_VOLUME || HIGH_IMPACT`.

## Duration Filter

Port of `backend/src/stocks/stocks.service.ts:29` (`moment.startOf`, week = Sunday) in `app/utils/duration.py`:

- `tweek` → `modified > startOf(week)` (Sunday 00:00)
- `lweek` → `modified BETWEEN startOf(week-1) AND startOf(week)`
- `tmonth` → `modified > startOf(month)`
- `lmonth` → `modified BETWEEN startOf(month-1) AND startOf(month)`
- `tyear` → `modified > startOf(year)`
- `lyear` → `modified BETWEEN startOf(year-1) AND startOf(year)`
- default → no filter

## Notes

- `GET /stock-exchange/Nse` is cached 1h in `app/nse.py:42` (mirrors NestJS `CacheInterceptor`).
- NSE APIs are flaky/rate-limited; LTP may be `null` — callers handle gracefully. `find_all({load:true})` swallows per-row errors like the original.
- CORS is `allow_origins=["*"]` (`app/main.py:36`).
