# Paper Trading with Advisor

> **Try before you buy. For real NSE stocks.**

Pick any NSE stock, say you bought 100 shares at today's price (paper trade — no real money), track what would have happened, and get an AI hint if the stock looks interesting — or a warning if it's too illiquid to actually trade. Compare multiple stocks from the same starting line (baseline 100) like mutual funds do.

**For:** retail investors learning NSE, paper traders who want realistic "what-if" history.

### How it works (simple)
1. Search a stock (e.g. RELIANCE), click **Paper Buy** at current price.
2. See realistic buy/sell: *ideal 300 → realistic 302 (slippage) | only 200 of 1000 doable (low volume)* — so you know what was actually tradable.
3. Track profit — switch baseline to 100 to compare RELIANCE vs TCS from the same start.
4. Get prediction hint (`score`, `expected return`) — blocked with a warning if market-cap/volume is too small.
5. Jump to fundamentals: **Screener.in / NSE / BSE / TradingView** links on every stock page.

*Technical detail below — you can skip if you just want to use it.*

---

# NSE Finance — Paper Trading + Qlib Prediction

Paper trading for NSE equities with realistic execution, Qlib-powered predictions, and baseline-normalized performance. FastAPI + SQLModel (`backend/`).

## Overview

- **Paper trading** — create portfolios, positions, trades; LTP snapshotted at trade time via `yfinance` / `nsepython` (port of `stock-nse-india`). Enriches with 52-week low/high.
- **Qlib prediction** — `POST /quant/predict` returns `score` in [-1,1], `expected_return`, `confidence` in [0,1]. Alpha158 features + LGBModel when `pyqlib` data is loaded; deterministic hash+momentum fallback otherwise.
- **Baseline normalization** — each portfolio has `baseline_value` (default 100). Performance endpoint returns `pnl_normalized = pnl / baseline_value * 100`. Formula: `norm = 100 * (price / baseline)`.
- **Execution realism** — `POST /quant/execution/simulate` answers "what could you actually buy/sell" given ADV, spread, and market impact. See `docs/ARCHITECTURE.md`.
- **Screener / liquidity gate** — mcap < 500 Cr, ADV 20D < 1 L, impact > 2% are flagged. Heavy inference is gated behind the liquidity check.

## Architecture

```
                External
                ┌───────────────────────────────────────────┐
                │ Screener.in  NSE India  BSE  TradingView  │
                │ (mcap/vol)   (quote)   (alt) (chart)      │
                └──────────────┬────────────────────────────┘
                               │  yahooquery / nsepython / yfinance
                               ▼
React (Vite :5173) ──fetch──► FastAPI :8000 ──► Qlib Service (Alpha158 → LGBM)
  │  src/lib/api.ts              │  app/main.py        │  app/quant/qlib_service.py
  │  @tanstack/query             │  app/routers/*      │  provider_uri=./qlib_data
  │  @tanstack/table  @tanstack/form                ▼
  │                                   SQLite/libSQL finance_app.db (Turso) — swappable to Postgres
  │                                   portfolios / positions / trades / price_snapshots
  │                                   + legacy Stocks (compat)
  └─ HeyAPI codegen ◄── /openapi.json ─┘
     @hey-api/openapi-ts  (https://heyapi.dev)
```

- React talks to FastAPI on `:8000` via `fetch` (`src/lib/api.ts`, `VITE_API_URL`).
- FastAPI serves `GET /stocks?duration=…&load=true` and `GET /stock-exchange/Nse` for backward compat with existing `Home.tsx` / `Table.tsx`.
- Qlib Service is lazy-initialized; if `pyqlib` or provider data is missing it falls back to mock predictions (no crash).
- Legacy NestJS app in `backend/` is kept until parity is verified, then delete.

## Tech Stack

| Layer | Stack |
|-------|-------|
| API | FastAPI 0.110 + SQLModel 0.0.16 (SQLAlchemy 2.0) + Alembic 1.13 + pydantic v2 |
| Quant | pyqlib 0.9.6 + lightgbm 4.3.0 + pandas 2.1 + numpy 1.26 · `yahooquery` / `nsepython` / `yfinance` for NSE data |
| DB | SQLite/libSQL `finance_app.db` (Turso libSQL, swappable to Postgres via DATABASE_URL) |
| Frontend | Vite 4 + React 18 + Tailwind 3 + shadcn / Base UI + `@tabler/icons-react` |
| Frontend data | `@tanstack/react-table` 8 (v9 API in `PaperTradeTable.tsx`), `@tanstack/react-form` 1.x, `@tanstack/react-query` 4, `fetch` only (no axios) |
| Codegen | `@hey-api/openapi-ts` from `http://localhost:8000/openapi.json` → `src/api/generated` |

## Setup

