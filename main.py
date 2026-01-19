from fastapi import FastAPI
from datetime import datetime
from scraper import scrape_mse_data

app = FastAPI(title="Malawi Trading API")

# Temporary in-memory cache for MVP
cache = {
    "last_updated": None,
    "data": []
}

@app.get("/stocks")
async def get_stocks():
    # Only scrape if we haven't updated today or cache is empty
    today = datetime.now().strftime("%Y-%m-%d")
    
    if cache["last_updated"] != today:
        print("Scraping fresh data...")
        new_data = scrape_mse_data()
        if new_data:
            cache["data"] = new_data
            cache["last_updated"] = today
            
    return {
        "status": "success",
        "market": "MSE",
        "last_updated": cache["last_updated"],
        "count": len(cache["data"]),
        "stocks": cache["data"]
    }

@app.get("/stocks/{symbol}")
async def get_stock_detail(symbol: str):
    # Search the cache for a specific company (e.g., AIRTEL, NBM)
    stock = next((s for s in cache["data"] if s["symbol"].upper() == symbol.upper()), None)
    if stock:
        return stock
    return {"error": "Company not found"}