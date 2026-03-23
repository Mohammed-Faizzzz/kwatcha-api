from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware

class RemoveHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.pop("server", None)        # removes "uvicorn"
        response.headers.pop("x-powered-by", None)
        return response