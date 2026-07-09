# PATH: core/pagination.py
#
# WHY THIS FILE EXISTS:
# Poore project mein kahin DEFAULT_PAGINATION_CLASS set nahi thi, isliye
# jo endpoints doc mein {count, next, previous, results} shape promise
# karte hain (Products list, Products search, My Orders, Admin Orders,
# Admin Orders filter, List Returns, List Complaints) — sab plain array
# ya sirf {count, results} bhej rahe the.
#
# FIX STRATEGY: Hum ye pagination class GLOBALLY (settings.py mein)
# nahi laga rahe — kyunke bohat sare endpoints (Categories, Discounts,
# Notifications, Admin Customers, WhatsApp logs, Behavior records, etc.)
# ki API doc khud kehti hai response ek PLAIN ARRAY hoga, koi wrapper
# nahi. Agar hum globally pagination on kar dete to un sab endpoints ko
# bhi zabardasti {count, results} mein wrap kar deta aur unke frontend
# integrations tootna shuru ho jate jahan already plain array expect ho
# raha hai.
#
# Isliye ye class sirf un specific views mein `pagination_class =
# StandardResultsPagination` likh kar manually attach ki gayi hai jinke
# doc mein pagination explicitly documented hai:
#   - apps/products/views.py      -> ProductViewSet (list + search)
#   - apps/orders/views.py        -> OrderListView, AdminOrderListView,
#                                     AdminOrderFilterView
#   - apps/orders/return_views.py -> ReturnListView
#   - apps/orders/complaint_views.py -> CreateComplaintView (its GET/list)
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsPagination(PageNumberPagination):
    """
    Used where the doc explicitly documents next/previous in the shape:
    Products (List/Search), Returns (List), Complaints (List).
    """
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        # FIX (Postman testing — 09 Jul 2026): doc har jagah jahan
        # pagination promise karta hai (List Returns, List Complaints,
        # Admin Orders, etc.) {count, next, previous, results} shape
        # expect karta hai. Pehle sirf count + results return ho rahe
        # the — next/previous keys hi missing thi. Ab dono add ki gayi
        # hain (get_next_link/get_previous_link DRF ke
        # PageNumberPagination ke built-in helpers hain, aage/peechay
        # page na ho to None return karte hain).
        return Response({
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data
        })


class CountResultsPagination(PageNumberPagination):
    """
    NEW (Postman testing — 09 Jul 2026): doc explicitly documents ONLY
    {count, results} for these endpoints — no next/previous keys at all:
      - API 53 List My Orders        (apps/orders/views.py -> OrderListView)
      - API 57 Admin List All Orders (apps/orders/views.py -> AdminOrderListView)
      - API 58 Admin Filter Orders   (apps/orders/views.py -> AdminOrderFilterView)
    Using the same StandardResultsPagination class here would add
    next/previous keys that the doc doesn't ask for, so a separate,
    leaner class is used instead.
    """
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "results": data
        })