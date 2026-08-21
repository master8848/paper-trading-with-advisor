# AGENTS.md

## Repo Structure
Two apps — **no** root `package.json` / workspaces. Run commands per directory.
- `backend/` — FastAPI + SQLModel + libSQL/SQLite + Alembic. Entry `app/main.py` → `AppModule` replaced. Domains: `portfolios/` (baseline `norm=100*(price/baseline)`), `positions/`, `trades/` (LTP snapshot), `stocks/` (compat `GET /stocks?duration=tweek|lweek|tmonth|lmonth|tyear|lyear&load=true`), `stock-exchange/` (NSE proxy cached), `quant/` (Qlib Alpha158→LGBM, execution realism, screener).
- `frontend/` — Vite 4 + React 18 + Tailwind 3 + shadcn Base UI + Tabler Icons + TanStack Table 9 + Form + Query 4 + Hey API fetch codegen. Entry `src/main.tsx` → `src/routes.tsx` → `src/Home.tsx` → `src/Table.tsx` / `src/Form.tsx` / `src/pages/StockView.tsx` (`/stock/:symbol` with Screener/NSE/BSE/TradingView).

## Setup & Run
SQLite/libSQL by default (file `finance_app.db`, libSQL-compatible via Turso), swappable to Postgres/MySQL via `DATABASE_URL`.
```bash
# Backend (FastAPI :8000, CORS enabled)
cd backend && uv sync  # or pip install -r requirements.txt
# Optional: DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/finance_app
# Optional: DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/finance_app?charset=utf8mb4
# Optional: DATABASE_URL=sqlite+libsql://user:token@host:8080/db?secure=true  # Turso self-host
DATABASE_URL=sqlite:///./finance_app.db alembic upgrade head
DATABASE_URL=sqlite:///./finance_app.db uvicorn app.main:app --reload --port 8000
# docs at http://localhost:8000/docs  openapi at /openapi.json

# Self-hosted libSQL (Turso)
docker compose -f docker-compose.libsql.yml up -d  # sqld on :8080

# Frontend (VITE_API_URL defaults to http://localhost:8000)
cd frontend && npm install
npm run gen:api  # heyapi from http://localhost:8000/openapi.json -> src/api/generated
npm run dev     # vite dev server (default 5173)
npm run build   # vite build -> dist/
npm run preview # vite preview
```
Run both concurrently for full stack. Frontend will fail silently if backend not on `:8000`.

## Backend Quirks
- **DB config is env-driven** `DATABASE_URL` (default `sqlite:///./finance_app.db`, libSQL-compatible; swappable to `postgresql+psycopg://...` or `mysql+pymysql://...`). `alembic/env.py` respects `DATABASE_URL` (normalizes `libsql://` → `sqlite+libsql://`).
- **Duration filter** `app/utils/duration.py` ports `stocks.service.ts:29` `tweek|lweek|tmonth|lmonth|tyear|lyear` via `date-fns` (was `moment.startOf('week')`).
- **Enrichment** `?load=true` fetched per row via `yahooquery`/`nsepython` (was `stock-nse-india`), swallow errors.
- **Quant** `app/quant/` lazy `pyqlib` init; fallback hash+momentum if no provider data; liquidity gate `mcap<500Cr||avgVol<1L||impact>2%` blocks inference.
- **Caching** `GET /stock-exchange/Nse` via `cachetools` TTL (was `CacheInterceptor`).

## Frontend Quirks
- **Generated client** `@hey-api/openapi-ts` `openapi-ts.config.ts` → `src/api/generated` (`client: 'fetch'`, no axios). `src/lib/api.ts` is manual `fetch` wrapper (`BASE=VITE_API_URL||8000`), `src/api/client.ts` configures generated client. Prefer generated SDK for type safety; `api<any>` still in `Home/Form/StockView/PaperTrade*`.
- **State** Redux store only for column visibility (`longLoaded`/`shortLoaded`); server state in TanStack Query `cacheTime: Infinity`, `staleTime: Infinity`.
- **Routing** `/` + `/stock/:symbol` (`routes.tsx:4`).
- **Tailwind** `tailwind.config.js` content `index.html` + `src/**/*.{js,ts,jsx,tsx}`, plugin `@tailwindcss/forms`.

## Code Quality & Tests
```bash
cd backend
ruff check . && ruff format .
ty check  # or mypy
pytest -q  # 20 tests in tests/test_quant.py
npm run lint  # frontend has no lint script
python -m py_compile app/main.py app/models.py app/database.py app/nse.py app/utils/duration.py app/routers/*.py app/quant/*.py alembic/env.py
cd frontend && npm run build
# Single test: pytest tests/test_quant.py -k test_screener -v
```
Frontend has **no** test/lint scripts. Backend specs are minimal — don't rely on them catching regressions.

## Gotchas
- SQLite file `finance_app.db` created on first `alembic upgrade head` or `create_db_and_tables()`; no MySQL server needed. For Postgres/libSQL set `DATABASE_URL`.
- NSE API (`yahooquery`/`nsepython`) is flaky / rate-limited; `findEquityHistoricalData` swallows errors — don't assume `lastTradedPrice` always present.
- `VITE_API_URL` must match backend port (`:8000`); update both `backend/app/main.py` and `frontend/src/lib/api.ts` / `.env.example` together if changing.
- `nest-cli.json` legacy removed; `alembic` manages migrations.
