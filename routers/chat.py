import asyncio
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from clients import anthropic_client, limiter, redis_client
from services.rag import retrieve

router = APIRouter()

# Static system prompt placed first with cache_control so it is cacheable at the API level.
# Dynamic context (RAG chunks + live prices) is appended per-turn in the user message.
_SYSTEM_PROMPT = """You are Kwatcha AI, a specialist investing assistant for the Malawi Stock Exchange (MSE).

You help users with:
- Prices, performance, and trading data of MSE-listed stocks
- Corporate news: earnings, dividends, AGMs, board changes, acquisitions
- Sector analysis across MSE-listed industries (banking, telecoms, agriculture, hospitality, real estate)
- General investing concepts as they apply to the MSE context
- Comparing MSE stocks by financial metrics and market data

Strict rules:
1. Answer ONLY questions related to MSE stocks, Malawian capital markets, or investing concepts relevant to the MSE. Decline all other topics politely.
2. Never give specific price targets or definitive buy/sell recommendations. Always direct users to a licensed MSE stockbroker for personal advice.
3. Ground your answers in the provided context — cite prices, percentages, dates, and news items when relevant.
4. If the provided context lacks enough information, say so clearly and recommend mse.co.mw for further research.
5. Be concise, structured, and factual. Use bullet points or short paragraphs where helpful.

If a user asks something unrelated to MSE or investing, respond exactly:
"I'm only able to help with questions about MSE stocks and investing in Malawi. Please ask me about listed companies, stock prices, or capital markets topics."
"""

_OFF_TOPIC_KEYWORDS = frozenset([
    "recipe", "weather", "football", "soccer", "cricket",
    "movie", "music", "song", "game", "joke", "poem",
    "homework", "essay", "health", "medical", "doctor",
    "travel", "visa", "passport", "hotel booking",
    "relationship", "love", "dating",
])


def _is_clearly_off_topic(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in _OFF_TOPIC_KEYWORDS)


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[ConversationMessage] = []


class Source(BaseModel):
    ticker: str
    title: str
    type: str
    url: str


class ChatResponse(BaseModel):
    response: str
    sources: list[Source]


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if anthropic_client is None:
        raise HTTPException(status_code=503, detail="AI service not configured")

    if _is_clearly_off_topic(message):
        return ChatResponse(
            response=(
                "I'm only able to help with questions about MSE stocks and investing in Malawi. "
                "Please ask me about listed companies, stock prices, or capital markets topics."
            ),
            sources=[],
        )

    try:
        chunks = await asyncio.to_thread(retrieve, message, 5)
    except Exception as e:
        print(f"[RAG] retrieve failed: {e}")
        chunks = []

    live_prices: dict = {}
    try:
        for key in redis_client.keys("prices:*"):
            ticker = key.split(":")[1]
            data = redis_client.get(key)
            if data:
                try:
                    live_prices[ticker] = json.loads(data)
                except (json.JSONDecodeError, ValueError):
                    continue
    except Exception as e:
        print(f"[Chat] Redis unavailable: {e}")

    context_sections: list[str] = []

    if chunks:
        rag_text = "\n---\n".join(c["text"] for c in chunks)
        context_sections.append(f"## Relevant Knowledge Base\n{rag_text}")

    if live_prices:
        price_lines = []
        for ticker, p in sorted(live_prices.items()):
            price_lines.append(
                f"  {ticker}: open={p.get('open')}, close={p.get('close')}, "
                f"change={p.get('change')} ({p.get('pct_change')}%), "
                f"volume={p.get('volume')}, turnover={p.get('turnover')}"
            )
        context_sections.append("## Live MSE Market Data\n" + "\n".join(price_lines))

    dynamic_context = "\n\n".join(context_sections)
    user_turn = f"{dynamic_context}\n\n---\nUser question: {message}" if dynamic_context else message

    # Build messages list: history (last 10) + current user turn
    messages: list[dict] = []
    for msg in body.conversation_history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_turn})

    try:
        response = await anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=messages,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

    seen_titles: set[str] = set()
    sources: list[Source] = []
    for c in chunks:
        if c["type"] == "general" or not c["title"] or c["title"] in seen_titles:
            continue
        seen_titles.add(c["title"])
        sources.append(Source(
            ticker=c["ticker"],
            title=c["title"],
            type=c["type"],
            url=c["url"],
        ))

    return ChatResponse(response=response.content[0].text, sources=sources)
