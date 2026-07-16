# PATH: apps/ai/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from langchain_core.messages import HumanMessage, AIMessage

from apps.ai.agents.shopping_agent import run_shopping_agent
from apps.ai.models import ChatSession, ChatMessage
from apps.ai.customer_context import get_customer_context
from apps.stores.models import Store

MAX_HISTORY_MESSAGES = 12


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.session_key = self.scope['url_route']['kwargs']['session_key']
        self.room_group_name = f"chat_{self.session_key}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connected",
            "message": "WebSocket connected successfully",
            "session_key": self.session_key
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Invalid message format — expected JSON.",
            }))
            return
        user_message = data.get("message", "")

        try:
            response_text, products_metadata = await self.get_agent_response(user_message)
        except Exception as e:
            response_text, products_metadata = f"Sorry, something went wrong: {str(e)}", []

        # NEW — 'metadata' field mein product_id/category_id waale products
        # bheje jate hain, taake frontend UI cards render kar sake.
        await self.send(text_data=json.dumps({
            "type": "message",
            "sender": "ai",
            "message": response_text,
            "metadata": {"products": products_metadata} if products_metadata else None,
        }))

    @sync_to_async
    def get_agent_response(self, user_message):
        chat_session, _ = ChatSession.objects.select_related('user').get_or_create(
            session_key=self.session_key,
            defaults={'store': Store.objects.first()},
        )
        user = chat_session.user

        ChatMessage.objects.create(session=chat_session, sender='user', message=user_message)

        if user is not None:
            messages_qs = ChatMessage.objects.filter(
                session__user=user
            ).select_related('session').order_by('-created_at')
        else:
            messages_qs = chat_session.messages.order_by('-created_at')

        previous_messages = list(messages_qs[1:MAX_HISTORY_MESSAGES + 1])
        previous_messages.reverse()

        chat_history = []
        for msg in previous_messages:
            if msg.sender == 'user':
                chat_history.append(HumanMessage(content=msg.message))
            else:
                chat_history.append(AIMessage(content=msg.message))

        customer_context = get_customer_context(user)

        output, products_metadata = run_shopping_agent(
            user_message,
            session_key=self.session_key,
            user=user,
            chat_history=chat_history,
            customer_context=customer_context,
        )

        if isinstance(output, list):
            output = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in output
            ).strip()

        # NEW — metadata bhi ChatMessage mein save hoti hai (jaisa model
        # comment mein already documented tha: "product cards, order info...")
        ChatMessage.objects.create(
            session=chat_session,
            sender='ai',
            message=output,
            metadata={"products": products_metadata} if products_metadata else None,
        )

        return output, products_metadata