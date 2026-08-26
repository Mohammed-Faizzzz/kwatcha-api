import re
import traceback
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from clients import supabase

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ALLOWED_UPLOAD_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/jpg"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


def _parse_date(value: str, field_name: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a valid date in YYYY-MM-DD format.")


async def _validate_upload(file: UploadFile | None, field_name: str, required: bool = False) -> bytes | None:
    if file is None or not file.filename:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required.")
        return None

    if file.content_type not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be a PDF or image file (got {file.content_type})."
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail=f"{field_name} is empty.")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"{field_name} exceeds the 10MB size limit.")
    return content


@router.post("/create_account")
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

    # ─── Input validation ───────────────────────────────────────
    email = email.strip().lower()
    username = username.strip()
    full_name = full_name.strip()

    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Please provide a valid email address.")
    if not username:
        raise HTTPException(status_code=400, detail="Username cannot be empty.")
    if not full_name:
        raise HTTPException(status_code=400, detail="Full name cannot be empty.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    if not account_type.strip():
        raise HTTPException(status_code=400, detail="account_type cannot be empty.")
    if not investor_type.strip():
        raise HTTPException(status_code=400, detail="investor_type cannot be empty.")

    _parse_date(date_of_birth, "date_of_birth")
    _parse_date(primary_signature_date, "primary_signature_date")
    if joint_date_of_birth:
        _parse_date(joint_date_of_birth, "joint_date_of_birth")
    if date_of_registration:
        _parse_date(date_of_registration, "date_of_registration")

    certified_id_bytes = await _validate_upload(certified_id, "certified_id", required=True)
    passport_photo_bytes = await _validate_upload(passport_photo, "passport_photo", required=True)
    proof_of_address_bytes = await _validate_upload(proof_of_address, "proof_of_address")
    company_docs_bytes = await _validate_upload(company_docs, "company_docs")

    file_bytes = {
        "certified_id": (certified_id, certified_id_bytes),
        "passport_photo": (passport_photo, passport_photo_bytes),
        "proof_of_address": (proof_of_address, proof_of_address_bytes),
        "company_docs": (company_docs, company_docs_bytes),
    }

    try:
        auth_response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"username": username}
        })

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Account creation failed. Please try again.")

        user_id = auth_response.user.id
        user_email = auth_response.user.email

        for name, (file, content) in file_bytes.items():
            if file is not None and content is not None:
                path = f"{user_id}/{name}_{file.filename}"
                supabase.storage.from_("kyc-documents").upload(path, content)

        supabase.table("profiles").insert({
            "id": user_id,
            "username": username,
            "email": user_email,
            "account_type": account_type,
            "full_name": full_name,
            "id_number": id_number,
            "balance": 0.00,
            "status": "pending"
        }).execute()

        return {"message": "Account created. Pending review."}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        message = str(e).lower()
        if "already" in message or "registered" in message or "duplicate" in message or "exists" in message:
            raise HTTPException(status_code=409, detail="An account with this email or username already exists.")
        raise HTTPException(status_code=500, detail="Account creation failed due to a server error. Please try again later.")


@router.post("/login")
async def login(credentials: dict):
    username = (credentials.get("username") or "").strip()
    password = credentials.get("password") or ""

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")

    try:
        # 1. Get email from username
        result = supabase.table("profiles").select("email, status").eq("username", username).single().execute()
        if not result.data:
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        # 2. Check approval status before even attempting auth
        status = result.data["status"]
        if status == "pending":
            raise HTTPException(status_code=403, detail="Your account is pending approval. We'll notify you by email.")
        if status == "rejected":
            raise HTTPException(status_code=403, detail="Your application was not approved.")

        # 3. Sign in
        response = supabase.auth.sign_in_with_password({
            "email": result.data["email"],
            "password": password
        })
        return {
            "access_token": response.session.access_token,
            "user": response.user
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid username or password.")


@router.post("/orders")
async def place_order(order: dict, token: str):
    if not token or not token.strip():
        raise HTTPException(status_code=401, detail="Authentication token is required.")

    ticker = order.get("ticker")
    shares = order.get("shares")
    price = order.get("price")
    order_type = order.get("type")

    if not ticker or not isinstance(ticker, str):
        raise HTTPException(status_code=400, detail="A valid ticker is required.")
    if order_type not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="Order type must be 'buy' or 'sell'.")
    try:
        shares = float(shares)
        price = float(price)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="shares and price must be valid numbers.")
    if shares <= 0:
        raise HTTPException(status_code=400, detail="shares must be greater than zero.")
    if price <= 0:
        raise HTTPException(status_code=400, detail="price must be greater than zero.")

    supabase.postgrest.auth(token)
    try:
        result = supabase.rpc("execute_trade", {
            "p_ticker": ticker.upper(),
            "p_shares": shares,
            "p_price": price,
            "p_type": order_type
        }).execute()
        return {"message": "Trade successful", "data": result.data}
    except Exception as e:
        print(f"[/orders] Trade failed: {e}")
        raise HTTPException(status_code=400, detail="Trade failed or insufficient funds.")
