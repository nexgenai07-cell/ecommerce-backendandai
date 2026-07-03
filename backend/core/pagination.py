# PATH: core/pagination.py
# NEW FILE.
#
# WHY THIS FILE EXISTS:
# Poore project mein kahin DEFAULT_PAGINATION_CLASS set nahi thi, isliye
# jo endpoints doc mein {count, next, previous, results} shape promise
# karte hain (Products list, Products search, My Orders, Admin Orders,
# Admin Orders filter) — sab plain array bhej rahe the.
#
# FIX STRATEGY: Hum ye pagination class GLOBALLY (settings.py mein)
# nahi laga rahe — kyunke bohat sare endpoints (Categories, Discounts,
# Returns, Complaints, Notifications, Admin Customers, WhatsApp logs,
# Behavior records, etc.) ki API doc khud kehti hai response ek PLAIN
# ARRAY hoga, koi wrapper nahi. Agar hum globally pagination on kar dete
# to un sab endpoints ko bhi zabardasti {count, results} mein wrap kar
# deta aur unke frontend integrations tootna shuru ho jate jahan already
# plain array expect ho raha hai.
#
# Isliye ye class sirf un specific views mein `pagination_class =
# StandardResultsPagination` likh kar manually attach ki gayi hai jinke
# doc mein pagination explicitly documented hai:
#   - apps/products/views.py      -> ProductViewSet (list + search)
#   - apps/orders/views.py        -> OrderListView, AdminOrderListView,
#                                     AdminOrderFilterView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "results": data
        })