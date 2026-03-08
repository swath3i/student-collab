import logging

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