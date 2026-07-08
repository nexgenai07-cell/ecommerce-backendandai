from django.urls import path
from .views import CreatePaymentIntentView

urlpatterns = [
    path(
        "create-intent/",
        CreatePaymentIntentView.as_view(),
        name="create-payment-intent",
    ),
]