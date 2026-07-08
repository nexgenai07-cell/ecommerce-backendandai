# PATH: apps/products/admin.py

from django.contrib import admin
from .models import Product, ProductImage, ProductHistory, Discount, ProductDiscount, ProductStats


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'sku', 'price', 'original_price', 'stock', 'is_active', 'category', 'store']
    search_fields = ['name', 'sku']
    list_filter = ['is_active', 'category', 'store']
    inlines = [ProductImageInline]


@admin.register(ProductHistory)
class ProductHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'old_price', 'new_price', 'old_stock', 'new_stock', 'changed_by', 'created_at']
    list_filter = ['created_at']


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ['id', 'code', 'type', 'value', 'is_active', 'start_date', 'end_date']
    search_fields = ['code']
    list_filter = ['is_active', 'type']


admin.site.register(ProductDiscount)
admin.site.register(ProductStats)