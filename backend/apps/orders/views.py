import random
import string

from django.db import transaction
from django.utils import timezone

from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response

from core.pagination import StandardResultsPagination
from apps.notifications.utils import create_notification

from .models import Customer, Order, OrderItem, Payment
from .serializers import (
    OrderListSerializer,
    OrderDetailSerializer,
    CheckoutSerializer,
    AdminOrderStatusSerializer,
)

from apps.cart.models import Cart
from apps.users.permissions import IsAdmin


def generate_order_number():
    year = timezone.now().year
    last_order = (
        Order.objects.filter(order_number__startswith=f"ORD-{year}-")
        .order_by("-id")
        .first()
    )

    if last_order:
        last_seq = int(last_order.order_number.split("-")[-1])
        new_seq = last_seq + 1
    else:
        new_seq = 1

    return f"ORD-{year}-{new_seq:05d}"


def get_or_create_customer(user, store_id=1):
    customer, _ = Customer.objects.get_or_create(
        user=user,
        store_id=store_id,
        defaults={
            "name": user.name,
            "phone": user.phone or "",
            "email": user.email,
        },
    )
    return customer


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cart = Cart.objects.filter(user=request.user).first()

        if not cart or not cart.items.exists():
            return Response(
                {"error": "Your cart is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():

            cart_items = list(
                cart.items.select_related("product")
                .select_for_update()
                .all()
            )

            out_of_stock = []

            for item in cart_items:
                product = item.product

                if product.stock < item.quantity:
                    out_of_stock.append(product.name)

            if out_of_stock:
                return Response(
                    {
                        "error": (
                            "These items are no longer available "
                            f"in the requested quantity: {', '.join(out_of_stock)}"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            subtotal = sum(
                item.product.price * item.quantity
                for item in cart_items
            )

            discount_amount = 0

            if cart.coupon:
                if cart.coupon.type == "percent":
                    discount_amount = (
                        subtotal * cart.coupon.value
                    ) / 100
                else:
                    discount_amount = cart.coupon.value

                discount_amount = min(
                    discount_amount,
                    subtotal,
                )

            total_amount = subtotal - discount_amount

            customer = get_or_create_customer(
                request.user,
                store_id=cart.store_id,
            )

            order = Order.objects.create(
                store_id=cart.store_id,
                customer=customer,
                order_number=generate_order_number(),
                total_amount=total_amount,
                discount_amount=discount_amount,
                status="pending",
                payment_method=data["payment_method"],
                shipping_address=data["shipping_address"],
                notes=data.get("notes", ""),
            )

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    price=item.product.price,
                    quantity=item.quantity,
                    total_price=item.product.price * item.quantity,
                )

                item.product.stock -= item.quantity
                item.product.save()

            Payment.objects.create(
                order=order,
                method=data["payment_method"],
                status="pending",
                amount=total_amount,
            )

            cart.items.all().delete()
            cart.coupon = None
            cart.save()

        create_notification(
        user=request.user,
        title="Order Confirmed",
        message=f"Your order #{order.order_number} has been placed successfully.",
        notification_type="order",
)

        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class OrderListView(generics.ListAPIView):
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return (
            Order.objects.filter(
                customer__user=self.request.user
            )
            .order_by("-created_at")
        )


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "order_number"

    def get_queryset(self):
        return Order.objects.filter(
            customer__user=self.request.user
        )
        
        
class OrderCancelView(APIView):
    """PUT /api/v1/orders/{order_number}/cancel/"""
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, order_number):
        try:
            order = Order.objects.get(
                order_number=order_number,
                customer__user=request.user,
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.status == "delivered":
            return Response(
                {"error": "Delivered orders cannot be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.status == "cancelled":
            return Response(
                {"error": "Order is already cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for item in order.items.all():
                if item.product:
                    item.product.stock += item.quantity
                    item.product.save()

            order.status = "cancelled"
            order.save()

            if hasattr(order, "payment"):
                order.payment.status = "refunded"
                order.payment.save()

        return Response(OrderDetailSerializer(order).data)


class OrderTrackView(APIView):
    """GET /api/v1/orders/{order_number}/track/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_number):
        try:
            order = Order.objects.get(
                order_number=order_number,
                customer__user=request.user,
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "order_number": order.order_number,
                "status": order.status,
                "tracking_number": order.tracking_number,
                "updated_at": order.updated_at,
            }
        )


# ============================================================
# ADMIN VIEWS
# ============================================================

class AdminOrderListView(generics.ListAPIView):
    """GET /api/v1/admin/orders/"""
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return Order.objects.all().order_by("-created_at")


class AdminOrderStatusUpdateView(APIView):
    """PUT /api/v1/admin/orders/{order_number}/status/"""
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def put(self, request, order_number):
        try:
            order = Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]

        if order.status == "delivered" and new_status == "cancelled":
            return Response(
                {"error": "Delivered orders cannot be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status == "cancelled" and order.status != "cancelled":
            with transaction.atomic():
                for item in order.items.all():
                    if item.product:
                        item.product.stock += item.quantity
                        item.product.save()

                if hasattr(order, "payment"):
                    order.payment.status = "refunded"
                    order.payment.save()

        order.status = new_status

        if (
            "tracking_number" in serializer.validated_data
            and serializer.validated_data["tracking_number"]
        ):
            order.tracking_number = serializer.validated_data[
                "tracking_number"
            ]

        order.save()

        status_titles = {
            "pending": "Order Pending",
            "confirmed": "Order Confirmed",
            "processing": "Order Processing",
            "shipped": "Order Shipped",
            "delivered": "Order Delivered",
            "cancelled": "Order Cancelled",
        }

        status_messages = {
            "pending": f"Your order #{order.order_number} is pending.",
            "confirmed": f"Your order #{order.order_number} has been confirmed.",
            "processing": f"Your order #{order.order_number} is being prepared.",
            "shipped": f"Your order #{order.order_number} is on its way.",
            "delivered": f"Your order #{order.order_number} has been delivered.",
            "cancelled": f"Your order #{order.order_number} has been cancelled.",
        }

        create_notification(
        user=order.customer.user,
        store=order.store,
        title=status_titles.get(new_status, "Order Update"),
        message=status_messages.get(
        new_status,
        f"Your order #{order.order_number} has been updated.",
    ),
        notification_type="order",
)

        return Response(OrderDetailSerializer(order).data)
    
class AdminOrderFilterView(generics.ListAPIView):
    """
    GET /api/v1/admin/orders/filter/?status=&start_date=&end_date=&customer_name=&order_number=
    """
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        qs = Order.objects.all().order_by("-created_at")
        params = self.request.query_params

        if params.get("status"):
            qs = qs.filter(status=params["status"])

        if params.get("start_date"):
            qs = qs.filter(created_at__date__gte=params["start_date"])

        if params.get("end_date"):
            qs = qs.filter(created_at__date__lte=params["end_date"])

        if params.get("customer_name"):
            qs = qs.filter(
                customer__name__icontains=params["customer_name"]
            )

        if params.get("order_number"):
            qs = qs.filter(
                order_number__icontains=params["order_number"]
            )

        return qs