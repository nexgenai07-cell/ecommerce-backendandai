# PATH: apps/ai/tools/registry.py
#
# Developer A ke plain Python functions (product_tools.py) ko
# LangChain @tool format mein wrap karta hai taake agent unhe call kar sake.

from langchain_core.tools import tool

from .product_tools import (
    search_products_tool as _search_products,
    get_product_details_tool as _get_product_details,
    compare_products_tool as _compare_products,
)


@tool
def search_products(query: str, max_price: float = None, category: str = None, limit: int = 5) -> dict:
    """Search for products using a natural language query, with optional max price and category filters.
    Use this when the customer describes what they're looking for."""
    return _search_products(query, max_price, category, limit)


@tool
def get_product_details(product_id: int) -> dict:
    """Get full details (price, stock, description) of a single product by its ID.
    Use this after search_products when the customer wants more info on one item."""
    return _get_product_details(product_id)


@tool
def compare_products(product_ids: list) -> dict:
    """Compare 2 to 4 products side-by-side by their product IDs.
    Use this when the customer wants to compare multiple products."""
    return _compare_products(product_ids)


SHOPPING_AGENT_TOOLS = [search_products, get_product_details, compare_products]