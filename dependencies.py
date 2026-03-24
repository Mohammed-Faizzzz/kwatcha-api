from fastapi import Header, HTTPException
from clients import INTERNAL_API_KEY


def verify_internal(x_api_key: str = Header(...)):
    if x_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
