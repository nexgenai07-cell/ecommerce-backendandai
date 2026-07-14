# PATH: apps/ai/urls.py

from django.urls import path
from .views import StartChatSessionView, ChatSessionHistoryView, ClearChatSessionView, AuditLogListView
from .admin_views import StartAdminChatSessionView

# Note: these get included under 'api/v1/chat/' in core/urls.py
urlpatterns = [
    path('session/start/', StartChatSessionView.as_view(), name='chat-session-start'),
    path('session/<str:session_key>/history/', ChatSessionHistoryView.as_view(), name='chat-session-history'),
    path('session/<str:session_key>/clear/', ClearChatSessionView.as_view(), name='chat-session-clear'),
    # NEW — admin-only chat session (IsAdmin-gated)
    path('admin/session/start/', StartAdminChatSessionView.as_view(), name='admin-chat-session-start'),
]

# Separate list — included under 'api/v1/admin/audit-logs/' in core/urls.py
audit_log_urlpatterns = [
    path('', AuditLogListView.as_view(), name='audit-log-list'),
]
