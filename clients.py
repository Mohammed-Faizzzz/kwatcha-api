import os
import redis
from google import genai as google_genai
from supabase import create_client, Client
from slowapi import Limiter
from slowapi.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

MSE_API_URL = "https://kwatcha-api-production.up.railway.app/stocks"

supabase: Client = create_client(URL, KEY)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
limiter = Limiter(key_func=get_remote_address)

gemini_client: google_genai.Client | None = (
    google_genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
)
