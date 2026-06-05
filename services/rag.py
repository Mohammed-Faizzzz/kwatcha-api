import json
import os
from pathlib import Path
from typing import TypedDict

import chromadb
from google.genai import types as genai_types

from clients import gemini_client

INSIGHTS_PATH = Path(__file__).parent.parent / "insights.json"

MSE_COMPANIES = {
    "AIRTEL": {
        "name": "Airtel Malawi PLC",
        "sector": "Telecommunications",
        "description": (
            "Malawi's leading mobile network operator providing voice, data, and Airtel Money "
            "mobile financial services. Part of the pan-African Airtel Africa group. "
            "New MD Aashish Dutt appointed January 2025. Profit soared 375% in H1 2025."
        ),
    },
    "BHL": {
        "name": "Blantyre Hotels Limited",
        "sector": "Hospitality",
        "description": (
            "Operates premium hotel properties in Malawi including the historic Ryalls Hotel "
            "in Blantyre city centre."
        ),
    },
    "FDHB": {
        "name": "FDH Bank PLC",
        "sector": "Banking & Financial Services",
        "description": (
            "One of Malawi's largest and fastest-growing commercial banks. "
            "Posted record profits of K151 billion in 2025, achieving a K4.7 trillion market cap milestone. "
            "Acquired Ecobank Mozambique in 2025 as part of regional expansion."
        ),
    },
    "FMBCH": {
        "name": "FMB Capital Holdings PLC",
        "sector": "Banking & Financial Services",
        "description": (
            "Holding company for First Merchant Bank offering diversified financial services "
            "across several African countries including Malawi, Zambia, and Tanzania."
        ),
    },
    "ICON": {
        "name": "ICON Properties PLC",
        "sector": "Real Estate",
        "description": (
            "Listed real estate investment company focused on commercial and residential "
            "property development and management in Malawi."
        ),
    },
    "ILLOVO": {
        "name": "Illovo Sugar (Malawi) PLC",
        "sector": "Agriculture & Food Processing",
        "description": (
            "Malawi's largest sugar producer and agribusiness, part of the Illovo Sugar Africa group. "
            "Reported a 250% profit jump in 2025 but production fell 25% from peak due to adverse weather. "
            "Partnered with IFC for sustainable agriculture and job creation."
        ),
    },
    "MPICO": {
        "name": "MPICO PLC",
        "sector": "Real Estate",
        "description": (
            "Commercial property investment and development company managing real estate assets "
            "across major cities in Malawi."
        ),
    },
    "NBM": {
        "name": "National Bank of Malawi PLC",
        "sector": "Banking & Financial Services",
        "description": (
            "One of Malawi's oldest and largest commercial banks, a subsidiary of Press Corporation. "
            "Offers retail, corporate, and trade finance services. "
            "Grant Kabango appointed Board Chairman December 2025. Held its 53rd AGM in 2025."
        ),
    },
    "NBS": {
        "name": "NBS Bank PLC",
        "sector": "Banking & Financial Services",
        "description": (
            "Retail-focused commercial bank with a wide branch network across Malawi, "
            "serving individuals, SMEs, and corporates."
        ),
    },
    "NICO": {
        "name": "NICO Holdings PLC",
        "sector": "Insurance & Financial Services",
        "description": (
            "Diversified financial services group offering general insurance, life insurance, "
            "banking, and asset management across southern and eastern Africa."
        ),
    },
    "NITL": {
        "name": "National Investment Trust Limited",
        "sector": "Investment Trusts",
        "description": (
            "Closed-end collective investment scheme listed on the MSE. "
            "Invests in a managed portfolio of Malawian equities and fixed income instruments, "
            "providing broad market exposure for retail investors."
        ),
    },
    "OMU": {
        "name": "Old Mutual Limited",
        "sector": "Insurance & Asset Management",
        "description": (
            "Pan-African financial services group listed on multiple exchanges including the MSE. "
            "Offers long-term savings, life insurance, investment management, and retail banking."
        ),
    },
    "PCL": {
        "name": "Press Corporation Limited",
        "sector": "Conglomerate",
        "description": (
            "Malawi's largest conglomerate with major stakes in NBM (banking), "
            "Airtel Malawi (telecoms), Castel Malawi (beverages), and other sectors. "
            "Acts as a diversified proxy for the Malawian economy."
        ),
    },
    "STANDARD": {
        "name": "Standard Bank Malawi PLC",
        "sector": "Banking & Financial Services",
        "description": (
            "Part of the Standard Bank Group (Africa's largest bank by assets), offering "
            "corporate, business, and personal banking services in Malawi."
        ),
    },
    "SUNBIRD": {
        "name": "Sunbird Tourism PLC",
        "sector": "Hospitality & Tourism",
        "description": (
            "Malawi's largest hotel and hospitality group operating resorts, lakeside lodges, "
            "and conference facilities at prime tourism destinations across the country."
        ),
    },
    "TNM": {
        "name": "Telekom Networks Malawi PLC",
        "sector": "Telecommunications",
        "description": (
            "One of Malawi's two major mobile network operators providing voice, data, and digital services. "
            "Secured license renewal paving the way for 5G deployment. "
            "Ended a 19-year Super League sponsorship in January 2026 as part of a corporate strategy shift."
        ),
    },
}

