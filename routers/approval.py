import traceback

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from clients import supabase
from dependencies import verify_internal

router = APIRouter()

@router.post("/admin/approve-user", dependencies=[Depends(verify_internal)])
async def approve_user(body: dict):
    email = (body.get("email") or "").strip()
    status = body.get("status", "approved")

    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")

    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'.")

    try:
        result = supabase.table("profiles")\
            .update({"status": status})\
            .eq("email", email)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="User not found.")

        return {"message": f"User {email} has been {status}."}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Unable to update user status. Please try again later.")