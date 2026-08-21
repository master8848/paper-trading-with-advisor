# AGENTS.md

## Repo Structure
Two independent apps — **no** root `package.json` / workspaces. Run commands per directory.
- `backend/` — NestJS 9 + TypeORM + MySQL + `stock-nse-india`. Entry `src/main.ts` → `AppModule` (`src/app.module.ts`). Two domains: `stocks/` (CRUD on `Stocks` entity `src/stocks/entities/FinanceData.ts`) and `stock-exchange/` (proxy to NSE India API, cached).
- `frontend/` — Vite 4 + React 18 + Tailwind 3 + React Router 6 + Redux Toolkit + TanStack Query 4 + `react-table` 7 + Axios. Entry `src/main.tsx` → `src/routes.tsx` → `src/Home.tsx` → `src/Table.tsx` / `src/Form.tsx`.

## Setup & Run
No env files; config is hardcoded. Needs local MySQL.
```bash
# Backend (port 3000, CORS enabled, global ValidationPipe)
cd backend && npm install
# Requires MySQL running: host localhost:3306, user Finance, pass ***REDACTED***, db finance_app (see src/app.module.ts:11-22)
npm run start:dev   # watch mode (nest start --watch)
npm run start:debug # --debug --watch
npm run build       # nest build -> dist/
npm run start:prod  # node dist/main (run after build)

# Frontend (hardcoded backend URL http://localhost:3000 in Home.tsx:19, Table.tsx:37, Form.tsx)
cd frontend && npm install
npm run dev     # vite dev server (default 5173)
npm run build   # vite build -> dist/
npm run preview # vite preview
```
Run both concurrently for full stack. Frontend will fail silently if backend not on `:3000`.

## Backend Quirks
- **DB config is hardcoded** in `src/app.module.ts` — no `.env` loading. `migrationsRun: true`, `synchronize` commented out. Only `Stocks` entity is registered; `StockExchangeModule` is stateless.
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
