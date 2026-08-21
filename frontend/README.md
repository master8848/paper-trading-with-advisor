# frontend — Vite + React

Vite 4 + React 18 + Tailwind 3 + shadcn / Base UI + TanStack Table/Form/Query. Talks to FastAPI on `:8000` via `fetch` (`src/lib/api.ts`).

## Setup

```bash
cd frontend
pnpm install          # or npm install
npm run gen:api       # requires backend on http://localhost:8000
npm run dev           # http://localhost:5173
npm run build         # -> dist/
npm run preview       # preview build
```

Env:

```bash
# frontend/.env.local  (optional, defaults to http://localhost:8000)
VITE_API_URL=http://localhost:8000
```

`VITE_API_URL` is read in `src/lib/api.ts:1` via `import.meta.env.VITE_API_URL`. No `axios` — all calls go through `api<T>(url, init)` which prepends `VITE_API_URL`, sets `Content-Type: application/json`, stringifies bodies, and throws on `!res.ok`. Use `qs(params)` to build query strings.

## Stack

- **Vite 4** + `@vitejs/plugin-react` (`vite.config.js`)
- **React 18**, **React Router 6** (`src/routes.tsx`, single route `/`)
- **Tailwind 3** + `@tailwindcss/forms`, content globs `index.html` + `src/**/*.{js,ts,jsx,tsx}` (`tailwind.config.js`)
- **shadcn / Base UI** — `class-variance-authority` + `clsx` + `tailwind-merge` are installed for `cn()` utility and variant-driven components
- **@tabler/icons-react** (`^3.46`) for icons (`IconAlertTriangle` etc. in `PaperTradeForm.tsx`); `@heroicons/react` and `react-icons` also present but prefer Tabler for new code
- **@tanstack/react-table 8** (spec calls it "v9" — the installed line is `^8.21`, API is the v8/v9 `createColumnHelper` / `useReactTable` style in `PaperTradeTable.tsx`; legacy `react-table` 7 + `Table.tsx` is kept for compat)
- **@tanstack/react-form 1.x** for forms (`PaperTradeForm.tsx:95` uses `useForm` + `form.Field` + `zod` validation)
- **@tanstack/react-query 4** for server state (`Home.tsx:16` uses `cacheTime: Infinity, staleTime: Infinity, refetchOnWindowFocus: false`)
- **No axios** — `axios` is still in `package.json` but new/migrated code must use `fetch` via `src/lib/api.ts`. Remove `import axios` when touching a file.

## shadcn / Base UI

Init (if not already):

```bash
cd frontend
npx shadcn@latest init
npx shadcn@latest add button dialog select input card badge
```

Components live under `src/components/ui/` (convention). They use `class-variance-authority` for variants and `clsx` + `tailwind-merge` via `cn()` helper in `src/lib/utils.ts` (create if missing):

```ts
import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }
```

Base UI primitives (`@base-ui-components/react` if adopted) are unstyled and compose with Tailwind; shadcn wraps them with Tailwind styling. Keep Tailwind as the styling source.

## TanStack Table / Form / Query Usage

**Table** — new code uses `PaperTradeTable.tsx` pattern:

```ts
import { createColumnHelper, useReactTable, getCoreRowModel, getPaginationRowModel, getFilteredRowModel, getSortedRowModel, flexRender } from "@tanstack/react-table"

const columnHelper = createColumnHelper<StockRow>()
const columns = [columnHelper.accessor("stockName", { header: "Symbol" }), /* ... */]

const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel(), getPaginationRowModel: getPaginationRowModel(), getFilteredRowModel: getFilteredRowModel(), getSortedRowModel: getSortedRowModel() })
```

Legacy `Table.tsx` uses `react-table` 7 (`useTable`, `usePagination`, etc.) and is kept for `Home.tsx`. Migrate tables to the TanStack 8 API incrementally.

**Form** — `PaperTradeForm.tsx:95`:

```ts
import { useForm } from "@tanstack/react-form"
import { z } from "zod"

const tradeSchema = z.object({ stockName: z.string().min(1), quantity: z.coerce.number().min(1), price: z.coerce.number().min(0.01), type: z.enum(["buy","sell"]) })
const form = useForm({ defaultValues, onSubmit: async ({ value }) => { /* validate + api() */ } })
// per-field: <form.Field name="stockName" validators={{ onChange: ... }} children={(field) => <input value={field.state.value} onChange={e=>field.handleChange(e.target.value)} />} />
```

**Query** — `Home.tsx:16` and `src/lib/api.ts`:

```ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api, qs } from "./lib/api"

const { data } = useQuery({ queryKey: ["Stocks", duration, load], queryFn: () => api(`/stocks${qs({ duration, load })}`), staleTime: Infinity })
const mutation = useMutation({ mutationFn: (payload) => api(`/trades`, { method: "POST", body: JSON.stringify(payload) }) })
```

## StockView — External Links

Stock symbols link out for research (no API keys needed):

