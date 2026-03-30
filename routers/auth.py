import traceback

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from clients import supabase

router = APIRouter()


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

        supabase.table("profiles").insert({
            "id": user_id,
            "account_type": account_type,
            "full_name": full_name,
            "id_number": id_number,
            "balance": 0.00
        }).execute()

        return {"message": "Account created. Pending review."}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def login(credentials: dict):
    username = credentials.get("username")
    password = credentials.get("password")
    try:
        result = supabase.table("users").select("email").eq("username", username).single().execute()
        if not result.data:
            raise HTTPException(status_code=401, detail="Invalid username or password.")
        
        email = result.data["email"]

        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return {
            "access_token": response.session.access_token,
            "user": response.user
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid username or password.")


@router.post("/orders")
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
