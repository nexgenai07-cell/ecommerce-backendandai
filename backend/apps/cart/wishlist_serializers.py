# PATH: apps/cart/wishlist_serializers.py

from rest_framework import serializers
from .models import Wishlist, WishlistItem
from apps.products.models import Product


class WishlistProductSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    in_stock = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "price",
            "primary_image",
            "in_stock",
            "stock",
            "category",
        ]

    def get_primary_image(self, obj):
        image = obj.primary_image
        if image and image.image:
            return image.image.url
        return None


class WishlistItemSerializer(serializers.ModelSerializer):
    product = WishlistProductSerializer(read_only=True)

    class Meta:
        model = WishlistItem
        fields = [
            "id",
            "product",
            "created_at",
        ]


class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Wishlist
        fields = [
            "id",
            "items",
            "created_at",
        ]


class AddToWishlistSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()

    def validate_product_id(self, value):
        if not Product.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Product not found.")
        return value