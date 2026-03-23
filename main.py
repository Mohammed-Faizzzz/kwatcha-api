from supabase import create_client, Client
from datetime import datetime, timezone
from decimal import Decimal
from scraper import scrape_mse_data
from remove_header import RemoveHeadersMiddleware
from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
import redis
import json
import os
import traceback
from dotenv import load_dotenv
# from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response

load_dotenv()

app = FastAPI(title="Malawi Trading API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://kwatcha-fe.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# app.add_middleware(RemoveHeadersMiddleware) 

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MSE_API_URL = "https://kwatcha-api-production.up.railway.app/stocks"
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

supabase: Client = create_client(URL, KEY)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
scheduler = AsyncIOScheduler()

# ─── Price Poller ────────────────────────────────────────────────

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

        # write to supabase
        supabase.table("price_history").insert(rows).execute()
        print(f"[Poller] Inserted {len(rows)} rows")

        # write to redis
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

# ─── Lifecycle ───────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    scheduler.add_job(
        poll_and_store_prices,
        trigger="interval",
        minutes=5,
        max_instances=1,
        id="price_poller"
    )
    scheduler.start()
    print("[Scheduler] Price poller started")
    # run once immediately on startup so you don't wait 5 mins
    await poll_and_store_prices()

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    print("[Scheduler] Stopped")

# ─── Exception Handlers ──────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"CRITICAL ERROR: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "details": str(exc)},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print("VALIDATION ERROR:", exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# ─── Routes ──────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "Welcome to the Malawi Trading API."}

@app.get("/debug/redis")
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

@app.get("/stocks")
async def get_stocks():
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

    # redis empty — degraded fallback, poller will fix this shortly
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
    
@app.get("/stocks/movers")
async def get_movers(top_n: int = 5):
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

@app.get("/stocks/{symbol}")
async def get_stock_detail(symbol: str):
    data = redis_client.get(f"prices:{symbol.upper()}")
    if data:
        return {"ticker": symbol.upper(), **json.loads(data)}
    raise HTTPException(status_code=404, detail="Symbol not found")

@app.get("/history/{ticker}")
async def get_price_history(ticker: str, days: int = 30):
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

# ─── Account + Auth (unchanged) ──────────────────────────────────

@app.post("/create_account")
async def create_account(
    account_type: str = Form(...),
    full_name: str = Form(...),
    gender: str = Form(...),
    id_type: str = Form(...),
    id_number: str = Form(...),
    date_of_birth: str = Form(...),
    investor_type: str = Form(...),
    joint_full_name: str = Form(None),
    joint_gender: str = Form(None),
    joint_id_type: str = Form(None),
    joint_id_number: str = Form(None),
    joint_date_of_birth: str = Form(None),
    joint_investor_type: str = Form(None),
    company_name: str = Form(None),
    registration_number: str = Form(None),
    date_of_registration: str = Form(None),
    authorised_signatory_1: str = Form(None),
    authorised_signatory_2: str = Form(None),
    physical_address: str = Form(...),
    postal_address: str = Form(None),
    telephone: str = Form(...),
    cellphone: str = Form(None),
    fax: str = Form(None),
    email: str = Form(...),
    bank_name: str = Form(None),
    bank_branch_code: str = Form(None),
    account_number: str = Form(None),
    account_name: str = Form(None),
    primary_signature_date: str = Form(...),
    joint_signature_date: str = Form(None),
    username: str = Form(...),
    password: str = Form(...),
    certified_id: UploadFile = File(...),
    passport_photo: UploadFile = File(...),
    proof_of_address: UploadFile = File(None),
    company_docs: UploadFile = File(None),
):
    print("=" * 50)
    print("NEW ACCOUNT APPLICATION RECEIVED")
    print("=" * 50)

    try:
        auth_response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"username": username}
        })

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="User creation failed")

        user_id = auth_response.user.id

        uploads = [
            ("certified_id", certified_id),
            ("passport_photo", passport_photo),
            ("proof_of_address", proof_of_address),
        ]
        for name, file in uploads:
            if file and file.filename:
                path = f"{user_id}/{name}_{file.filename}"
                content = await file.read()
                supabase.storage.from_("kyc-documents").upload(path, content)

        profile_data = {
            "id": user_id,
            "account_type": account_type,
            "full_name": full_name,
            "id_number": id_number,
            "balance": 0.00
        }
        supabase.table("profiles").insert(profile_data).execute()

        return {"message": "Account created. Pending review."}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
async def login(credentials: dict):
    email = credentials.get("email")
    password = credentials.get("password")
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return {
            "access_token": response.session.access_token,
            "user": response.user
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/orders")
async def place_order(order: dict, token: str):
    supabase.postgrest.auth(token)
    try:
        result = supabase.rpc("execute_trade", {
            "p_ticker": order.get("ticker"),
            "p_shares": order.get("shares"),
            "p_price": order.get("price"),
            "p_type": order.get("type")
        }).execute()
        return {"message": "Trade successful", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Trade failed or insufficient funds")