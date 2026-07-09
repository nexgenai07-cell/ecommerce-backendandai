# PATH: apps/analytics/dashboard_views.py

from datetime import timedelta
from django.core.cache import cache
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.orders.models import Order, OrderItem, Customer
from apps.products.models import Product
from apps.users.permissions import IsAdmin


def parse_date_range(request):
    """Shared helper — reads ?start_date=&end_date=&period= from query params"""
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    period = request.query_params.get('period', 'daily')
    return start_date, end_date, period


def filter_orders_by_date(qs, start_date, end_date):
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)
    return qs


class DashboardView(APIView):
    """
    GET /api/v1/analytics/dashboard/

    High-level summary cards for the admin dashboard homepage.
    Cached for 5 minutes since this is called frequently but changes slowly.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        cache_key = 'analytics_dashboard'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        prev_30_days = last_30_days - timedelta(days=30)

        delivered_orders = Order.objects.exclude(status='cancelled')

        total_revenue = delivered_orders.aggregate(total=Sum('total_amount'))['total'] or 0
        total_orders = Order.objects.count()
        total_customers = Customer.objects.count()
        total_products = Product.objects.filter(is_active=True).count()

        this_period_revenue = delivered_orders.filter(
            created_at__date__gte=last_30_days
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        prev_period_revenue = delivered_orders.filter(
            created_at__date__gte=prev_30_days, created_at__date__lt=last_30_days
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        this_period_orders = Order.objects.filter(created_at__date__gte=last_30_days).count()
        prev_period_orders = Order.objects.filter(
            created_at__date__gte=prev_30_days, created_at__date__lt=last_30_days
        ).count()

        def growth_pct(current, previous):
            if previous == 0:
                return '+0%' if current == 0 else '+100%'
            pct = ((current - previous) / previous) * 100
            sign = '+' if pct >= 0 else ''
            return f'{sign}{pct:.0f}%'

        today_revenue = delivered_orders.filter(created_at__date=today).aggregate(total=Sum('total_amount'))['total'] or 0
        today_orders = Order.objects.filter(created_at__date=today).count()

        pending_orders = Order.objects.filter(status='pending').count()
        low_stock_products = Product.objects.filter(is_active=True).count()
        low_stock_products = sum(1 for p in Product.objects.filter(is_active=True) if p.stock <= p.low_stock_threshold)

        data = {
            'total_revenue': total_revenue,
            'total_orders': total_orders,
            'total_customers': total_customers,
            'total_products': total_products,
            'revenue_growth': growth_pct(this_period_revenue, prev_period_revenue),
            'orders_growth': growth_pct(this_period_orders, prev_period_orders),
            'pending_orders': pending_orders,
            'low_stock_products': low_stock_products,
            'today_revenue': today_revenue,
            'today_orders': today_orders,
        }

        cache.set(cache_key, data, timeout=300)  # 5 minutes
        return Response(data)


class SalesReportView(APIView):
    """
    GET /api/v1/analytics/sales/?start_date=&end_date=&period=daily|weekly|monthly
    Returns order counts grouped by the requested period — used for bar/line charts.

    FIX (Postman testing — 09 Jul 2026): doc (API 83) expects
    {"period": "daily", "data": [{"date": "", "total_orders": 10,
    "total_revenue": 150000}]}. Previously this returned a bare array
    with field names order_count/revenue/period per row — missing the
    outer {period, data} wrapper and using the wrong inner field names.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        start_date, end_date, period = parse_date_range(request)
        qs = filter_orders_by_date(Order.objects.all(), start_date, end_date)

        trunc_fn = {'daily': TruncDate, 'weekly': TruncWeek, 'monthly': TruncMonth}.get(period, TruncDate)

        rows = (
            qs.annotate(bucket=trunc_fn('created_at'))
              .values('bucket')
              .annotate(total_orders=Count('id'), total_revenue=Sum('total_amount'))
              .order_by('bucket')
        )

        data = [
            {
                'date': row['bucket'],
                'total_orders': row['total_orders'],
                'total_revenue': row['total_revenue'] or 0,
            }
            for row in rows
        ]

        return Response({
            'period': period,
            'data': data,
        })


