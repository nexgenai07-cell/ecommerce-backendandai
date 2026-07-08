# PATH: apps/products/models.py

from django.db import models
from django.conf import settings


class Product(models.Model):
    store       = models.ForeignKey('stores.Store',      on_delete=models.CASCADE,  related_name='products')
    category    = models.ForeignKey('categories.Category', on_delete=models.SET_NULL, related_name='products', null=True, blank=True)
    name        = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # original/crossed price
    stock       = models.PositiveIntegerField(default=0)
    sku         = models.CharField(max_length=100, unique=True)
    is_active   = models.BooleanField(default=True)
    publish_at           = models.DateTimeField(null=True, blank=True)
    low_stock_threshold  = models.PositiveIntegerField(default=5)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def primary_image(self):
        return self.images.filter(is_primary=True).first()

    @property
    def in_stock(self):
        return self.stock > 0


class ProductImage(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image      = models.ImageField(upload_to='products/', null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'product_images'

    def __str__(self):
        return f'Image for {self.product.name}'


class ProductHistory(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='history')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    old_price  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    new_price  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    old_stock  = models.IntegerField(null=True, blank=True)
    new_stock  = models.IntegerField(null=True, blank=True)
    reason     = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'product_history'
        ordering = ['-created_at']


class Discount(models.Model):
    TYPE_CHOICES = [
        ('percent', 'Percentage'),
        ('fixed',   'Fixed Amount'),
    ]

    store            = models.ForeignKey('stores.Store', on_delete=models.CASCADE, related_name='discounts')
    code             = models.CharField(max_length=50, unique=True)
    type             = models.CharField(max_length=10, choices=TYPE_CHOICES)
    value            = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    start_date       = models.DateTimeField()
    end_date         = models.DateTimeField()
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'discounts'

    def __str__(self):
        return self.code


class ProductDiscount(models.Model):
    discount   = models.ForeignKey(Discount, on_delete=models.CASCADE, related_name='product_discounts')
    product    = models.ForeignKey(Product,  on_delete=models.CASCADE, related_name='product_discounts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'product_discounts'
        unique_together = ['discount', 'product']


class ProductStats(models.Model):
    product       = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stats')
    store         = models.ForeignKey('stores.Store', on_delete=models.CASCADE)
    date          = models.DateField()
    total_sold    = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'product_stats'
        unique_together = ['product', 'date']
        ordering        = ['-date']