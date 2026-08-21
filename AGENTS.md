# AGENTS.md

## Repo Structure
Two independent apps — **no** root `package.json` / workspaces. Run commands per directory.
- `backend/` — NestJS 9 + TypeORM + MySQL + `stock-nse-india`. Entry `src/main.ts` → `AppModule` (`src/app.module.ts`). Two domains: `stocks/` (CRUD on `Stocks` entity `src/stocks/entities/FinanceData.ts`) and `stock-exchange/` (proxy to NSE India API, cached).
- `frontend/` — Vite 4 + React 18 + Tailwind 3 + React Router 6 + Redux Toolkit + TanStack Query 4 + `react-table` 7 + Axios. Entry `src/main.tsx` → `src/routes.tsx` → `src/Home.tsx` → `src/Table.tsx` / `src/Form.tsx`.

## Setup & Run
No env files historically; now SQLite by default (libsql-compatible), swappable to Postgres/MySQL via `DATABASE_URL`.
```bash
# Backend_py (FastAPI :8000, SQLite finance_app.db by default — no MySQL needed)
cd backend_py && uv sync  # or pip install -r requirements.txt
# Optional: DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/finance_app  # Postgres
# Optional: DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/finance_app?charset=utf8mb4  # MySQL
# Optional: DATABASE_URL=libsql://...  # Turso
DATABASE_URL=sqlite:///./finance_app.db alembic upgrade head
DATABASE_URL=sqlite:///./finance_app.db uvicorn app.main:app --reload --port 8000
# Legacy NestJS backend/ (deprecated, now env-driven, defaults to sqlite; was MySQL)
cd backend && npm install && npm run start:dev

# Frontend (VITE_API_URL env, defaults to http://localhost:8000)
cd frontend && npm install
npm run dev     # vite dev server (default 5173)
npm run build   # vite build -> dist/
npm run preview # vite preview
```
Run both concurrently for full stack. Frontend will fail silently if backend not on `:8000`.

## Backend Quirks
- **DB config is env-driven** `DATABASE_URL` (default `sqlite:///./finance_app.db`, libsql-compatible; swappable to `postgresql+psycopg://...` or `mysql+pymysql://...`). Legacy `backend/src/app.module.ts` was hardcoded MySQL, now env-driven. `migrationsRun: true`, `synchronize` commented out. Only `Stocks` entity is registered; `StockExchangeModule` is stateless.
- **TypeORM + moment**: `StocksService.findAll()` (`src/stocks/stocks.service.ts:29`) filters by `modified` using `MoreThan`/`Between` with `moment().startOf(...)` and `toISOString()`. Duration param: `tweek|lweek|tmonth|lmonth|tyear|lyear` (default = all). `?load=true` enriches each row via `stock-nse-india` call — slow, makes N parallel HTTP requests.
- **Validation**: `main.ts:8` uses `new ValidationPipe()` without `whitelist/transform` flags. DTOs (`stocks/dto/*.ts`) use `class-validator`.
- **Caching**: `StockExchangeController.getStockExchange()` (`src/stock-exchange/stock-exchange.controller.ts:18`) uses `CacheInterceptor` for `GET /stock-exchange/Nse`.
- **Path alias**: `src/` via `tsconfig.json:13 baseUrl ./.` — imports like `src/stocks/...`.

## Frontend Quirks
- **Duplicate query libs**: both `react-query@3` and `@tanstack/react-query@4` installed; actual code uses `@tanstack/react-query` only (`Home.tsx:1`, `Table.tsx:15`). Don't add `react-query` imports.
- **State**: Redux store (`src/store/app.ts` + `configureSettingsSlice.ts`) only for table column visibility (`longLoaded`/`shortLoaded`); server state lives in TanStack Query with `cacheTime: Infinity`, `staleTime: Infinity`, `refetchOnWindowFocus: false` (`Home.tsx:16`).
- **Routing**: single route `/` (`routes.tsx:4`). No tests/lint scripts.
- **Tailwind**: `tailwind.config.js` content globs `index.html` + `src/**/*.{js,ts,jsx,tsx}`, plugin `@tailwindcss/forms`.

## Code Quality & Tests
```bash
cd backend
npm run lint      # eslint "{src,apps,libs,test}/**/*.ts" --fix (uses .eslintrc.js + .prettierrc)
npm run format    # prettier --write "src/**/*.ts" "test/**/*.ts"
npm run test      # jest (jest config inline in package.json: rootDir src, testRegex .*\.spec\.ts)
npm run test:cov  # jest --coverage -> ../coverage
npm run test:e2e  # jest --config ./test/jest-e2e.json (rootDir ., testRegex .e2e-spec.ts) — see test/app.e2e-spec.ts
npm run test:watch
# Single test: npx jest src/stocks/stocks.service.spec.ts --runInBand
```
Frontend has **no** test/lint scripts. Backend specs are minimal stubs — don't rely on them catching regressions.

## Gotchas
- MySQL must exist before `npm run start:dev`; app will crash on connection failure.
- NSE API (`stock-nse-india`) is flaky / rate-limited; `StocksService.findAll({load:true})` and `StockExchangeService.findEquityHistoricalData` swallow errors and return original row — don't assume `lastTradedPrice` always present.
- Hardcoded secrets and URLs — update both `backend/src/app.module.ts` and `frontend/src/Home.tsx|Table.tsx|Form.tsx` together if changing ports/hosts.
- `nest-cli.json` has `deleteOutDir: true`; `tsconfig.build.json` excludes `test` and `**/*spec.ts`.
