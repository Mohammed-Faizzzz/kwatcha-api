# kwatcha-api

A REST API that provides real-time and historical stock market data for the **Malawi Stock Exchange (MSE)**. It powers the [Kwatcha](https://kwatcha-fe.vercel.app) trading platform — scraping MSE listings, caching prices in Redis, persisting history in Supabase, and exposing a clean JSON API to the frontend.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Running Locally](#running-locally)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)

---

## Features

- Live MSE stock prices cached in Redis (refreshed every 5 minutes)
- Automatic scraper fallback if Redis is empty
- Price history persistence in Supabase (Postgres)
- Market movers endpoint: top gainers, losers, volume & turnover leaders
- User account creation with KYC document uploads
- JWT-based authentication via Supabase Auth
- Trade execution via Supabase RPC
- Per-IP rate limiting on all public endpoints

---

## Architecture

```
                         ┌─────────────────────┐
                         │   Frontend (Next.js) │
                         │  kwatcha-fe.vercel   │
                         └────────┬────────────┘
                                  │ HTTP
                         ┌────────▼────────────┐
                         │    kwatcha-api       │
                         │  (FastAPI / Python)  │
                         │                      │
                         │  ┌────────────────┐  │
                         │  │ APScheduler    │  │
                         │  │ (every 5 min)  │  │
                         │  └───────┬────────┘  │
                         └──────────┼───────────┘
                                    │
              ┌─────────────────────┼──────────────────────┐
              │                     │                      │
    ┌─────────▼──────┐   ┌──────────▼──────┐   ┌──────────▼──────┐
    │   MSE Website  │   │  Redis (cache)  │   │    Supabase      │
    │ mse.co.mw      │   │  prices:TICKER  │   │  - price_history │
    │ (HTML scrape)  │   │  TTL: 10 min    │   │  - profiles      │
    └────────────────┘   └─────────────────┘   │  - kyc-documents │
                                                │  - Auth          │
                                                └──────────────────┘
```

### Data flow

1. **Poller** — on startup and every 5 minutes, the scheduler calls the `/stocks` endpoint on this same API (which triggers the scraper), then writes the result to both Redis and Supabase `price_history`.
2. **Cache-first reads** — all `/stocks` requests read from Redis first. If Redis is empty (cold start or cache miss), the scraper hits `mse.co.mw` directly as a fallback.
3. **History** — Supabase stores every polled snapshot, enabling time-series queries via `/history/{ticker}`.
4. **Auth** — account creation goes through Supabase Auth (admin API) and stores KYC documents in Supabase Storage.

---

## Project Structure

```
kwatcha-api/
├── main.py              # App factory, middleware, lifecycle hooks, exception handlers
├── clients.py           # Shared clients: Supabase, Redis, rate limiter, env vars
├── dependencies.py      # FastAPI dependency: internal API key verification
├── scraper.py           # BeautifulSoup scraper for mse.co.mw
├── remove_header.py     # Middleware utility (unused in production)
├── routers/
│   ├── stocks.py        # GET /stocks, /stocks/movers, /stocks/{symbol}, /debug/redis
│   ├── history.py       # GET /history/{ticker}
│   └── auth.py          # POST /create_account, /login, /orders
├── services/
│   └── poller.py        # Background price poller + APScheduler instance
├── requirements.txt
└── Procfile             # Railway/Heroku process definition
```

---

## API Reference

All public endpoints are rate-limited per IP.

### Stocks

| Method | Endpoint | Limit | Description |
|--------|----------|-------|-------------|
| `GET` | `/stocks` | 30/min | All current MSE stock prices |
| `GET` | `/stocks/{symbol}` | 30/min | Single stock by ticker (e.g. `NBM`) |
| `GET` | `/stocks/movers` | 30/min | Top gainers, losers, volume & turnover leaders |
| `GET` | `/history/{ticker}` | 20/min | Price history for a ticker (default: last 30 days) |

**`GET /stocks`**
```json
{
  "status": "success",
  "market": "MSE",
  "source": "cache",
  "count": 16,
  "stocks": {
    "NBM": {
      "open": 2950.0,
      "close": 3000.0,
      "change": 1.69,
      "volume": 12500,
      "turnover": 37500000.0,
      "updated_at": "2026-03-24T10:00:00+00:00"
    }
  }
}
```

**`GET /stocks/movers?top_n=5`**
```json
{
  "status": "success",
  "market": "MSE",
  "summary": {
    "total_stocks": 16,
    "gainers": 5,
    "losers": 3,
    "unchanged": 8,
    "total_volume": 250000,
    "total_turnover": 850000000.0
  },
  "top_gainers": [...],
  "top_losers": [...],
  "highest_volume": [...],
  "highest_turnover": [...]
}
```

**`GET /history/{ticker}?days=30`**
```json
{
  "ticker": "NBM",
  "history": [
    {
      "close": 2950.0,
      "volume": 10000,
      "turnover": 29500000.0,
      "snapshot_at": "2026-02-24T10:00:00+00:00"
    }
  ]
}
```

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/create_account` | Register a new user with KYC documents (multipart/form-data) |
| `POST` | `/login` | Sign in, returns a Supabase JWT access token |
| `POST` | `/orders` | Execute a trade via Supabase RPC |

### Internal (API key required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/debug/redis` | Inspect all cached Redis keys and values |

Pass `X-Api-Key: <INTERNAL_API_KEY>` in the request header.

---

## Running Locally

### Prerequisites

- Python 3.11+
- A running Redis instance (or Docker)
- A Supabase project

### 1. Clone and install

```bash
git clone https://github.com/<your-org>/kwatcha-api.git
cd kwatcha-api
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in the values — see Environment Variables below
```

### 3. Start Redis

```bash
# With Docker
docker run -d -p 6379:6379 redis:alpine

# Or if installed locally
redis-server
```

### 4. Run the API

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>

# Redis
REDIS_URL=redis://localhost:6379

# Internal API key (for /debug/redis)
INTERNAL_API_KEY=<any-secret-string>
```

> **Note:** Use the **service role** key (not the anon key) — the API creates users via the admin API and uploads files to private storage buckets.

---

## Deployment

The app is deployed on [Railway](https://railway.app) using the `Procfile`:

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

Railway injects `$PORT` automatically. Set all environment variables in the Railway project dashboard under **Variables**.

Redis is provisioned as a Railway plugin — copy the `REDIS_URL` from the plugin into the service's variables.
