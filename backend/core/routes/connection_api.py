import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from ninja import Router
from core.schemas.schemas import ConnectionRequestSchema, ConnectionResponseSchema, MessageSchemaIn
from core.services.connection_service import ConnectionService
from core.services.message_service import MessageService

logger = logging.getLogger(__name__)
router = Router()


@router.post("/", response={200: dict, 400: dict})
def send_connection(request, payload: ConnectionRequestSchema):
    try:
        ConnectionService.send_request(request.user, payload.receiver_id)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Connection request error: {e}")
        return 400, {"detail": str(e)}


@router.get("/", response={200: list, 400: dict})
def get_connections(request):
    try:
        return ConnectionService.get_connections(request.user)
    except Exception as e:
        logger.error(f"Get connections error: {e}")
        return 400, {"detail": str(e)}


@router.put("/{connection_id}", response={200: dict, 400: dict})
def respond_connection(request, connection_id: str, payload: ConnectionResponseSchema):
    try:
        ConnectionService.respond_to_request(request.user, connection_id, payload.accept)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Connection response error: {e}")
        return 400, {"detail": str(e)}


@router.get("/{connection_id}/messages", response={200: list, 400: dict, 403: dict})
def get_messages(request, connection_id: str):
    try:
        conn = ConnectionService.get_connection_for_user(request.user, connection_id)
        if conn.status != 'accepted':
            return 403, {"detail": "Chat only available for accepted connections"}
        return MessageService.get_messages(conn, request.user)
    except Exception as e:
        logger.error(f"Get messages error: {e}")
        return 400, {"detail": str(e)}


@router.post("/{connection_id}/messages", response={200: dict, 400: dict, 403: dict})
def send_message(request, connection_id: str, payload: MessageSchemaIn):
    try:
        conn = ConnectionService.get_connection_for_user(request.user, connection_id)
        if conn.status != 'accepted':
            return 403, {"detail": "Chat only available for accepted connections"}
        content = payload.content.strip()
        if not content:
            return 400, {"detail": "Message cannot be empty"}
        msg = MessageService.send_message(conn, request.user, content)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{connection_id}",
            {
                "type": "chat_message",
                "id": str(msg.id),
                "sender_id": str(request.user.id),
                "content": content,
                "sent_at": msg.sent_at.isoformat(),
            }
        )
        return {"id": str(msg.id), "sent_at": msg.sent_at.isoformat()}
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return 400, {"detail": str(e)}


@router.put("/{connection_id}/messages/read", response={200: dict, 400: dict})
def mark_read(request, connection_id: str):
    try:
        conn = ConnectionService.get_connection_for_user(request.user, connection_id)
        MessageService.mark_read(conn, request.user)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Mark read error: {e}")
        return 400, {"detail": str(e)}
