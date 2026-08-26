import asyncio
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from clients import limiter
from routers import auth, history, stocks
from routers.chat import router as chat_router
from services.poller import poll_and_store_prices, scheduler
from services.rag import build_index

app = FastAPI(title="Malawi Trading API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://kwatcha-fe.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(stocks.router)
app.include_router(history.router)
app.include_router(auth.router)
app.include_router(chat_router)


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
    print("[Scheduler] Price poller started — first run in 5 minutes")

    try:
        await asyncio.to_thread(build_index)
    except Exception as e:
        print(f"[RAG] Index build failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    print("[Scheduler] Stopped")


# ─── Exception Handlers ──────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"CRITICAL ERROR on {request.method} {request.url.path}: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Something went wrong on our end. Please try again shortly.",
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("VALIDATION ERROR:", exc.errors())
    friendly_errors = [
        {"field": ".".join(str(p) for p in err["loc"] if p != "body"), "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Some of the submitted data is invalid.",
            "errors": friendly_errors,
        },
    )

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "status": "error",
            "message": "Too many requests. Please slow down.",
        }
    )


# ─── Root ────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "Welcome to the Malawi Trading API."}
