import logging
from django.utils import timezone
from core.models import Message

logger = logging.getLogger(__name__)


class MessageService:
    @staticmethod
    def get_messages(connection, user):
        try:
            messages = (
                Message.objects
                .filter(connection=connection)
                .select_related('sender')
                .order_by('sent_at')
            )
            return [
                {
                    "id": str(m.id),
                    "sender_id": str(m.sender.id),
                    "sender_name": m.sender.name,
                    "sender_pic": m.sender.profile_pic.url if m.sender.profile_pic else None,
                    "content": m.content,
                    "sent_at": m.sent_at.isoformat(),
                    "read_at": m.read_at.isoformat() if m.read_at else None,
                    "is_mine": m.sender_id == user.id,
                }
                for m in messages
            ]
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            raise Exception(f"Failed to fetch messages: {str(e)}")

    @staticmethod
    def send_message(connection, sender, content):
        try:
            return Message.objects.create(
                connection=connection,
                sender=sender,
                content=content,
            )
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise Exception(f"Failed to send message: {str(e)}")

    @staticmethod
    def mark_read(connection, user):
        try:
            Message.objects.filter(
                connection=connection,
                read_at__isnull=True,
            ).exclude(sender=user).update(read_at=timezone.now())
        except Exception as e:
            logger.error(f"Error marking messages read: {e}")
            raise Exception(f"Failed to mark messages read: {str(e)}")
