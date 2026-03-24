from fastapi import APIRouter, HTTPException, Request

from clients import limiter, supabase

router = APIRouter()


@router.get("/history/{ticker}")
@limiter.limit("20/minute")
async def get_price_history(request: Request, ticker: str, days: int = 30):
    response = (
        supabase.table("price_history")
        .select("close, volume, turnover, snapshot_at")
        .eq("ticker", ticker.upper())
        .gte("snapshot_at", f"now() - interval '{days} days'")
        .order("snapshot_at", desc=False)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="No history found for ticker")
    return {"ticker": ticker.upper(), "history": response.data}
