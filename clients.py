import os
import redis
import anthropic
from supabase import create_client, Client
from slowapi import Limiter
from slowapi.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

MSE_API_URL = "https://kwatcha-api-production.up.railway.app/stocks"

supabase: Client = create_client(URL, KEY)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
limiter = Limiter(key_func=get_remote_address)

anthropic_client: anthropic.AsyncAnthropic | None = (
    anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
)
