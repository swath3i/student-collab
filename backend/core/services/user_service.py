import logging
from django.db.models import Q
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


class UserService:
    @staticmethod
    def get_user(user):
        try:
            return {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "profile_pic": user.profile_pic.url if user.profile_pic else None,
            }
        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            raise Exception(f"Failed to fetch user: {str(e)}")

    @staticmethod
    def update_user(user, name):
        try:
            user.name = name
            user.save(update_fields=['name'])
            return user
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            raise Exception(f"Failed to update user: {str(e)}")

    @staticmethod
    def update_profile_pic(user, profile_pic):
        try:
            user.profile_pic = profile_pic
            user.save(update_fields=['profile_pic'])
            return user
        except Exception as e:
            logger.error(f"Error updating profile pic: {e}")
            raise Exception(f"Failed to update profile pic: {str(e)}")

    @staticmethod
    def get_user_profile(user_id):
        try:
            User = get_user_model()
            u = User.objects.get(id=user_id)
            try:
                profile = u.profile
                skills_text = profile.skills_text
                intent_text = profile.intent_text
            except Exception:
                skills_text = ""
                intent_text = ""
            return {
                "id": str(u.id),
                "name": u.name,
                "profile_pic": u.profile_pic.url if u.profile_pic else None,
                "skills_text": skills_text,
                "intent_text": intent_text,
            }
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
            raise

    @staticmethod
    def search_users(current_user, query):
        try:
            from core.models import Connection
            User = get_user_model()

            q = query.strip()
            if len(q) < 2:
                return []

            # Build connection map: other_user_id → {connection_id, status, direction}
            conn_map = {}
            for conn in Connection.objects.filter(requester=current_user):
                conn_map[str(conn.receiver_id)] = {
                    "connection_id": str(conn.id),
                    "status": conn.status,
                    "direction": "sent",
                }
            for conn in Connection.objects.filter(receiver=current_user):
                conn_map[str(conn.requester_id)] = {
                    "connection_id": str(conn.id),
                    "status": conn.status,
                    "direction": "received",
                }

            users = (
                User.objects
                .filter(name__icontains=q)
                .exclude(id=current_user.id)
                .prefetch_related('profile')
                [:20]
            )

            result = []
            for u in users:
                try:
                    profile = u.profile
                    skills_text = profile.skills_text
                    intent_text = profile.intent_text
                except Exception:
                    skills_text = ""
                    intent_text = ""
                result.append({
                    "id": str(u.id),
                    "name": u.name,
                    "email": u.email,
                    "profile_pic": u.profile_pic.url if u.profile_pic else None,
                    "skills_text": skills_text,
                    "intent_text": intent_text,
                    "connection": conn_map.get(str(u.id)),
                })
            return result
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            raise Exception(f"Failed to search users: {str(e)}")