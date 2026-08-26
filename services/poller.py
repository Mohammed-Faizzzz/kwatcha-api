import json
import traceback
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from clients import redis_client, supabase
from scraper import scrape_mse_data

scheduler = AsyncIOScheduler()


async def poll_and_store_prices():
    print(f"[Poller] Running at {datetime.now(timezone.utc).isoformat()}")
    try:
        stocks = await scrape_mse_data()

        if not stocks:
            print("[Poller] Scraper returned no data")
            return

        snapshot_at = datetime.now(timezone.utc)
        today = snapshot_at.date().isoformat()

        rows = []
        for ticker, values in stocks.items():
            if values["open"] is None:
                continue
            try:
                rows.append({
                    "ticker": ticker,
                    "open": float(values["open"]),
                    "close": float(values["close"]),
                    "change": float(values["change"]),
                    "volume": int(values["volume"]),
                    "turnover": float(values["turnover"]),
                    "snapshot_at": today,
                })
            except (TypeError, ValueError) as e:
                print(f"[Poller] Skipping {ticker}: malformed data ({e})")
                continue

        if rows:
            try:
                supabase.table("price_history").upsert(
                    rows,
                    on_conflict="ticker,snapshot_at"
                ).execute()
                print(f"[Poller] Upserted {len(rows)} rows")
            except Exception as e:
                print(f"[Poller] Supabase upsert failed: {e}")

        redis_updated = 0
        for ticker, values in stocks.items():
            if values["open"] is None:
                continue
            try:
                open_price = float(values["open"])
                close_price = float(values["close"])
                change = close_price - open_price
                pct_change = round(change / open_price * 100, 4) if open_price else 0.0
                redis_client.setex(
                    f"prices:{ticker}",
                    86400,  # 24hr TTL — survives multiple failed polls
                    json.dumps({
                        "open": open_price,
                        "close": close_price,
                        "change": round(change, 4),
                        "pct_change": pct_change,
                        "volume": int(values["volume"]) if values["volume"] else 0,
                        "turnover": float(values["turnover"]) if values["turnover"] else 0.0,
                        "updated_at": snapshot_at.isoformat()
                    })
                )
                redis_updated += 1
            except (TypeError, ValueError) as e:
                print(f"[Poller] Skipping Redis update for {ticker}: malformed data ({e})")
            except Exception as e:
                print(f"[Poller] Redis unavailable, aborting cache update: {e}")
                break
        print(f"[Poller] Redis updated for {redis_updated} tickers")

    except Exception as e:
        print(f"[Poller] Failed: {e}")
        traceback.print_exc()
