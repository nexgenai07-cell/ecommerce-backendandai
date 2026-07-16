# PATH: apps/ai/admin_consumers.py
#
# Admin dashboard ka WebSocket consumer — customer ChatConsumer se bilkul
# alag route pe hai. Role check yahan bhi hota hai (defense in depth —
# StartAdminChatSessionView pe IsAdmin already check ho chuka hai, lekin
# yahan bhi dobara confirm karte hain taake koi bypass na kar sake).

import json
import re
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from langchain_core.messages import HumanMessage, AIMessage

from apps.ai.models import ChatSession, ChatMessage
from apps.ai.admin_agents.coordinator import route_intent
from apps.ai.admin_agents.operations_agent import run_operations_agent
from apps.ai.admin_agents.analytics_agent import run_analytics_agent

MAX_HISTORY_MESSAGES = 12

# NEW — kabhi kabhi Groq fallback models (khaas kar chhote/faster models
# jaise llama-3.1-8b-instant) apna internal tool-call wrapper text mein
# hi leak kar dete hain, e.g. "<function>asal jawab</function>" — is se
# raw tags user ko dikh jate hain. Ye regex us wrapper ko hata kar sirf
# andar wala asal jawab rakh leta hai (agar tags na hon to text waisa hi
# rehta hai — no-op).
_LEAKED_FUNCTION_TAG_RE = re.compile(r'</?function[^>]*>', re.IGNORECASE)


def _strip_leaked_function_tags(text: str) -> str:
    if not isinstance(text, str) or '<function' not in text.lower():
        return text
    return _LEAKED_FUNCTION_TAG_RE.sub('', text).strip()


class AdminChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.session_key = self.scope['url_route']['kwargs']['session_key']

        # Role check — session ka user 'admin' role ka hona chahiye
        is_authorized = await self.check_admin_session()
        if not is_authorized:
            await self.close(code=4403)  # custom close code — "forbidden"
            return

        self.room_group_name = f"admin_chat_{self.session_key}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connected",
            "message": "Admin WebSocket connected successfully",
            "session_key": self.session_key,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    @sync_to_async
    def check_admin_session(self):
        session = ChatSession.objects.select_related('user').filter(session_key=self.session_key).first()
        return session is not None and session.user is not None and getattr(session.user, 'role', None) == 'admin'

    async def receive(self, text_data):
        data = json.loads(text_data)
        user_message = data.get("message", "")

        try:
            response_text, metadata = await self.get_agent_response(user_message)
        except Exception as e:
            response_text, metadata = f"Sorry, something went wrong: {str(e)}", None

        await self.send(text_data=json.dumps({
            "type": "message",
            "sender": "ai",
            "message": response_text,
            "metadata": metadata,
        }))

    @sync_to_async
    def get_agent_response(self, user_message):
        chat_session = ChatSession.objects.select_related('user').get(session_key=self.session_key)
        user = chat_session.user

        ChatMessage.objects.create(session=chat_session, sender='user', message=user_message)

        previous_messages = list(chat_session.messages.order_by('-created_at')[1:MAX_HISTORY_MESSAGES + 1])
        previous_messages.reverse()

        chat_history = []
        for msg in previous_messages:
            if msg.sender == 'user':
                chat_history.append(HumanMessage(content=msg.message))
            else:
                chat_history.append(AIMessage(content=msg.message))

        intent = route_intent(user_message)

        if intent == 'analytics':
            output, metadata = run_analytics_agent(user_message, user=user, chat_history=chat_history)
        else:
            output, metadata = run_operations_agent(user_message, session_key=self.session_key, user=user, chat_history=chat_history)

        if isinstance(output, list):
            output = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in output
            ).strip()

        output = _strip_leaked_function_tags(output)

        ChatMessage.objects.create(session=chat_session, sender='ai', message=output, metadata=metadata)

        return output, metadata