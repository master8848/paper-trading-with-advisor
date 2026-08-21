# Architecture

## Data Flow

```
User (browser)
  │  Vite :5173  src/lib/api.ts (fetch, VITE_API_URL)
  ▼
FastAPI :8000  app/main.py
  ├─ /stocks, /stock-exchange/*  ──►  app/nse.py  ──► yfinance / yahooquery / nsepython ──► NSE / Yahoo
  ├─ /portfolios, /positions, /trades  ──►  SQLModel  ──►  SQLite finance_app.db (libsql)
  └─ /quant/*  ──►  QlibService + Screener + ExecutionSimulator
                    │           │              │
                    │           │              └─ 20D history, spread, circuit, delivery
                    │           └─ mcap / ADV / impact flags
                    └─ Alpha158 → DatasetH → LGBModel  (or fallback hash+momentum)
                         ▲
                         │  provider_uri = backend_py/qlib_data
                         │  (calendars/day.txt, csv/day/*.csv, models/*.pkl)
```

- Frontend uses `@tanstack/react-query` with `staleTime: Infinity`; mutations invalidate `queryKey` to refetch.
- Legacy `GET /stocks?duration=&load=true` still works: `duration` filters by `modified`, `load=true` enriches each row with LTP/52W via `find_equity_historical_data` (N calls, errors swallowed).
- `GET /stock-exchange/Nse` is cached 1h in `app/nse.py`.
- HeyAPI codegen: `http://localhost:8000/openapi.json` → `frontend/src/api/generated` (`@hey-api/openapi-ts` fetch client).

## DB Schema

SQLite `finance_app.db` (libsql-compatible; swappable to Postgres via DATABASE_URL). Managed by Alembic (`backend_py/alembic/`). `Stocks` table is retained for compat.

```sql
-- legacy (TypeORM Stocks entity) — kept verbatim
Stocks (
  id PK,
  username       VARCHAR(255),
  message        VARCHAR(1024) NULL,
  price          VARCHAR(64),          -- string in legacy
  stockName      VARCHAR(64),
  date           DATETIME,             -- stored as VARCHAR(64) in model, DATETIME in MySQL
  modified       DATETIME,
  transactionType ENUM('buy','sell'),
  quantity       VARCHAR(64),
  total          VARCHAR(64)
)

portfolios (
  id PK,
  user_id        VARCHAR(255) INDEX,   -- migrated from Stocks.username
  name           VARCHAR(255),
  baseline_value DECIMAL(20,4) DEFAULT 100,
  created_at     DATETIME DEFAULT now()
)

positions (
  id PK,
  portfolio_id   FK → portfolios.id INDEX,
  symbol         VARCHAR(64) INDEX,    -- migrated from Stocks.stockName
  qty            DECIMAL(20,4),        -- migrated from Stocks.quantity
  avg_buy_price  DECIMAL(20,4),        -- migrated from Stocks.price
  baseline_price DECIMAL(20,4) NULL,
  created_at     DATETIME DEFAULT now()
)

trades (
  id PK,
  position_id    FK → positions.id NULL INDEX,
  symbol         VARCHAR(64) INDEX,
  price_snapshot DECIMAL(20,4),        -- price at trade time (LTP snapshot or explicit)
  qty            DECIMAL(20,4),
  type           ENUM('buy','sell'),
  traded_at      DATETIME DEFAULT now(),
  ltp            DECIMAL(20,4) NULL,   -- snapshot enrichment
  fiftyTwoWeekLow  DECIMAL(20,4) NULL,
  fiftyTwoWeekHigh DECIMAL(20,4) NULL
)

price_snapshots (
  id PK,
  symbol         VARCHAR(64) INDEX,
  date           DATE INDEX,
  open,high,low,close  DECIMAL(20,4),
  volume         BIGINT,
  delivery_volume BIGINT NULL,
  market_cap     DECIMAL(20,4) NULL,
  -- unique constraint on (symbol, date) via Alembic
  COMMENT 'Daily OHLCV snapshots per symbol'
)
```

Migrations:

- `001_initial_portfolios_positions_trades.py` — creates new tables.
- `002_migrate_stocks_to_portfolios.py` — copies `Stocks` rows into `portfolios`/`positions` idempotently; does not drop `Stocks`.

See `backend_py/app/models.py` for SQLModel definitions and `backend_py/app/schemas.py` for pydantic schemas.

## Qlib Pipeline

`backend_py/app/quant/qlib_service.py` — lazy, import-deferred.

