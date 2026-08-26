import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from clients import limiter, redis_client, safe_redis_get, safe_redis_keys
from dependencies import verify_internal
from scraper import scrape_mse_data

router = APIRouter()

MAX_TOP_N = 50


@router.get("/debug/flush-prices", dependencies=[Depends(verify_internal)])
async def flush_prices():
    try:
        keys = redis_client.keys("prices:*")
        if keys:
            redis_client.delete(*keys)
    except Exception as e:
        print(f"[/debug/flush-prices] Redis error: {e}")
        raise HTTPException(status_code=503, detail="Cache service unavailable. Please try again later.")
    return {"status": "success", "flushed": len(keys)}


@router.get("/debug/redis", dependencies=[Depends(verify_internal)])
async def debug_redis():
    try:
        keys = redis_client.keys("prices:*")
    except Exception as e:
        print(f"[/debug/redis] Redis error: {e}")
        raise HTTPException(status_code=503, detail="Cache service unavailable. Please try again later.")

    stocks = {}
    for key in keys:
        data = safe_redis_get(key)
        if data:
            try:
                stocks[key] = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                continue
    return {
        "key_count": len(keys),
        "keys": keys,
        "data": stocks
    }


@router.get("/stocks")
@limiter.limit("30/minute")
async def get_stocks(request: Request):
    keys = safe_redis_keys("prices:*")

    if keys:
        stocks = {}
        for key in keys:
            parts = key.split(":")
            if len(parts) < 2:
                continue
            ticker = parts[1]
            data = safe_redis_get(key)
            if data:
                try:
                    stocks[ticker] = json.loads(data)
                except (json.JSONDecodeError, ValueError):
                    continue
        if stocks:
            return {
                "status": "success",
                "market": "MSE",
                "source": "cache",
                "count": len(stocks),
                "stocks": stocks
            }

    print("[/stocks] Redis empty or unavailable, falling back to scraper")
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        new_data = await scrape_mse_data()
    except Exception as e:
        print(f"[/stocks] Scraper exception: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch stock data. Please try again shortly.")
    if not new_data:
        raise HTTPException(status_code=503, detail="Unable to fetch stock data. Please try again shortly.")
    return {
        "status": "success",
        "market": "MSE",
        "source": "scraper",
        "last_updated": today,
        "count": len(new_data),
        "stocks": new_data
    }


@router.get("/stocks/movers")
@limiter.limit("30/minute")
async def get_movers(request: Request, top_n: int = 5):
    if top_n <= 0:
        raise HTTPException(status_code=400, detail="top_n must be a positive integer.")
    if top_n > MAX_TOP_N:
        raise HTTPException(status_code=400, detail=f"top_n cannot exceed {MAX_TOP_N}.")

    keys = safe_redis_keys("prices:*")
    if not keys:
        raise HTTPException(status_code=503, detail="No stock data available right now. Please try again shortly.")

    stocks = {}
    for key in keys:
        parts = key.split(":")
        if len(parts) < 2:
            continue
        ticker = parts[1]
        data = safe_redis_get(key)
        if data:
            try:
                stocks[ticker] = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                continue

    if not stocks:
        raise HTTPException(status_code=503, detail="No stock data available right now. Please try again shortly.")

    entries = [{"ticker": t, **v} for t, v in stocks.items()]

    def to_float(val, default=0.0):
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    sorted_by_change = sorted(entries, key=lambda x: to_float(x.get("pct_change")))
    gainers = sorted_by_change[::-1][:top_n]
    losers = sorted_by_change[:top_n]

    sorted_by_volume = sorted(entries, key=lambda x: to_float(x.get("volume")), reverse=True)
    sorted_by_turnover = sorted(entries, key=lambda x: to_float(x.get("turnover")), reverse=True)

    num_gainers = sum(1 for e in entries if to_float(e.get("pct_change")) > 0)
    num_losers = sum(1 for e in entries if to_float(e.get("pct_change")) < 0)
    num_unchanged = len(entries) - num_gainers - num_losers

    return {
        "status": "success",
        "market": "MSE",
        "summary": {
            "total_stocks": len(entries),
            "gainers": num_gainers,
            "losers": num_losers,
            "unchanged": num_unchanged,
            "total_volume": sum(to_float(e.get("volume")) for e in entries),
            "total_turnover": round(sum(to_float(e.get("turnover")) for e in entries), 2),
        },
        "top_gainers": gainers,
        "top_losers": losers,
        "highest_volume": sorted_by_volume[:top_n],
        "highest_turnover": sorted_by_turnover[:top_n],
    }


@router.get("/stocks/{symbol}")
@limiter.limit("30/minute")
async def get_stock_detail(request: Request, symbol: str):
    symbol = symbol.strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol cannot be empty.")

    data = safe_redis_get(f"prices:{symbol.upper()}")
    if not data:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol.upper()}' not found.")

    try:
        parsed = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        print(f"[/stocks/{symbol}] Corrupt cache entry")
        raise HTTPException(status_code=503, detail="Stock data is temporarily unavailable. Please try again shortly.")

    return {"ticker": symbol.upper(), **parsed}
