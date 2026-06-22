from django.contrib import admin
from .models import Customer, Order, OrderItem, Payment


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'name',
        'phone',
        'email',
        'store',
        'created_at',
    ]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'order_number',
        'customer',
        'store',
        'total_amount',
        'status',
        'payment_method',
        'created_at',
    ]

    list_filter = [
        'status',
        'payment_method',
        'created_at',
    ]

    search_fields = [
        'order_number',
        'customer__name',
        'customer__phone',
    ]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'order',
        'product_name',
        'quantity',
        'price',
        'total_price',
    ]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'order',
        'method',
        'status',
        'amount',
        'created_at',
    ]