_MSE_GENERAL: list[tuple[str, str, str]] = [
    (
        "mse_overview",
        (
            "The Malawi Stock Exchange (MSE) is the only securities exchange in Malawi, "
            "established in 1994 and based in Blantyre. It operates a Main Board with 16 listed equities "
            "and a Development & Enterprise Market (DEMI) for smaller companies. "
            "All prices are quoted in Malawian Kwacha (MWK). Settlement is T+5. "
            "The exchange is regulated by the Reserve Bank of Malawi."
        ),
        "MSE Exchange Overview",
    ),
    (
        "mse_trading_mechanics",
        (
            "MSE trading hours: 09:00 to 12:00 Central Africa Time (UTC+2), weekdays only. "
            "Prices quoted in Malawian Kwacha (MWK). "
            "Key metrics: open price, close price, daily change, percentage change, volume, and turnover. "
            "The MSE is a thinly traded market — volume spikes deserve close attention. "
            "Market cap = shares outstanding × current share price."
        ),
        "MSE Trading Mechanics",
    ),
    (
        "mse_investing_guidance",
        (
            "To invest on the MSE you must use a licensed stockbroker: Stockbrokers Malawi, "
            "Nico Securities, or CDH Investment Bank. "
            "Diversify across sectors (banking, telecoms, agriculture, hospitality, real estate). "
            "Monitor dividend announcements, AGM notices, and results via mse.co.mw. "
            "Factor in MWK inflation when evaluating real returns. "
            "Liquidity risk is significant — some counters trade only a few sessions per week."
        ),
        "MSE Investing Guidance",
    ),
]

_collection: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is not None:
        return _collection
    client = chromadb.EphemeralClient()
    _collection = client.get_or_create_collection(
        name="mse_knowledge",
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def _embed_documents(texts: list[str]) -> list[list[float]]:
    result = gemini_client.models.embed_content(
        model="text-embedding-004",
        contents=texts,
        config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    return [e.values for e in result.embeddings]


def _embed_query(text: str) -> list[float]:
    result = gemini_client.models.embed_content(
        model="text-embedding-004",
        contents=[text],
        config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return result.embeddings[0].values


def build_index() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        print("[RAG] GEMINI_API_KEY not set — skipping index build")
        return

    collection = _get_collection()
    if collection.count() > 0:
        return

    docs: list[str] = []
    ids: list[str] = []
    metas: list[dict] = []

    for ticker, info in MSE_COMPANIES.items():
        text = (
            f"Ticker: {ticker} | Company: {info['name']} | Sector: {info['sector']}\n"
            f"{info['description']}"
        )
        docs.append(text)
        ids.append(f"profile_{ticker}")
        metas.append({
            "ticker": ticker,
            "type": "company_profile",
            "title": f"{info['name']} Company Profile",
            "date": "",
            "url": "https://mse.co.mw",
        })

    for chunk_id, text, title in _MSE_GENERAL:
        docs.append(text)
        ids.append(chunk_id)
        metas.append({
            "ticker": "MSE",
            "type": "general",
            "title": title,
            "date": "",
            "url": "https://mse.co.mw",
        })

    if INSIGHTS_PATH.exists():
        with open(INSIGHTS_PATH) as f:
            insights: dict = json.load(f)

        for ticker, data in insights.items():
            for i, article in enumerate(data.get("articles", [])):
                text = (
                    f"Ticker: {ticker} | News: {article['title']} "
                    f"(published {article.get('date', 'unknown date')})"
                )
                docs.append(text)
                ids.append(f"article_{ticker}_{i}")
                metas.append({
                    "ticker": ticker,
                    "type": "article",
                    "title": article["title"],
                    "date": article.get("date", ""),
                    "url": article.get("url", ""),
                })

            for i, update in enumerate(data.get("trading_updates", [])):
                text = (
                    f"Ticker: {ticker} | Trading Update: {update['title']} "
                    f"({update.get('date', 'unknown date')}) — {update.get('type', '')}"
                )
                docs.append(text)
                ids.append(f"update_{ticker}_{i}")
                metas.append({
                    "ticker": ticker,
                    "type": "trading_update",
                    "title": update["title"],
                    "date": update.get("date", ""),
                    "url": "",
                })

            for i, podcast in enumerate(data.get("podcasts", [])):
                if not podcast.get("title"):
                    continue
                text = (
                    f"Ticker: {ticker} | Podcast/Media: {podcast['title']} "
                    f"({podcast.get('date', '')})"
                )
                docs.append(text)
                ids.append(f"podcast_{ticker}_{i}")
                metas.append({
                    "ticker": ticker,
                    "type": "podcast",
                    "title": podcast["title"],
                    "date": podcast.get("date", ""),
                    "url": podcast.get("url", ""),
                })

    embeddings = _embed_documents(docs)
    collection.add(documents=docs, ids=ids, metadatas=metas, embeddings=embeddings)
    print(f"[RAG] Indexed {len(docs)} chunks into vector store")


class RetrievedChunk(TypedDict):
    text: str
    ticker: str
    type: str
    title: str
    date: str
    url: str


def retrieve(query: str, top_k: int = 5) -> list[RetrievedChunk]:
    collection = _get_collection()
    if collection.count() == 0:
        return []

    query_embedding = _embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas"],
    )

    chunks: list[RetrievedChunk] = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        chunks.append(
            RetrievedChunk(
                text=doc,
                ticker=meta.get("ticker", ""),
                type=meta.get("type", ""),
                title=meta.get("title", ""),
                date=meta.get("date", ""),
                url=meta.get("url", ""),
            )
        )
    return chunks
