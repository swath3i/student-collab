import logging
from django.contrib.auth import get_user_model
from core.models import Connection

logger = logging.getLogger(__name__)
User = get_user_model()


class ConnectionService:
    @staticmethod
    def send_request(requester, receiver_id):
        try:
            receiver = User.objects.get(id=receiver_id)

            if requester.id == receiver.id:
                raise Exception("Cannot connect with yourself")

            # Check if connection already exists in either direction
            existing = Connection.objects.filter(
                requester=requester, receiver=receiver
            ).first() or Connection.objects.filter(
                requester=receiver, receiver=requester
            ).first()

            if existing:
                raise Exception(f"Connection already exists: {existing.status}")

            connection = Connection.objects.create(
                requester=requester,
                receiver=receiver,
                status=Connection.Status.PENDING,
            )

            return connection

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

            return connection

        except Connection.DoesNotExist:
            raise Exception("Connection request not found")
        except Exception as e:
            logger.error(f"Error responding to connection: {e}")
            raise Exception(str(e))

    @staticmethod
    def get_connections(user):
        try:
            sent = Connection.objects.filter(requester=user).select_related('receiver')
            received = Connection.objects.filter(receiver=user).select_related('requester')

            connections = []

            for conn in sent:
                connections.append({
                    "connection_id": str(conn.id),
                    "user": {
                        "id": str(conn.receiver.id),
                        "name": conn.receiver.name,
                        "email": conn.receiver.email,
                        "profile_pic": conn.receiver.profile_pic.url if conn.receiver.profile_pic else None,
                    },
                    "status": conn.status,
                    "direction": "sent",
                })

            for conn in received:
                connections.append({
                    "connection_id": str(conn.id),
                    "user": {
                        "id": str(conn.requester.id),
                        "name": conn.requester.name,
                        "email": conn.requester.email,
                        "profile_pic": conn.requester.profile_pic.url if conn.requester.profile_pic else None,
                    },
                    "status": conn.status,
                    "direction": "received",
                })

            return connections

        except Exception as e:
            logger.error(f"Error getting connections: {e}")
            raise Exception(f"Failed to get connections: {str(e)}")