import logging
from core.models import Profile

logger = logging.getLogger(__name__)


class ProfileService:
    @staticmethod
    def create_profile(user, skills_text, intent_text):
        try:
            profile, created = Profile.objects.update_or_create(
                user=user,
                defaults={
                    'skills_text': skills_text,
                    'intent_text': intent_text,
                }
            )

            # TODO: Call ML service to generate embeddings

            return profile
        except Exception as e:
            logger.error(f"Error creating profile: {e}")
            raise Exception(f"Failed to create profile: {str(e)}")