# PATH: apps/ai/admin_tools/analytics_tools.py
#
# Analytics Agent ke tools — Day 4 REAL implementation. Sab read-only
# hain, isliye confirmation gating ki zaroorat nahi (jaisa PDF section
# 4.2 mein hai). Har tool apps/analytics ke maujooda Django REST
# endpoints ko HTTP se call karta hai (call_internal_api se) — koi
# direct DB/ORM access nahi, jaisa doc section 5 ka requirement hai
# ("Every tool is a thin, validated wrapper around an existing Django
# REST endpoint").
#
# Tool ka input 'date_range' ek human-friendly keyword hai (jaisa PDF
# section 6 Day 1 contract mein diya gaya, e.g. "last_30_days"), lekin
# asal endpoints start_date/end_date/period query params expect karte
# hain — is liye _resolve_date_range() us translation ka kaam karta hai.

from datetime import date, timedelta

from apps.ai.admin_tools.api_client import call_internal_api

_SUPPORTED_RANGES = (
    'today', 'yesterday', 'last_7_days', 'last_30_days', 'last_90_days',
    'this_month', 'last_month', 'this_year', 'all_time',
)


def _resolve_date_range(date_range: str):
    """
    'date_range' keyword ko (start_date, end_date) ISO strings mein
    convert karta hai. Na-pehchana-gaya keyword bhi silently
    'last_30_days' pe fallback ho jata hai (agent ko crash na kare).
    Returns (start_date_str_or_None, end_date_str_or_None).
    """
    today = date.today()
    key = (date_range or 'last_30_days').strip().lower()

    if key == 'today':
        start = end = today
    elif key == 'yesterday':
        start = end = today - timedelta(days=1)
    elif key == 'last_7_days':
        start, end = today - timedelta(days=7), today
    elif key == 'last_90_days':
        start, end = today - timedelta(days=90), today
    elif key == 'this_month':
        start, end = today.replace(day=1), today
    elif key == 'last_month':
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        start, end = last_month_end.replace(day=1), last_month_end
    elif key == 'this_year':
        start, end = today.replace(month=1, day=1), today
    elif key == 'all_time':
        return None, None
    else:
        # covers 'last_30_days' aur koi bhi unrecognized value
        start, end = today - timedelta(days=30), today

    return start.isoformat(), end.isoformat()


def sales_report_tool(user, date_range: str = "last_30_days") -> dict:
    """GET /api/v1/analytics/sales/ — order count + revenue, daily grouped."""
    start_date, end_date = _resolve_date_range(date_range)
    params = {'period': 'daily'}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    result = call_internal_api(user, 'GET', '/api/v1/analytics/sales/', params=params)
    if not result['success']:
        return {'success': False, 'error': result['error']}

    rows = (result['data'] or {}).get('data', [])
    total_orders = sum(r.get('total_orders', 0) or 0 for r in rows)
    total_revenue = sum(r.get('total_revenue', 0) or 0 for r in rows)

    return {
        'success': True,
        'date_range': date_range,
        'summary': {'days_with_data': len(rows), 'daily_breakdown': rows},
        'totals': {'total_orders': total_orders, 'total_revenue': total_revenue},
    }


def revenue_report_tool(user, date_range: str = "last_30_days") -> dict:
    """GET /api/v1/analytics/revenue/ — revenue grouped by period (cancelled orders excluded)."""
    start_date, end_date = _resolve_date_range(date_range)
    params = {'period': 'daily'}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    result = call_internal_api(user, 'GET', '/api/v1/analytics/revenue/', params=params)
    if not result['success']:
        return {'success': False, 'error': result['error']}

    rows = (result['data'] or {}).get('data', [])
    total_revenue = sum(r.get('revenue', 0) or 0 for r in rows)

    return {
        'success': True,
        'date_range': date_range,
        'revenue_breakdown': {'by_period': rows, 'total_revenue': total_revenue},
    }


def best_sellers_tool(user, date_range: str = "last_30_days", limit: int = 5) -> dict:
    """GET /api/v1/analytics/products/best-sellers/ — top products by units sold."""
    start_date, end_date = _resolve_date_range(date_range)
    params = {'limit': limit}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    result = call_internal_api(user, 'GET', '/api/v1/analytics/products/best-sellers/', params=params)
    if not result['success']:
        return {'success': False, 'error': result['error'], 'best_sellers': []}

    rows = result['data'] or []
    best_sellers = [
        {
            'product_id': r.get('product_id'),
            'name': r.get('product_name'),
            'units_sold': r.get('total_sold'),
            'revenue': r.get('total_revenue'),
        }
        for r in rows
    ]

    return {'success': True, 'date_range': date_range, 'best_sellers': best_sellers}


def customer_growth_tool(user, date_range: str = "last_30_days") -> dict:
    """
    GET /api/v1/analytics/customers/growth/ — new customer count per period.
    Note: 'retention' (PDF output field) is not tracked anywhere in the
    database (no repeat-purchase/cohort table exists) — same kind of gap
    as order status-history noted in order_tools.py. Returned as None
    with an explanatory note rather than a made-up number.
    """
    start_date, end_date = _resolve_date_range(date_range)
    params = {'period': 'daily'}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    result = call_internal_api(user, 'GET', '/api/v1/analytics/customers/growth/', params=params)
    if not result['success']:
        return {'success': False, 'error': result['error']}

    rows = result['data'] or []
    total_new_customers = sum(r.get('new_customers', 0) or 0 for r in rows)

    return {
        'success': True,
        'date_range': date_range,
        'new_customers': total_new_customers,
        'by_period': rows,
        'retention': None,
        'note': 'Retention is not tracked in the database yet — only new-customer counts are available.',
    }