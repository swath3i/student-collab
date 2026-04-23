import logging
from django.contrib.auth import get_user_model
from core.models import Connection, Message

logger = logging.getLogger(__name__)
User = get_user_model()


class ConnectionService:
    @staticmethod
    def send_request(requester, receiver_id):
        try:
            receiver = User.objects.get(id=receiver_id)

            if requester.id == receiver.id:
                raise Exception("Cannot connect with yourself")

            existing = Connection.objects.filter(
                requester=requester, receiver=receiver
            ).first() or Connection.objects.filter(
                requester=receiver, receiver=requester
            ).first()

            if existing:
                raise Exception(f"Connection already exists: {existing.status}")

            return Connection.objects.create(
                requester=requester,
                receiver=receiver,
                status=Connection.Status.PENDING,
            )

        except User.DoesNotExist:
            raise Exception("User not found")
        except Exception as e:
            logger.error(f"Error sending connection request: {e}")
            raise Exception(str(e))

    @staticmethod
    def respond_to_request(user, connection_id, accept):
        try:
            connection = Connection.objects.get(id=connection_id, receiver=user)

            if connection.status != Connection.Status.PENDING:
                raise Exception("Connection is not pending")

            connection.status = Connection.Status.ACCEPTED if accept else Connection.Status.DECLINED
            connection.save(update_fields=['status'])

            if accept:
                from core.services.recommendation_service import RecommendationService
                RecommendationService.invalidate_cache(user.id)
                RecommendationService.invalidate_cache(connection.requester_id)

            return connection

        except Connection.DoesNotExist:
            raise Exception("Connection request not found")
        except Exception as e:
            logger.error(f"Error responding to connection: {e}")
            raise Exception(str(e))

    @staticmethod
    def get_connection_for_user(user, connection_id):
        try:
            conn = Connection.objects.get(id=connection_id)
            if conn.requester_id != user.id and conn.receiver_id != user.id:
                raise Exception("Access denied")
            return conn
        except Connection.DoesNotExist:
            raise Exception("Connection not found")

    @staticmethod
    def _last_message(conn):
        msg = Message.objects.filter(connection=conn).order_by('-sent_at').first()
        if not msg:
            return None
        return {
            "content": msg.content,
            "sent_at": msg.sent_at.isoformat(),
            "sender_id": str(msg.sender_id),
        }

    @staticmethod
    def _unread_count(conn, other_user):
        return Message.objects.filter(
            connection=conn,
            sender=other_user,
            read_at__isnull=True,
        ).count()

    @staticmethod
    def get_connections(user):
        try:
            sent = Connection.objects.filter(requester=user).select_related('receiver')
            received = Connection.objects.filter(receiver=user).select_related('requester')

            connections = []

            for conn in sent:
                other = conn.receiver
                connections.append({
                    "connection_id": str(conn.id),
                    "user": {
                        "id": str(other.id),
                        "name": other.name,
                        "email": other.email,
                        "profile_pic": other.profile_pic.url if other.profile_pic else None,
                    },
                    "status": conn.status,
                    "direction": "sent",
                    "last_message": ConnectionService._last_message(conn),
                    "unread_count": ConnectionService._unread_count(conn, other),
                })

            for conn in received:
                other = conn.requester
                connections.append({
                    "connection_id": str(conn.id),
                    "user": {
                        "id": str(other.id),
                        "name": other.name,
                        "email": other.email,
                        "profile_pic": other.profile_pic.url if other.profile_pic else None,
                    },
                    "status": conn.status,
                    "direction": "received",
                    "last_message": ConnectionService._last_message(conn),
                    "unread_count": ConnectionService._unread_count(conn, other),
                })

            return connections

        except Exception as e:
            logger.error(f"Error getting connections: {e}")
            raise Exception(f"Failed to get connections: {str(e)}")
