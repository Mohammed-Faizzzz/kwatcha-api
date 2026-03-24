import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from clients import limiter, redis_client
from dependencies import verify_internal
from scraper import scrape_mse_data

router = APIRouter()


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
                stocks[ticker] = json.loads(data)
        return {
            "status": "success",
            "market": "MSE",
            "source": "cache",
            "count": len(stocks),
            "stocks": stocks
        }

    print("[/stocks] Redis empty, falling back to scraper")
    today = datetime.now().strftime("%Y-%m-%d")
    new_data = scrape_mse_data()
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
    keys = redis_client.keys("prices:*")
    if not keys:
        raise HTTPException(status_code=503, detail="No stock data available")

    stocks = {}
    for key in keys:
        ticker = key.split(":")[1]
        data = redis_client.get(key)
        if data:
            stocks[ticker] = json.loads(data)

    entries = [{"ticker": t, **v} for t, v in stocks.items()]

    sorted_by_change = sorted(entries, key=lambda x: x.get("change", 0))
    gainers = sorted_by_change[::-1][:top_n]
    losers = sorted_by_change[:top_n]

    sorted_by_volume = sorted(entries, key=lambda x: x.get("volume", 0), reverse=True)
    sorted_by_turnover = sorted(entries, key=lambda x: x.get("turnover", 0), reverse=True)

    num_gainers = sum(1 for e in entries if e.get("change", 0) > 0)
    num_losers = sum(1 for e in entries if e.get("change", 0) < 0)
    num_unchanged = len(entries) - num_gainers - num_losers

    return {
        "status": "success",
        "market": "MSE",
        "summary": {
            "total_stocks": len(entries),
            "gainers": num_gainers,
            "losers": num_losers,
            "unchanged": num_unchanged,
            "total_volume": sum(e.get("volume", 0) for e in entries),
            "total_turnover": round(sum(e.get("turnover", 0) for e in entries), 2),
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
