# PATH: apps/products/urls.py

from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, serve_product_image

router = DefaultRouter()
router.register('', ProductViewSet, basename='product')

urlpatterns = [
    path('images/<int:pk>/', serve_product_image, name='product-image'),
] + router.urls