from fastapi import APIRouter, HTTPException, Request

from clients import limiter, supabase
from datetime import datetime, timedelta, timezone

router = APIRouter()

MAX_HISTORY_DAYS = 365


@router.get("/history/{ticker}")
@limiter.limit("20/minute")
async def get_price_history(request: Request, ticker: str, days: int = 30):
    ticker = ticker.strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker cannot be empty.")
    if days <= 0:
        raise HTTPException(status_code=400, detail="days must be a positive integer.")
    if days > MAX_HISTORY_DAYS:
        raise HTTPException(status_code=400, detail=f"days cannot exceed {MAX_HISTORY_DAYS}.")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        response = (
            supabase.table("price_history")
            .select("close, volume, turnover, snapshot_at")
            .eq("ticker", ticker.upper())
            .gte("snapshot_at", cutoff)
            .order("snapshot_at", desc=False)
            .execute()
        )
    except Exception as e:
        print(f"[/history/{ticker}] Supabase error: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch price history right now. Please try again shortly.")

    if not response.data:
        raise HTTPException(status_code=404, detail=f"No history found for ticker '{ticker.upper()}'.")
    return {"ticker": ticker.upper(), "history": response.data}
