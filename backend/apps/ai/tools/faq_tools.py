# PATH: apps/ai/tools/faq_tools.py
#
# Support Agent tool — FAQ knowledge base (Qdrant) se semantic search
# kar k relevant Q&A chunks return karta hai. Ye "RAG" pattern hai:
# AI khud jawab nahi banata, pehle relevant document chunks retrieve
# karta hai, phir unhi ke basis pe natural jawab deta hai (hallucination
# se bachne k liye).

import requests
from django.conf import settings
from qdrant_client import QdrantClient

from apps.ai.gemini_utils import gemini_keys, is_quota_error

FAQ_COLLECTION = "faq_knowledge"


def _get_qdrant_client():
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)


def _get_faq_query_embedding(text):
    """taskType='RETRIEVAL_QUERY' — retry/fallback ke sath."""
    from apps.ai.gemini_utils import call_with_fallback

    def attempt():
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={gemini_keys.current_key}',
            json={
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": text}]},
                "taskType": "RETRIEVAL_QUERY"
            }
        )
        result = response.json()
        if 'error' in result:
            raise Exception(f"Embedding error: {result['error']['message']}")
        return result['embedding']['values']

    return call_with_fallback(attempt)


def answer_faq_tool(query: str, limit: int = 3) -> dict:
    """
    TOOL: answer_faq_tool

    Store ki FAQ knowledge base (shipping, returns, payments, orders,
    account policies) mein customer ke sawal se semantic search karta hai.
    Use this for policy/general questions — NOT for live product search,
    prices, or order-specific tracking (those have their own tools).

    Args:
        query: Customer ka sawal — jaise "return kaise karun" ya "cash on delivery hai?"
        limit: Kitne relevant FAQ entries chahiye (default 3)

    Returns:
        dict with matching FAQ entries (question + answer pairs)
    """
    try:
        qdrant = _get_qdrant_client()
        query_vector = _get_faq_query_embedding(query)

        search_response = qdrant.query_points(
            collection_name=FAQ_COLLECTION,
            query=query_vector,
            limit=limit,
            score_threshold=0.3,
            with_payload=True,
        )

        results = [
            {
                'question': r.payload['question'],
                'answer': r.payload['answer'],
                'source_document': r.payload.get('document_title'),
                'relevance_score': round(r.score, 3),
            }
            for r in search_response.points
        ]

        return {
            'success': True,
            'results': results,
            'found': len(results),
        }

    except Exception as e:
        return {'success': False, 'error': str(e), 'results': [], 'found': 0}