from django import forms
from django.urls import reverse
from django.utils.html import format_html
from django.contrib import admin
from .models import Product, ProductImage, ProductHistory, Discount, ProductDiscount, ProductStats


class ProductImageInlineForm(forms.ModelForm):
    image_upload = forms.ImageField(required=False, label='Upload Image')

    class Meta:
        model = ProductImage
        fields = ['is_primary']

    def save(self, commit=True):
        instance = super().save(commit=False)
        upload = self.cleaned_data.get('image_upload')
        if upload:
            instance.image_data = upload.read()
            instance.image_name = upload.name
            instance.image_content_type = upload.content_type
        if commit:
            instance.save()
        return instance


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageInlineForm
    extra = 1
    fields = ['image_preview', 'image_upload', 'is_primary']
    readonly_fields = ['image_preview']

    def image_preview(self, obj):
        if obj.pk and obj.image_data:
            url = reverse('product-image', args=[obj.pk])
            return format_html('<img src="{}" style="max-height:80px;"/>', url)
        return "(no image yet)"
    image_preview.short_description = "Preview"


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