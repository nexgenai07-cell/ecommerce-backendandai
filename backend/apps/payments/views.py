import stripe

from django.conf import settings
from django.utils import timezone

from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import (
    authentication_classes,
    permission_classes,
)

from apps.orders.models import Order

stripe.api_key = settings.STRIPE_SECRET_KEY


class CreatePaymentIntentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        order_number = request.data.get("order_number")

        if not order_number:
            return Response(
                {"error": "order_number is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = Order.objects.get(
                order_number=order_number,
                customer__user=request.user,
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        intent = stripe.PaymentIntent.create(
            amount=int(order.total_amount * 100),
            currency="pkr",
            metadata={
                "order_id": order.id,
                "order_number": order.order_number,
            },
        )

        payment = order.payment
        payment.stripe_payment_intent_id = intent.id
        payment.save()

        return Response(
            {
                "client_secret": intent.client_secret,
                "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
                "amount": int(order.total_amount * 100),
                "currency": "pkr",
                "order_number": order.order_number,
            }
        )


@authentication_classes([])
@permission_classes([])
class StripeWebhookView(APIView):

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except ValueError:
            return Response(status=400)
        except stripe.error.SignatureVerificationError:
            return Response(status=400)

        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]

            order_number = intent["metadata"]["order_number"]            
            try:
                order = Order.objects.get(order_number=order_number)

                payment = order.payment
                payment.status = "paid"
                payment.paid_at = timezone.now()
                payment.save()

                order.status = "confirmed"
                order.save()

            except Order.DoesNotExist:
                pass

        elif event["type"] == "payment_intent.payment_failed":
            intent = event["data"]["object"]

            order_number = intent["metadata"].get("order_number")

            try:
                order = Order.objects.get(order_number=order_number)

                payment = order.payment
                payment.status = "failed"
                payment.save()

            except Order.DoesNotExist:
                pass

        return Response(status=200)