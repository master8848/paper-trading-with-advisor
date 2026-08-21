# API

Base `http://localhost:8000`. Spec at `/openapi.json`, Swagger UI at `/docs`, ReDoc at `/redoc` (if enabled). All examples use `fetch` via `frontend/src/lib/api.ts:api()` — `VITE_API_URL` defaults to `http://localhost:8000`.

## OpenAPI

- **Spec**: `GET http://localhost:8000/openapi.json` (served by FastAPI `app/main.py:26`)
- **Swagger**: `http://localhost:8000/docs`
- **Health**: `GET /health` → `{"status":"ok"}`
- **Index**: `GET /` → route map

Codegen:

```bash
cd frontend
npm run gen:api   # @hey-api/openapi-ts: http://localhost:8000/openapi.json -> src/api/generated (fetch client)
```

Regenerate after any schema change. See https://heyapi.dev.

## Endpoints

| Tag | Method | Path | Notes |
|-----|--------|------|-------|
| portfolios | `POST` | `/portfolios` | Create `{user_id, name, baseline_value?}` |
| portfolios | `GET` | `/portfolios` | List |
| portfolios | `GET` | `/portfolios/{id}` | Detail |
| portfolios | `POST` | `/portfolios/{id}/baseline?baseline_value=&baseline_price=` | Update baseline |
| portfolios | `GET` | `/portfolios/{id}/performance?normalized=true` | PnL per position, `pnl_normalized = pnl/baseline_value*100` |
| positions | `POST` | `/positions` | Create `{portfolio_id, symbol, qty, avg_buy_price, baseline_price?}` |
| positions | `GET` | `/positions?portfolio_id=` | List |
| trades | `POST` | `/trades` | Paper trade (see below) |
| trades | `GET` | `/trades?position_id=&symbol=` | List |
| trades | `GET` | `/trades/{id}` | Detail |
| stocks | `GET` | `/stocks?duration=&load=` | Legacy compat, `duration` in `tweek|lweek|tmonth|lmonth|tyear|lyear`, `load=true` enriches LTP/52W |
| stocks | `POST` | `/stocks` | Legacy create |
| stocks | `PATCH` | `/stocks/{id}` | Legacy update |
| stocks | `DELETE` | `/stocks/{id}` | Legacy delete |
| stock-exchange | `GET` | `/stock-exchange/Nse` | Cached 1h symbol list |
| stock-exchange | `GET` | `/stock-exchange/{symbol}` | `{lastTradedPrice, fiftyTwoWeekLow, fiftyTwoWeekHigh}` |
| quant | `POST` | `/quant/predict` | `{symbol, horizon}` → score/return/confidence |
| quant | `POST` | `/quant/backtest` | `{symbol, start, end}` → cumulative_return/sharpe/mdd |
| quant | `GET` | `/quant/screen/{symbol}` | Liquidity gate |
| quant | `GET` | `/quant/warnings/{symbol}?qty=&ideal_price=` | Screener flags |
| quant | `POST` | `/quant/execution/simulate` | Realistic execution |
| quant | `GET` | `/quant/health` | `{qlib_available, provider_uri, initialized}` |

## Examples

### Portfolios & Positions

```bash
# create portfolio
curl -X POST http://localhost:8000/portfolios \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"MBSKS","name":"Default","baseline_value":100}'

# create position
curl -X POST http://localhost:8000/positions \
  -H 'Content-Type: application/json' \
  -d '{"portfolio_id":1,"symbol":"RELIANCE","qty":10,"avg_buy_price":2500}'

# performance (normalized)
curl http://localhost:8000/portfolios/1/performance?normalized=true

# update baseline
curl -X POST 'http://localhost:8000/portfolios/1/baseline?baseline_value=100&baseline_price=2500'
```

```ts
// frontend (src/lib/api.ts)
import { api } from "./lib/api"
await api("/portfolios", { method: "POST", body: JSON.stringify({ user_id: "MBSKS", name: "Default" }) })
const perf = await api(`/portfolios/${id}/performance?normalized=true`)
```

### Paper Trade with Realistic Execution

Flow: preview execution realism before placing the trade, then post the trade. If `price_snapshot` is omitted the server snapshots current LTP; if LTP is unavailable it returns 502 and you must provide `price_snapshot` explicitly.