class RevenueReportView(APIView):
    """
    GET /api/v1/analytics/revenue/?start_date=&end_date=&period=daily|weekly|monthly
    Same grouping as sales, focused purely on revenue figures.

    FIX (Postman testing — 09 Jul 2026): doc (API 84) expects
    {"data": [{"period": "2024-01", "revenue": 1500000}]}. Previously
    this returned a bare array — the outer {"data": [...]} wrapper was
    missing (inner field names period/revenue were already correct).
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        start_date, end_date, period = parse_date_range(request)
        qs = filter_orders_by_date(Order.objects.exclude(status='cancelled'), start_date, end_date)

        trunc_fn = {'daily': TruncDate, 'weekly': TruncWeek, 'monthly': TruncMonth}.get(period, TruncDate)

        data = (
            qs.annotate(period=trunc_fn('created_at'))
              .values('period')
              .annotate(revenue=Sum('total_amount'))
              .order_by('period')
        )

        return Response({
            'data': list(data),
        })


class OrdersAnalyticsView(APIView):
    """
    GET /api/v1/analytics/orders/?start_date=&end_date=
    Returns order counts broken down by status — used for the status pie/bar chart.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        start_date, end_date, _ = parse_date_range(request)
        qs = filter_orders_by_date(Order.objects.all(), start_date, end_date)

        breakdown = qs.values('status').annotate(count=Count('id')).order_by('status')

        return Response({
            'total': qs.count(),
            'by_status': list(breakdown),
        })


class BestSellersView(APIView):
    """GET /api/v1/analytics/products/best-sellers/?start_date=&end_date=&limit=5"""
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        limit = int(request.query_params.get('limit', 5))

        qs = OrderItem.objects.exclude(order__status='cancelled')
        if start_date:
            qs = qs.filter(order__created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(order__created_at__date__lte=end_date)

        data = (
            qs.values('product_id', 'product_name')
              .annotate(total_sold=Sum('quantity'), total_revenue=Sum('total_price'))
              .order_by('-total_sold')[:limit]
        )

        return Response(list(data))


class LowPerformingProductsView(APIView):
    """GET /api/v1/analytics/products/low-performing/?limit=5 — least sold active products"""
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        limit = int(request.query_params.get('limit', 5))

        sold_product_ids = (
            OrderItem.objects.exclude(order__status='cancelled')
            .values('product_id')
            .annotate(total_sold=Sum('quantity'))
        )
        sold_map = {row['product_id']: row['total_sold'] for row in sold_product_ids}

        products = Product.objects.filter(is_active=True)
        ranked = sorted(products, key=lambda p: sold_map.get(p.id, 0))[:limit]

        data = [
            {
                'product_id': p.id,
                'name': p.name,
                'total_sold': sold_map.get(p.id, 0),
                'stock': p.stock,
            }
            for p in ranked
        ]

        return Response(data)


class CustomerGrowthView(APIView):
    """GET /api/v1/analytics/customers/growth/?start_date=&end_date=&period=daily|weekly|monthly"""
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        start_date, end_date, period = parse_date_range(request)
        qs = Customer.objects.all()
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)

        trunc_fn = {'daily': TruncDate, 'weekly': TruncWeek, 'monthly': TruncMonth}.get(period, TruncDate)

        data = (
            qs.annotate(period=trunc_fn('created_at'))
              .values('period')
              .annotate(new_customers=Count('id'))
              .order_by('period')
        )

        return Response(list(data))


class InventoryAlertsView(APIView):
    """GET /api/v1/analytics/inventory/alerts/ — active products at/below their low stock threshold"""
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        products = Product.objects.filter(is_active=True)
        alerts = [
            {'product_id': p.id, 'name': p.name, 'stock': p.stock, 'threshold': p.low_stock_threshold}
            for p in products if p.stock <= p.low_stock_threshold
        ]
        return Response(alerts)


class AnalyticsExportView(APIView):
    """
    GET /api/v1/analytics/export/?start_date=&end_date=
    Returns a CSV file of orders within the date range.
    NOTE: For large datasets this should move to a Celery background task
    that emails/links the file instead of generating it synchronously.

    FIX (Postman testing — 09 Jul 2026): crashed with AttributeError
    because Order has no `payment_method` field — payment info lives on
    the related Payment model (order.payment), which may not even exist
    for every order (e.g. cancelled/unpaid orders). Now reads the
    payment status safely via hasattr, falling back to "N/A", and drops
    the non-existent payment_method column from the CSV header/rows.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        import csv
        from django.http import HttpResponse

        start_date, end_date, _ = parse_date_range(request)
        qs = filter_orders_by_date(Order.objects.all(), start_date, end_date)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders_export.csv"'

        writer = csv.writer(response)
        writer.writerow(['Order Number', 'Customer', 'Total Amount', 'Status', 'Payment Status', 'Created At'])

        for order in qs.select_related('customer', 'payment'):
            payment_status = order.payment.status if hasattr(order, 'payment') and order.payment else 'N/A'
            writer.writerow([
                order.order_number, order.customer.name, order.total_amount,
                order.status, payment_status, order.created_at,
            ])

        return response