# PATH: apps/ai/tools/product_tools.py
#
# Ye tools AI agent ke liye hain.
# Har tool Django APIs ya Qdrant ko call karta hai — directly DB touch nahi karta.
# BE2 in tools ko LangChain agent mein register karega.

import requests
from django.conf import settings
from qdrant_client import QdrantClient

from apps.ai.gemini_utils import gemini_keys, is_quota_error


def get_qdrant_client():
    """Qdrant client — har tool use karta hai ise"""
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )


def get_query_embedding(text):
    """
    User ki query ko vector mein convert karta hai — retry/fallback ke sath
    (429 par key rotate, 503 overload par samei key se dobara try).
    """
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


def search_products_tool(query: str, max_price: float = None, category: str = None, limit: int = 5) -> dict:
    """
    TOOL: search_products_tool

    User ki natural language query se Qdrant mein semantic search karta hai.
    Ye normal keyword search se better hai — "affordable phone with good camera"
    jaisi query bhi sahi results deta hai, exact word match ki zaroorat nahi.

    Args:
        query:     User ki search query — jaise "Samsung phone under 50000"
        max_price: Maximum price filter (optional) — jaise 50000.0
        category:  Category filter (optional) — jaise "Electronics"
        limit:     Kitne results chahiye (default 5)

    Returns:
        dict with 'products' list and 'total_found' count
    """
    try:
        qdrant = get_qdrant_client()

        # Step 1: Query ko vector mein convert karo
        query_vector = get_query_embedding(query)

        # Step 2: Qdrant mein similar products dhundo
        # qdrant-client ki nayi version mein .search() hata diya gaya hai,
        # ab .query_points() use hota hai — result .points attribute mein aata hai
        search_response = qdrant.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=query_vector,
            limit=limit * 3,  # zyada fetch karo — filters ke baad bhi enough milein
            score_threshold=0.3,
            with_payload=True,
        )
        search_results = search_response.points

        # Step 3: Client-side filters apply karo (price, category)
        products = []
        for result in search_results:
            payload = result.payload

            # Price filter
            if max_price and payload.get('price', 0) > max_price:
                continue

            # Category filter (case-insensitive)
            if category and payload.get('category', '').lower() != category.lower():
                continue

            products.append({
                'product_id':     payload['product_id'],
                'name':           payload['name'],
                'category':       payload.get('category'),
                'category_id':    payload.get('category_id'),
                'price':          payload['price'],
                'original_price': payload.get('original_price'),
                'in_stock':       payload.get('in_stock', True),
                'stock':          payload.get('stock', 0),
                'description':    payload.get('description', ''),
                'image':          payload.get('image'),
                'relevance_score': round(result.score, 3),
            })

            if len(products) >= limit:
                break

        return {
            'success': True,
            'products': products,
            'total_found': len(products),
            'query': query,
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'products': [],
            'total_found': 0,
        }


def get_product_details_tool(product_id: int) -> dict:
    """
    TOOL: get_product_details_tool

    Ek specific product ki poori detail deta hai.
    Django API se real-time data fetch karta hai (price/stock live hoga).

    Args:
        product_id: Product ka ID (Qdrant search results mein milta hai)

    Returns:
        dict with full product details
    """
    try:
        base_url = getattr(settings, 'INTERNAL_API_URL', 'http://localhost:8000')
        response = requests.get(f'{base_url}/api/v1/products/{product_id}/')

        if response.status_code == 200:
            product = response.json()
            return {
                'success': True,
                'product': product,
            }
        elif response.status_code == 404:
            return {'success': False, 'error': 'Product not found.'}
        else:
            return {'success': False, 'error': f'API error: {response.status_code}'}

    except Exception as e:
        return {'success': False, 'error': str(e)}


def compare_products_tool(product_ids: list) -> dict:
    """
    TOOL: compare_products_tool

    2 ya zyada products ki side-by-side comparison karta hai.
    AI is data ko use karke user-friendly comparison generate karta hai.

    Args:
        product_ids: List of product IDs — jaise [1, 2] ya [1, 2, 3]

    Returns:
        dict with comparison data for each product
    """
    if len(product_ids) < 2:
        return {'success': False, 'error': 'At least 2 product IDs required for comparison.'}

    if len(product_ids) > 4:
        return {'success': False, 'error': 'Maximum 4 products can be compared at once.'}

    products = []
    errors = []

    for pid in product_ids:
        result = get_product_details_tool(pid)
        if result['success']:
            products.append(result['product'])
        else:
            errors.append(f'Product {pid}: {result["error"]}')

    if not products:
        return {'success': False, 'error': 'No products found.', 'errors': errors}

    comparison = {
        'success': True,
        'products': products,
        'comparison_fields': ['name', 'price', 'original_price', 'stock', 'category'],
        'errors': errors if errors else None,
    }

    return comparison