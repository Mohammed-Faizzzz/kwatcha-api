from fastapi import FastAPI
from datetime import datetime
from scraper import scrape_mse_data

app = FastAPI(title="Malawi Trading API")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temporary in-memory cache for MVP
cache = {
    "last_updated": None,
    "data": []
}
@app.get("/")
async def root():
    return {"message": "Welcome to the Malawi Trading API. Access /stocks for market data."}

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

historic_data = {
    "AIRTEL": [
        {"date": "2023-01-01", "price": 10.0, "volume": 1000},
        {"date": "2023-01-02", "price": 10.5, "volume": 1500},
    ],
    "NBM": [
        {"date": "2023-01-01", "price": 20.0, "volume": 2000},
        {"date": "2023-01-02", "price": 21.0, "volume": 2500},
    ]
}
@app.get("/historic/{symbol}")
async def get_historic_data(symbol: str):
    # Implement logic to retrieve historic data for the given symbol
    data = historic_data.get(symbol.upper())
    if data:
        return {"symbol": symbol.upper(), "historic_data": data}
    return {"error": "Symbol not found"}

@app.get("/stocks/{symbol}")
async def get_stock_detail(symbol: str):
    # Search the cache for a specific company (e.g., AIRTEL, NBM)
    stock = next((s for s in cache["data"] if s["symbol"].upper() == symbol.upper()), None)
    if stock:
        return stock
    return {"error": "Company not found"}

@app.post("/create_account")
async def create_account(
    # Account type
    account_type: str = Form(...),

    # Primary applicant
    full_name: str = Form(None),
    gender: str = Form(None),
    id_type: str = Form(None),
    id_number: str = Form(None),
    date_of_birth: str = Form(None),
    investor_type: str = Form(None),

    # Joint applicant (optional)
    joint_full_name: str = Form(None),
    joint_gender: str = Form(None),
    joint_id_type: str = Form(None),
    joint_id_number: str = Form(None),
    joint_date_of_birth: str = Form(None),
    joint_investor_type: str = Form(None),

    # Company (optional)
    company_name: str = Form(None),
    registration_number: str = Form(None),
    date_of_registration: str = Form(None),
    authorised_signatory_1: str = Form(None),
    authorised_signatory_2: str = Form(None),

    # Contact info
    physical_address: str = Form(None),
    postal_address: str = Form(None),
    telephone: str = Form(None),
    cellphone: str = Form(None),
    fax: str = Form(None),
    email: str = Form(None),

    # Bank details
    bank_name: str = Form(None),
    bank_branch_code: str = Form(None),
    account_number: str = Form(None),
    account_name: str = Form(None),
    primary_signature_date: str = Form(None),
    joint_signature_date: str = Form(None),

    # Credentials
    username: str = Form(...),
    password: str = Form(...),

    # File uploads
    certified_id: UploadFile = File(None),
    passport_photo_1: UploadFile = File(None),
    passport_photo_2: UploadFile = File(None),
    proof_of_address: UploadFile = File(None),
    company_docs: UploadFile = File(None),
):
    print("=" * 50)
    print("NEW ACCOUNT APPLICATION RECEIVED")
    print("=" * 50)

    # Text fields
    fields = {
        "account_type": account_type,
        "full_name": full_name,
        "gender": gender,
        "id_type": id_type,
        "id_number": id_number,
        "date_of_birth": date_of_birth,
        "investor_type": investor_type,
        "joint_full_name": joint_full_name,
        "joint_gender": joint_gender,
        "joint_id_type": joint_id_type,
        "joint_id_number": joint_id_number,
        "joint_date_of_birth": joint_date_of_birth,
        "joint_investor_type": joint_investor_type,
        "company_name": company_name,
        "registration_number": registration_number,
        "date_of_registration": date_of_registration,
        "authorised_signatory_1": authorised_signatory_1,
        "authorised_signatory_2": authorised_signatory_2,
        "physical_address": physical_address,
        "postal_address": postal_address,
        "telephone": telephone,
        "cellphone": cellphone,
        "fax": fax,
        "email": email,
        "bank_name": bank_name,
        "bank_branch_code": bank_branch_code,
        "account_number": account_number,
        "account_name": account_name,
        "primary_signature_date": primary_signature_date,
        "joint_signature_date": joint_signature_date,
        "username": username,
        "password": "***hidden***",
    }

    print("\n-- TEXT FIELDS --")
    for key, value in fields.items():
        if value is not None:
            print(f"  {key}: {value}")

    print("\n-- FILE UPLOADS --")
    for name, upload in [
        ("certified_id", certified_id),
        ("passport_photo_1", passport_photo_1),
        ("passport_photo_2", passport_photo_2),
        ("proof_of_address", proof_of_address),
        ("company_docs", company_docs),
    ]:
        if upload and upload.filename:
            print(f"  {name}: {upload.filename} ({upload.content_type})")
        else:
            print(f"  {name}: not provided")

    print("=" * 50)

    return {"message": f"Application received for {username}"}