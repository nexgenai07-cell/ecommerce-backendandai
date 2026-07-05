# PATH: apps/orders/complaint_views.py

from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.returns.models import Complaint
from apps.returns.complaint_serializers import (
    ComplaintSerializer,
    CreateComplaintSerializer,
    AdminComplaintStatusSerializer,
    AdminComplaintRespondSerializer,
)
from .models import Order, Customer
from apps.users.permissions import IsAdmin


class CreateComplaintView(generics.ListCreateAPIView):
    """
    POST /api/v1/complaints/ -> submit a complaint
    GET  /api/v1/complaints/ -> customer sees own complaints, admin sees all
    """

    serializer_class = ComplaintSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Complaint.objects.all().order_by("-created_at")

        return Complaint.objects.filter(
            customer__user=user
        ).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = CreateComplaintSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        customer = Customer.objects.filter(user=request.user).first()
        if not customer:
            return Response(
                {"error": "No customer profile found. Place an order first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order = serializer.validated_data.get("order")

        # Ensure the supplied order belongs to the logged-in customer
        if order and order.customer.user != request.user:
            return Response(
                {"error": "Invalid order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        complaint = serializer.save(
            customer=customer,
            order=order,
            status="open",
        )

        return Response(
            ComplaintSerializer(
                complaint,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class ComplaintDetailView(generics.RetrieveAPIView):
    """GET /api/v1/complaints/{id}/"""

    serializer_class = ComplaintSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Complaint.objects.all()

        return Complaint.objects.filter(customer__user=user)

    def retrieve(self, request, *args, **kwargs):
        complaint = self.get_object()
        serializer = ComplaintSerializer(
            complaint,
            context={"request": request},
        )
        return Response(serializer.data)


class AdminComplaintStatusUpdateView(APIView):
    """PUT /api/v1/admin/complaints/{id}/status/"""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def put(self, request, pk):
        try:
            complaint = Complaint.objects.get(id=pk)
        except Complaint.DoesNotExist:
            return Response(
                {"error": "Complaint not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminComplaintStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        complaint.status = serializer.validated_data["status"]
        complaint.save()

        return Response(
            ComplaintSerializer(
                complaint,
                context={"request": request},
            ).data
        )


class AdminComplaintRespondView(APIView):
    """PUT /api/v1/admin/complaints/{id}/respond/"""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def put(self, request, pk):
        try:
            complaint = Complaint.objects.get(id=pk)
        except Complaint.DoesNotExist:
            return Response(
                {"error": "Complaint not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminComplaintRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        complaint.response = serializer.validated_data["response"]
        complaint.resolved_by = request.user
        complaint.status = "resolved"
        complaint.save()

        return Response(
            ComplaintSerializer(
                complaint,
                context={"request": request},
            ).data
        )