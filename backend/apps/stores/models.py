# PATH: ecommerce/apps/stores/models.py

from django.db import models
from django.conf import settings


class Store(models.Model):
    PLAN_CHOICES = [
        ('basic',      'Basic'),
        ('pro',        'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    owner      = models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=models.PROTECT,
                    related_name='stores',
                 )
    name       = models.CharField(max_length=255)
    logo = models.ImageField(
    upload_to='store_logos/',
    blank=True,
    null=True
                 )
    subdomain  = models.CharField(max_length=100, unique=True)
    phone      = models.CharField(max_length=20, blank=True, null=True)
    address    = models.TextField(blank=True, null=True)
    plan       = models.CharField(max_length=20, choices=PLAN_CHOICES, default='basic')
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stores'

    def __str__(self):
        return self.name