- **Screener.in** — `https://www.screener.in/company/{SYMBOL}/`
- **NSE India** — `https://www.nseindia.com/get-quotes/equity?symbol={SYMBOL}`
- **BSE India** — `https://www.bseindia.com/stock-share-price/{slug}/{SYMBOL}/`
- **TradingView** — `https://www.tradingview.com/symbols/NSE-{SYMBOL}/`

Example in a cell:

```tsx
<a href={`https://www.screener.in/company/${row.stockName}/`} target="_blank" rel="noreferrer">Screener</a>
<a href={`https://www.nseindia.com/get-quotes/equity?symbol=${row.stockName}`} target="_blank" rel="noreferrer">NSE</a>
<a href={`https://www.tradingview.com/symbols/NSE-${row.stockName}/`} target="_blank" rel="noreferrer">TradingView</a>
```

All are plain `https://` links — no broken/internal routes.

## HeyAPI Codegen

Spec is served by FastAPI at `http://localhost:8000/openapi.json` (`backend/app/main.py:26`).

```bash
# backend must be running on :8000
cd frontend
npm run gen:api
# pulls http://localhost:8000/openapi.json -> src/api/generated
```

`package.json` scripts (requires backend on :8000 or :3000):

```json
{
  "scripts": {
    "gen:api": "openapi-ts --input http://localhost:8000/openapi.json --output ./src/api/generated --client @hey-api/client-fetch",
    "gen:api:local": "openapi-ts --input ./openapi.json --output ./src/api/generated --client @hey-api/client-fetch",
    "gen:api:pull": "curl -s http://localhost:8000/openapi.json -o ./openapi.json 2>/dev/null || curl -s http://localhost:3000/openapi.json -o ./openapi.json; openapi-ts --input ./openapi.json --output ./src/api/generated --client @hey-api/client-fetch"
  },
  "devDependencies": {
    "@hey-api/openapi-ts": "^0.70.0"
  }
}
```

Config lives in `openapi-ts.config.ts` — JS-native, no Java `openapi-generator-cli`. It points to `http://localhost:8000/openapi.json` (fallback `http://localhost:3000/openapi.json` or local `./openapi.json` via `python backend/scripts/export_openapi.py --out frontend/openapi.json`), uses `client: 'fetch'` (`@hey-api/client-fetch`) and `exportSchemas: true` (`@hey-api/schemas` + `@hey-api/sdk`), and writes to `src/api/generated`. Thin wrapper `src/api/client.ts` configures `baseUrl` from `VITE_API_URL` (see `.env.example`); `src/lib/api.ts` re-exports the same `fetch` semantics and is compatible via `initGeneratedClient()`.

Docs: https://heyapi.dev/openapi-ts/. The generated client is `fetch`-based (no `axios`). Import from `src/api/generated` and wrap with TanStack Query. Example:

```ts
import { client } from '@/api/generated/client.gen';
client.setConfig({ baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000' });
import { getStocks } from '@/api/generated/sdk.gen';
// or hand wrapper:
import { api, qs } from '@/lib/api';
api(`/stocks${qs({ duration: 'tweek' })}`);
```

Regenerate after any backend schema change. Do not hand-edit `src/api/generated`. Verify with `npx tsc --noEmit`.

## Axios Removal

- `axios` is still listed in `package.json` and used in `PaperTradeForm.tsx` / `PaperTradeTable.tsx` for fallback dual-base logic (`FASTAPI_BASE` / `NEST_BASE`). New code must use `src/lib/api.ts:api()` (`fetch`) instead.
- When editing a file that imports `axios`, replace it with `api` and delete the `axios` import. Do not add new `axios` imports.
- Final cleanup: `npm uninstall axios` once no file imports it (verify with `grep -r "from \"axios\"" src/`).

## Project Layout

```
frontend/
  src/
    lib/api.ts            # fetch wrapper + qs()  (VITE_API_URL)
    lib/utils.ts          # cn() helper (clsx + tailwind-merge) if present
    components/
      PaperTradeForm.tsx  # @tanstack/react-form + zod + execution preview
      PaperTradeTable.tsx # @tanstack/react-table v8 (new)
      ui/                 # shadcn components (button, dialog, etc.)
    Table.tsx             # react-table 7 (legacy, Home.tsx)
    Form.tsx              # legacy form
    Home.tsx              # useQuery + Table + Form
    store/                # Redux Toolkit (column visibility)
    routes.tsx            # single route /
    main.tsx
  vite.config.js
  tailwind.config.js
  package.json
```

## Gotchas

- Backend moved from `:3000` (NestJS) to `:8000` (FastAPI). Set `VITE_API_URL=http://localhost:8000` or update `src/lib/api.ts:1` default. Mixed `:3000`/`:8000` references in `PaperTradeForm.tsx` are transitional.
- NSE APIs are flaky — LTP may be empty; UI handles `lastTradedPrice` as optional.
- `cacheTime`/`staleTime: Infinity` means queries never refetch unless invalidated — call `queryClient.invalidateQueries` after mutations.
