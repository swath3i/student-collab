import json
import logging
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.connection_id = self.scope['url_route']['kwargs']['connection_id']
        self.group_name = f"chat_{self.connection_id}"

        user = await self.authenticate()
        if not user:
            await self.close(code=4001)
            return

        allowed = await self.verify_connection(user)
        if not allowed:
            await self.close(code=4003)
            return

        self.user = user
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            content = data.get('content', '').strip()
            if not content:
                return
            message = await self.save_message(content)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'chat_message',
                    'id': str(message.id),
                    'sender_id': str(self.user.id),
                    'content': content,
                    'sent_at': message.sent_at.isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"ChatConsumer receive error: {e}")

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'id': event['id'],
            'sender_id': event['sender_id'],
            'content': event['content'],
            'sent_at': event['sent_at'],
        }))

    @database_sync_to_async
    def authenticate(self):
        query_string = self.scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]
        if not token:
            return None
        try:
            auth = JWTAuthentication()
            validated = auth.get_validated_token(token)
            user = auth.get_user(validated)
            return user if user.is_active else None
        except Exception:
            return None

    @database_sync_to_async
    def verify_connection(self, user):
        from core.models import Connection
        try:
            conn = Connection.objects.get(id=self.connection_id, status=Connection.Status.ACCEPTED)
            return conn.requester_id == user.id or conn.receiver_id == user.id
        except Connection.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content):
        from core.models import Connection, Message
        conn = Connection.objects.get(id=self.connection_id)
        return Message.objects.create(connection=conn, sender=self.user, content=content)