```
provider_uri (backend_py/qlib_data)
  ├─ calendars/day.txt        # trading days, seeded with last 30 if missing
  ├─ csv/day/<SYMBOL>.csv     # OHLCV from NSEDataCollector (datetime,open,high,low,close,volume,factor)
  └─ models/lgb_alpha158.pkl  # optional pretrained LGBModel

ensure_initialized()
  └─ qlib.init(provider_uri, region="in")   # once, thread-safe

_load_model()
  ├─ Alpha158(start_time, end_time, instruments="all")
  ├─ DatasetH(handler=Alpha158, segments={train, valid, test})
  └─ LGBModel(loss=mse, colsample_bytree=0.8879, lr=0.05, …)  # hyperparams in qlib_service.py:149
     └─ if models/lgb_alpha158.pkl exists → pickle.load, else keep unfit

predict(symbol, horizon="5d")
  ├─ 1) liquidity gate: Screener.liquidity_check(symbol)
  │     └─ if fails → return {score:0, expected_return:0, confidence:0.05, gated:true}
  ├─ 2) if qlib + model available:
  │     └─ D.features([symbol], fields=[$close,$volume,$high,$low]) → model.predict(df) → score in [-1,1]
  └─ 3) fallback: sha256(symbol:horizon) → [-1,1] *0.7 + 5d momentum *0.3
              expected_return = score * 0.02 * (horizon_days/5)
              confidence = 0.35 + |score|*0.3
              model_used = "fallback_momentum_hash"

backtest(symbol, start, end)
  └─ fallback MA5 momentum: signal = close > MA5(5) (shifted 1), strat_ret = signal*ret
     → cumulative_return, buy_hold_return, sharpe (annualized 252), max_drawdown, win_rate, trades[]

Data ingest: NSEDataCollector (app/quant/data_collector.py)
  fetch: yahooquery (primary) → nsepython (fallback)
  normalize_to_qlib(): lowercase cols, DatetimeIndex named "datetime",
                       map adjclose/qty aliases, ensure open/high/low/close/volume/factor, coerce numeric, sort
  save_to_qlib_bin(): write csv/day/<SYMBOL>.csv + update calendars/day.txt
  helpers: fetch_20d_history() (last 20 rows), get_trading_window(days=4), is_trading_day() (weekends + hardcoded NSE holidays 2024-2027)
```

If `pyqlib` is not installed, `_check_qlib_available()` returns false and all quant endpoints return fallback results without error.

## Liquidity Gate

`backend_py/app/quant/screener.py` + `app/quant/execution.py`. Heavy inference only runs if the symbol passes.

| Check | Threshold | Flag | Severity |
|-------|-----------|------|----------|
| Market cap | `< 500 Cr` (`5e9 INR`) | `LOW_MCAP` | critical if < 100 Cr else warn |
| ADV 20D | `< 1 L` (`100,000`) | `LOW_VOLUME` | critical if < 10k else warn |
| Impact cost | `> 2%` (`total_cost_pct`) | `HIGH_IMPACT` | warn |
| Delivery % | `< 20%` | `LOW_DELIVERY` | warn |

`Screener.get_mcap()` tries `yahooquery` (`marketCap` or `sharesOutstanding*price`) then `nsepython` (`metadata.marketCap` or `priceInfo.lastPrice * securityInfo.issuedSize`). `get_avg_volume_20d()` and `get_impact_cost_pct()` delegate to `ExecutionSimulator`.

- `GET /quant/screen/{symbol}` → `{passes, reason, mcap_cr, avg_volume_20d, impact_cost_pct, details}` — use this to decide whether to call `/quant/predict`.
- `GET /quant/warnings/{symbol}?qty=&ideal_price=` → `{mcap, mcap_cr, avg_volume_20d, impact_cost_pct, flags, warnings, illiquid}`.

## Baseline Normalization

Each `Portfolio` has `baseline_value` (default `100`). Each `Position` may have `baseline_price`.

```
pnl = (current_price - avg_buy_price) * qty
pnl_normalized = (pnl / baseline_value) * 100          # when normalized=true
norm_price     = 100 * (price / baseline_price)        # per-position normalized price (display)
```

Computed in `GET /portfolios/{id}/performance?normalized=true` (`backend_py/app/routers/portfolios.py:72`). `current_price` is fetched live via `find_last_traded_price(symbol)` per position; if LTP is unavailable `current_price` and `pnl` are `null`. `POST /portfolios/{id}/baseline?baseline_value=&baseline_price=` updates the portfolio baseline and backfills `baseline_price` for positions where it is null.

## Execution Realism

`backend_py/app/quant/execution.py:225` — `POST /quant/execution/simulate`.

```
avgVolume_20D, last_close, volatility_20D from 20D history
bid_ask_spread_pct, circuit_limit_pct, delivery_pct from yahooquery/nsepython (heuristics if missing)

feasible_qty = min(qty, floor(avgVolume_20D * 0.10))   # 10% ADV institutional cap
participation = qty / avgVolume_20D  (capped at 5.0)
slippage_pct  = 0.001 + 0.005 * participation           # 0.1% + 0.5%*participation
market_impact_pct = 0.002 * sqrt(participation) × vol_mult
                    vol_mult = 1 + min(vol_20D*10, 0.5)
half_spread   = 0.5 * bid_ask_spread_pct
total_cost_pct = slippage_pct + market_impact_pct + half_spread
realistic_buy  = ideal_price * (1 + total_cost_pct)
realistic_sell = ideal_price * (1 - total_cost_pct)
# clamped to circuit: last_close * (1 ± circuit_limit_pct)
market_impact_cost = total_cost_pct * ideal_price * feasible_qty
illiquid_flag = (avgVolume_20D < 1L) OR (total_cost_pct > 2%)
```

Returns `ExecutionResult` with `warning` when `feasible_qty < qty` or illiquid. Frontend shows this in `PaperTradeForm.tsx` as the "Realistic Execution Preview" before submit.

## External Links

Stock rows link out (no API, plain `https://`):

- Screener.in: `https://www.screener.in/company/{SYMBOL}/`
- NSE India: `https://www.nseindia.com/get-quotes/equity?symbol={SYMBOL}`
- BSE India: `https://www.bseindia.com/stock-share-price/{slug}/{SYMBOL}/`
- TradingView: `https://www.tradingview.com/symbols/NSE-{SYMBOL}/`
