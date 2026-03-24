import json
import traceback
from datetime import datetime, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from clients import MSE_API_URL, redis_client, supabase

scheduler = AsyncIOScheduler()


async def poll_and_store_prices():
    print(f"[Poller] Running at {datetime.now(timezone.utc).isoformat()}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(MSE_API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

        if data.get("status") != "success":
            print(f"[Poller] Non-success response: {data}")
            return

        snapshot_at = datetime.now(timezone.utc)
        stocks = data["stocks"]

        rows = [
            {
                "ticker": ticker,
                "open": float(values["open"]),
                "close": float(values["close"]),
                "change": float(values["change"]),
                "volume": int(values["volume"]),
                "turnover": float(values["turnover"]),
                "snapshot_at": snapshot_at.isoformat(),
            }
            for ticker, values in stocks.items()
        ]

        supabase.table("price_history").insert(rows).execute()
        print(f"[Poller] Inserted {len(rows)} rows")

        for row in rows:
            redis_client.setex(
                f"prices:{row['ticker']}",
                600,  # 10 min TTL
                json.dumps({
                    "open": row["open"],
                    "close": row["close"],
                    "change": row["change"],
                    "volume": row["volume"],
                    "turnover": row["turnover"],
                    "updated_at": snapshot_at.isoformat()
                })
            )
        print(f"[Poller] Redis updated for {len(rows)} tickers")

    except Exception as e:
        print(f"[Poller] Failed: {e}")
        traceback.print_exc()
