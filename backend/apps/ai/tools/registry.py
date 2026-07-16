# PATH: apps/ai/tools/registry.py

from typing import Optional
from langchain_core.tools import tool

from .product_tools import (
    search_products_tool as _search_products,
    get_product_details_tool as _get_product_details,
    compare_products_tool as _compare_products,
)
from .faq_tools import answer_faq_tool as _answer_faq


@tool
def search_products(query: str, max_price: Optional[float] = None, category: Optional[str] = None, limit: Optional[int] = 5) -> dict:
    """Search for products using a natural language query, with optional max price and category filters.
    Use this when the customer describes what they're looking for."""
    if limit is None:
        limit = 5
    return _search_products(query, max_price, category, limit)


@tool
def get_product_details(product_id: int) -> dict:
    """Get full details (price, stock, description) of a single product by its ID."""
    return _get_product_details(product_id)


@tool
def compare_products(product_ids: list) -> dict:
    """Compare 2 to 4 products side-by-side by their product IDs."""
    return _compare_products(product_ids)


@tool
def answer_faq(query: str) -> dict:
    """Search the store's FAQ knowledge base for policy and general questions."""
    return _answer_faq(query)


SHOPPING_AGENT_TOOLS = [search_products, get_product_details, compare_products, answer_faq]