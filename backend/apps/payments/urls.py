from django.urls import path

from .views import (
    CreatePaymentIntentView,
    StripeWebhookView,
)

urlpatterns = [
    path(
        "create-intent/",
        CreatePaymentIntentView.as_view(),
        name="create-payment-intent",
    ),
    path(
        "stripe/webhook/",
        StripeWebhookView.as_view(),
        name="stripe-webhook",
    ),
]