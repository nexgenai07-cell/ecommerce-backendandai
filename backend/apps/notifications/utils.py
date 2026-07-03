from .models import Notification
from apps.stores.models import Store


def create_notification(user, title, message, notification_type, store=None):
    if store is None:
        store = Store.objects.first()

    return Notification.objects.create(
        user=user,
        store=store,
        title=title,
        message=message,
        type=notification_type,
    )