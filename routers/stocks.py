import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from clients import limiter, redis_client
from dependencies import verify_internal
from scraper import scrape_mse_data

router = APIRouter()


@router.get("/debug/flush-prices", dependencies=[Depends(verify_internal)])
async def flush_prices():
    keys = redis_client.keys("prices:*")
    if keys:
        redis_client.delete(*keys)
    return {"status": "success", "flushed": len(keys)}


@router.get("/debug/redis", dependencies=[Depends(verify_internal)])
async def debug_redis():
    keys = redis_client.keys("prices:*")
    stocks = {}
    for key in keys:
        data = redis_client.get(key)
        if data:
            stocks[key] = json.loads(data)
    return {
        "key_count": len(keys),
        "keys": keys,
        "data": stocks
    }


@router.get("/stocks")
@limiter.limit("30/minute")
async def get_stocks(request: Request):
    keys = redis_client.keys("prices:*")

    if keys:
        stocks = {}
        for key in keys:
            ticker = key.split(":")[1]
            data = redis_client.get(key)
            if data:
                try:
                    stocks[ticker] = json.loads(data)
                except (json.JSONDecodeError, ValueError):
                    continue
        return {
            "status": "success",
            "market": "MSE",
            "source": "cache",
            "count": len(stocks),
            "stocks": stocks
        }

    print("[/stocks] Redis empty, falling back to scraper")
    today = datetime.now().strftime("%Y-%m-%d")
    new_data = await scrape_mse_data()
    if not new_data:
        raise HTTPException(status_code=503, detail="Unable to fetch stock data")
    return {
        "status": "success",
        "market": "MSE",
        "source": "scraper",
        "last_updated": today,
        "count": len(new_data),
        "stocks": new_data
    }


@router.get("/stocks/movers")
@limiter.limit("30/minute") # MODIFY TO USE CHANGE/PCT_CHANGE
async def get_movers(request: Request, top_n: int = 5):
    keys = redis_client.keys("prices:*")
    if not keys:
        raise HTTPException(status_code=503, detail="No stock data available")

    stocks = {}
    for key in keys:
        ticker = key.split(":")[1]
        data = redis_client.get(key)
        if data:
            try:
                stocks[ticker] = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                continue

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
    data = redis_client.get(f"prices:{symbol.upper()}")
    if data:
        return {"ticker": symbol.upper(), **json.loads(data)}
    raise HTTPException(status_code=404, detail="Symbol not found")