```bash
# 1) preview what qty/price is actually executable
curl -X POST http://localhost:8000/quant/execution/simulate \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"RELIANCE","qty":1000,"ideal_price":2850,"side":"buy"}'
# → { "feasible_qty": 850, "ideal_price": 2850, "realistic_buy_price": 2862.3,
#     "slippage_pct": 0.003, "market_impact_pct": 0.0014, "total_cost_pct": 0.004,
#     "illiquid_flag": false, "warning": null, "avg_volume_20d": 8500, ... }

# 2) check screener warnings (mcap <500Cr, ADV <1L, impact >2%)
curl 'http://localhost:8000/quant/warnings/RELIANCE?qty=1000'
# → { "illiquid": false, "warnings": [], "flags": [...], "impact_cost_pct": 0.004 }

# 3) place paper trade at realistic price (or omit price_snapshot to snapshot LTP)
curl -X POST http://localhost:8000/trades \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"RELIANCE","qty":10,"type":"buy","price_snapshot":2862.30}'

# 4) omit price_snapshot — server uses current LTP
curl -X POST http://localhost:8000/trades \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"RELIANCE","qty":10,"type":"buy"}'
```

Frontend pattern (`PaperTradeForm.tsx`):

```ts
import { api } from "../lib/api"
import { useQuery, useMutation } from "@tanstack/react-query"

// preview
const { data: preview } = useQuery({
  queryKey: ["executionPreview", symbol, qty],
  enabled: !!symbol && qty > 0,
  queryFn: () => api("/quant/execution/simulate", { method: "POST", body: JSON.stringify({ symbol, qty }) }),
})

// warnings
const { data: warnings } = useQuery({
  queryKey: ["warnings", symbol],
  enabled: !!symbol,
  queryFn: () => api(`/quant/warnings/${symbol}?qty=${qty}`),
})

// place trade — price_snapshot optional
const mutation = useMutation({
  mutationFn: (values: { symbol: string; qty: number; type: "buy"|"sell"; price_snapshot?: number }) =>
    api("/trades", { method: "POST", body: JSON.stringify(values) }),
})
```

> Show the preview in the form before submit (as `PaperTradeForm.tsx` does with the amber "Realistic Execution Preview" card). If `feasible_qty < qty` or `illiquid_flag` is true, warn that the order may partially fill or gap beyond the circuit limit.

### Quant — Predict & Backtest

```bash
# predict (gated by liquidity; fallback mock if qlib data missing)
curl -X POST http://localhost:8000/quant/predict \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"RELIANCE","horizon":"5d"}'
# → { "score": 0.23, "expected_return": 0.0092, "confidence": 0.58, "gated": false, "model_used": "fallback_momentum_hash" }
# if illiquid: { "score": 0, "expected_return": 0, "confidence": 0.05, "gated": true, "gate_reason": "Micro-cap ..." }

# backtest (YYYY-MM-DD)
curl -X POST http://localhost:8000/quant/backtest \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"RELIANCE","start":"2024-01-01","end":"2024-06-01"}'
# → { "cumulative_return": 0.04, "buy_hold_return": 0.03, "sharpe": 0.8, "max_drawdown": -0.05, "trades": [...] }

# liquidity gate
curl http://localhost:8000/quant/screen/RELIANCE
# → { "passes": true, "reason": "Passes liquidity threshold", "mcap_cr": 1200, "avg_volume_20d": 500000 }

# health
curl http://localhost:8000/quant/health
```

### Legacy Stocks (compat)

```bash
# duration filter (tweek|lweek|tmonth|lmonth|tyear|lyear) — port of moment.startOf, week=Sunday
curl 'http://localhost:8000/stocks?duration=tweek'
curl 'http://localhost:8000/stocks?duration=tweek&load=true'  # enriches each row with lastTradedPrice/52W
```

## Errors

- `422` — validation error (`symbol is required`, `qty must be >0`, etc.)
- `404` — portfolio/position/trade not found
- `502` — could not snapshot LTP for `POST /trades` without `price_snapshot` (provide `price_snapshot` explicitly)
- `500` — unexpected (quant fallback failures are swallowed and returned as fallback results, not 500)
