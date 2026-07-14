# PATH: apps/ai/admin_views.py

import uuid
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.stores.models import Store
from apps.users.permissions import IsAdmin
from apps.ai.models import ChatSession
from apps.ai.serializers import ChatSessionSerializer


class StartAdminChatSessionView(APIView):
    """
    POST /api/v1/chat/admin/session/start/

    Customer's StartChatSessionView se alag — sirf admin role wale users
    hi admin chat session bana sakte hain. Ye session_key WebSocket
    (ws/admin-chat/<session_key>/) se connect karne k liye use hoga.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request):
        session_key = uuid.uuid4().hex
        store = Store.objects.first()

        session = ChatSession.objects.create(
            session_key=session_key,
            store=store,
            user=request.user,
        )

        return Response(ChatSessionSerializer(session).data, status=status.HTTP_201_CREATED)