Prereqs: Python 3.12+, Node 18+, SQLite/libSQL (no server) — DB file `finance_app.db` created on first run (libSQL-compatible, Turso). For Postgres: `DATABASE_URL=postgresql+psycopg://...` For self-hosted Turso: `DATABASE_URL=sqlite+libsql://127.0.0.1:8080/finance_app.db` (see `docker-compose.libsql.yml`).

### Backend (`backend`)

```bash
cd backend

# install (prefer uv; pip fallback)
uv sync
# or
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# DB migrations (creates portfolios/positions/trades/price_snapshots, keeps Stocks)
alembic upgrade head
alembic current   # verify
alembic history   # list

# run
uvicorn app.main:app --reload --port 8000
# docs at http://localhost:8000/docs  (OpenAPI at /openapi.json)
# health at http://localhost:8000/health
```

DB is SQLite/libSQL `finance_app.db` by default (libsql-compatible). Swappable to Postgres/MySQL via DATABASE_URL env (see backend/app/database.py, alembic.ini). No creds required.

Optional tooling:

```bash
cd backend
ruff check . && ruff format .
ty check
pytest -q
```

### Frontend

```bash
cd frontend
pnpm install          # or npm install
npm run gen:api       # pulls http://localhost:8000/openapi.json -> src/api/generated (requires backend running)
npm run dev           # Vite on http://localhost:5173
npm run build         # production build -> dist/
```

Env var (optional, defaults to `http://localhost:8000` in `src/lib/api.ts`):

```bash
# frontend/.env.local
VITE_API_URL=http://localhost:8000
```

> If you changed the backend port from `:3000` (NestJS) to `:8000` (FastAPI), update `VITE_API_URL` and `src/lib/api.ts` base. Legacy components still referencing `:3000` should be migrated to `VITE_API_URL` / `src/lib/api.ts:api()`.

## OpenAPI Flow

1. FastAPI serves spec at `http://localhost:8000/openapi.json` and Swagger UI at `/docs` (`app/main.py:23`).
2. Frontend codegen uses [`@hey-api/openapi-ts`](https://heyapi.dev) (fetch client):
   ```bash
   cd frontend
   npm run gen:api   # hey-api openapi-ts: input http://localhost:8000/openapi.json -> src/api/generated
   ```
3. Generated client is `fetch`-based; do not add `axios` imports. Import from `src/api/generated` and call with TanStack Query.
4. Regenerate after any backend schema change. Commit `src/api/generated` or gitignore it and regenerate in CI — pick one and keep consistent.

## Migration from NestJS

- `backend/` (NestJS 9 + TypeORM) is **legacy**. `backend/` is the replacement and keeps the same frontend contract (DB now SQLite by default; was MySQL) (`GET /stocks`, `GET /stock-exchange/Nse`).
- `backend/src/app.module.ts:11-22` DB config is now env-driven SQLite (was MySQL hardcoded) — see `backend/app/database.py` and `backend/alembic.ini`.
- `migrationsRun: true` in NestJS → `alembic upgrade head` in FastAPI. `002_migrate_stocks_to_portfolios.py` copies legacy `Stocks` rows into new tables idempotently; the `Stocks` table is retained.
- Delete `backend/` after parity is verified (all frontend routes working against `:8000` and no regressions in `?load=true` enrichment / duration filters).

## Docs

- [Backend — FastAPI detail](backend/README.md)
- [Frontend — Vite/React detail](frontend/README.md)
- [Architecture — data flow, DB schema, Qlib pipeline](docs/ARCHITECTURE.md)
- [API — OpenAPI, curl examples, paper trade with execution realism](docs/API.md)

## Verification (no DB)

```bash
cd backend && python -m py_compile app/main.py app/models.py app/database.py app/nse.py app/utils/duration.py app/routers/*.py app/quant/*.py alembic/env.py
cd frontend && npm run build
```

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 master8848.

## Acknowledgements

This project stands on these open-source projects — thanks to their maintainers:

- **Qlib** (`microsoft/qlib`) — AI quant platform (Alpha158, backtest) — prediction engine
- **FastAPI / SQLModel / Alembic / Pydantic** — Python API + DB layer
- **yahooquery / yfinance / nsepython / stock-nse-india** — NSE data
- **LightGBM** — gradient boosting for stock scoring
- **React / Vite / Tailwind** — frontend shell
- **shadcn/ui + Base UI** — accessible components
- **Tabler Icons** — icon set (`@tabler/icons-react`)
- **TanStack Table / Form / Query** — headless table, forms, data fetching
- **Hey API** ([heyapi.dev](https://heyapi.dev), `@hey-api/openapi-ts`) — OpenAPI fetch codegen (replaces Java generator)
- **Redux Toolkit** — column-visibility state for tables

If you use this repo, please also credit upstream licenses (all MIT/Apache-2.0). Contributions back to those projects are welcome — see their repos for how to contribute.
