from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Category
from .serializers import CategorySerializer
from apps.users.permissions import IsAdmin


class CategoryViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/categories/       -> list (anyone)
    POST   /api/v1/categories/       -> create (admin only)
    GET    /api/v1/categories/{id}/  -> retrieve (anyone)
    PUT    /api/v1/categories/{id}/  -> update (admin only)
    DELETE /api/v1/categories/{id}/  -> delete (admin only)
    """

    serializer_class = CategorySerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # Disable pagination for this endpoint
    pagination_class = None

    def get_queryset(self):
        return Category.objects.all().order_by("name")

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsAdmin()]