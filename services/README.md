# cBot Codegen API

FastAPI service that generates Python cTrader cBot code, validates it with `ruff` + `mypy`, and runs SMA-cross backtests over data pulled from Twelve Data (free tier).

## Endpoints

- `GET /health` — liveness probe (reports whether `TWELVE_DATA_API_KEY` is set)
- `POST /generate` — `{ spec }` → `{ code, filename, warnings }`
- `POST /validate` — `{ code, checks: ["ruff","mypy"] }` → issues + summary
- `POST /backtest` — `{ spec, symbol, interval, outputsize, initial_balance }` → metrics + trades + equity curve
- `GET /backtest/smoke-test` — quick connection check, returns `{ ok, message, twelvedata_configured }`

All non-health endpoints require `Authorization: Bearer $API_TOKEN` when `API_TOKEN` is set.

## Local dev

```bash
cd services/codegen-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill API_TOKEN and TWELVE_DATA_API_KEY
uvicorn app.main:app --reload --port 8000
```

## Deploy to Render (free tier)

1. Push this repo to GitHub.
2. Render dashboard → **New +** → **Blueprint** → pick this repo.
3. Render auto-detects `services/codegen-api/render.yaml`.
4. `API_TOKEN` is auto-generated. Copy it from the service's **Environment** tab.
5. Add `TWELVE_DATA_API_KEY` in **Environment** (free key from https://twelvedata.com/, 800 req/day).
6. Set `ALLOWED_ORIGINS` to your Lovable app URLs (comma-separated) and redeploy.

Note: Render free tier sleeps after ~15 min idle → first request after a nap takes ~30 s to cold-start.

## Wiring into the Lovable app

Save these secrets in Lovable (server-only env vars, used by TanStack server functions):

- `CODEGEN_API_URL` — e.g. `https://cbot-codegen-api.onrender.com`
- `CODEGEN_API_TOKEN` — the `API_TOKEN` value from Render

The frontend calls `/generate`, `/validate`, `/backtest` through server functions in `src/lib/codegen-api.functions.ts`.

## Twelve Data symbol/interval format

- Symbols: `EUR/USD`, `GBP/USD`, `USD/JPY`, `XAU/USD`, `BTC/USD` (with slash)
- Intervals: `1min`, `5min`, `15min`, `30min`, `1h`, `2h`, `4h`, `1day`, `1week`
