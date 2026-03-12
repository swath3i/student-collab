import logging
from core.models import Profile
from core.services.ml_service import MLService
from core.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)


class ProfileService:
    @staticmethod
    def create_profile(user, skills_text, intent_text):
        try:
            skill_embedding = MLService.get_embedding(skills_text)
            intent_embedding = MLService.get_embedding(intent_text)

            profile, created = Profile.objects.update_or_create(
                user=user,
                defaults={
                    'skills_text': skills_text,
                    'intent_text': intent_text,
                    'skill_embedding': skill_embedding,
                    'intent_embedding': intent_embedding,
                }
            )

            RecommendationService.invalidate_cache(user.id)

            return profile
        except Exception as e:
            logger.error(f"Error creating profile: {e}")
            raise Exception(f"Failed to create profile: {str(e)}")