from supabase import create_client, Client
from datetime import datetime
from scraper import scrape_mse_data
from fastapi import FastAPI, HTTPException, Form, File, UploadFile
import os
from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import JSONResponse
import traceback
from fastapi.exceptions import RequestValidationError


load_dotenv()  # Load environment variables from .env file
app = FastAPI(title="Malawi Trading API")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Use the service role key for admin operations

supabase: Client = create_client(URL, KEY)

# Temporary in-memory cache for MVP
cache = {
    "last_updated": None,
    "data": []
}
@app.get("/")
async def root():
    return {"message": "Welcome to the Malawi Trading API. Access /stocks for market data."}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # This prints the error to your terminal so you can see the line number
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
    full_name: str = Form(...),
    gender: str = Form(...),
    id_type: str = Form(...),
    id_number: str = Form(...),
    date_of_birth: str = Form(...),
    investor_type: str = Form(...),

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
    physical_address: str = Form(...),
    postal_address: str = Form(None),
    telephone: str = Form(...),
    cellphone: str = Form(None),
    fax: str = Form(None),
    email: str = Form(...),

    # Bank details
    bank_name: str = Form(None),
    bank_branch_code: str = Form(None),
    account_number: str = Form(None),
    account_name: str = Form(None),
    primary_signature_date: str = Form(...),
    joint_signature_date: str = Form(None),

    # Credentials
    username: str = Form(...),
    password: str = Form(...),

    # File uploads
    certified_id: UploadFile = File(...),
    passport_photo: UploadFile = File(...),
    proof_of_address: UploadFile = File(None),
    company_docs: UploadFile = File(None),
):
    print("=" * 50)
    print("NEW ACCOUNT APPLICATION RECEIVED")
    print("=" * 50)

    try:
        # 1. Sign up the user (Supabase handles the password hashing)
        print(f"Creating user with email: {email} and username: {username}")
        
        auth_response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # marks them as confirmed immediately
            "user_metadata": {
                "username": username,
            }
        })

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="User creation failed")

        user_id = auth_response.user.id

        # 2. Upload KYC Files to Private Storage
        # We organize folders by user_id to keep documents segregated
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

        # 3. Insert detailed profile data into public.profiles
        # Map your large form into a single dictionary
        profile_data = {
            "id": user_id, # Link to the Auth user
            "account_type": account_type,
            "full_name": full_name,
            "id_number": id_number,
            "balance": 0.00 # Initializing account balance
        }
        supabase.table("profiles").insert(profile_data).execute()

        return {"message": "Account created. Please verify your email."}
    
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    print("=" * 50)

    return {"message": f"Application received for {username}"}

@app.post("/login")
async def login(credentials: dict):
    email = credentials.get("email") # Use email as per Supabase default
    password = credentials.get("password")

    try:
        response = supabase.auth.sign_in_with_password({
            "email": email, 
            "password": password
        })
        # The session contains the JWT needed for authenticated orders
        return {"access_token": response.session.access_token, "user": response.user}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/orders")
async def place_order(order: dict, token: str):
    # Set the session so the database knows WHICH user is trading
    supabase.postgrest.auth(token)
    
    # We call a custom Postgres function 'execute_trade' 
    # that handles balance checks and portfolio updates as a single transaction
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