# PATH: apps/ai/views.py

import uuid
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.stores.models import Store
from apps.users.permissions import IsAdmin
from .models import ChatSession, ChatMessage, AuditLog
from .serializers import ChatSessionSerializer, ChatSessionHistorySerializer, AuditLogSerializer


class StartChatSessionView(APIView):
    """
    POST /api/v1/chat/session/start/

    Starts a new chat session.
    - Anonymous users: a new random session_key is generated (frontend saves it
      in localStorage and sends it back on every later request).
    - Logged in users: session is automatically linked to their account.
    """
    # Anyone can start a chat session, even without logging in
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Generate a unique session key — frontend stores this and reuses it
        session_key = uuid.uuid4().hex

        # Single-store setup — always attach the one store that exists
        store = Store.objects.first()

        session = ChatSession.objects.create(
            session_key=session_key,
            store=store,
            # if the user is logged in, link the session to them right away
            user=request.user if request.user.is_authenticated else None,
        )

        return Response(ChatSessionSerializer(session).data, status=status.HTTP_201_CREATED)
    

class ChatSessionHistoryView(generics.RetrieveAPIView):
    """
    GET /api/v1/chat/session/{session_key}/history/

    Returns the full conversation (all messages) for a given session.
    """
    serializer_class = ChatSessionHistorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'session_key'
    queryset = ChatSession.objects.prefetch_related('messages')


class ClearChatSessionView(APIView):
    """
    DELETE /api/v1/chat/session/{session_key}/clear/

    Deletes all messages in a session (used when user clicks "clear chat").
    The session itself stays so the same session_key keeps working.
    """
    permission_classes = [permissions.AllowAny]

    def delete(self, request, session_key):
        try:
            session = ChatSession.objects.get(session_key=session_key)
        except ChatSession.DoesNotExist:
            return Response({'error': 'Session not found.'}, status=status.HTTP_404_NOT_FOUND)

        # remove all messages but keep the session row itself
        session.messages.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditLogListView(generics.ListAPIView):
    """
    GET /api/v1/admin/audit-logs/

    Lets admin see a history of every action performed (web or WhatsApp).
    Read-only — logs are created internally by the system, not via this API.
    """
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    queryset = AuditLog.objects.select_related('user').all()
