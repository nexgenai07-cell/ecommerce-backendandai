# PATH: apps/ai/admin_tools/analytics_tools.py
#
# Analytics Agent ke tools — Day 1 STUBS. Sab read-only hain, isliye
# confirmation gating ki zaroorat nahi.

def sales_report_tool(date_range: str = "last_30_days") -> dict:
    """STUB — Day 4."""
    return {'success': True, 'date_range': date_range, 'summary': {}, 'totals': {}}


def revenue_report_tool(date_range: str = "last_30_days") -> dict:
    """STUB — Day 4."""
    return {'success': True, 'date_range': date_range, 'revenue_breakdown': {}}


def best_sellers_tool(date_range: str = "last_30_days", limit: int = 5) -> dict:
    """STUB — Day 4."""
    return {'success': True, 'date_range': date_range, 'best_sellers': []}


def customer_growth_tool(date_range: str = "last_30_days") -> dict:
    """STUB — Day 4."""
    return {'success': True, 'date_range': date_range, 'new_customers': 0, 'retention': None}