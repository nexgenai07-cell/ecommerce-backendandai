from django.contrib import admin
from .models import Customer, Order, OrderItem, Payment
from apps.returns.models import Return, Complaint

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
    
    
@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "customer",
        "status",
        "created_at",
    )

    list_filter = ("status", "created_at")
    search_fields = ("order__order_number", "customer__name")
    
@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "customer",
        "type",
        "status",
        "created_at",
    )

    list_filter = ("type", "status", "created_at")
    search_fields = ("order__order_number", "customer__name")