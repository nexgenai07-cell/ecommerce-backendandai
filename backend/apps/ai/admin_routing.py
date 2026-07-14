# PATH: apps/ai/admin_routing.py

from django.urls import re_path
from .admin_consumers import AdminChatConsumer

admin_websocket_urlpatterns = [
    re_path(r'ws/admin-chat/(?P<session_key>[^/]+)/$', AdminChatConsumer.as_asgi()),
]