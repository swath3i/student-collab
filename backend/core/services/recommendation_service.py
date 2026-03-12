import json
import logging
import numpy as np
import redis
from core.models import Profile, Connection

logger = logging.getLogger(__name__)

SKILL_WEIGHT = 0.35
INTENT_WEIGHT = 0.65
CACHE_TTL = 1800  # 30 minutes
redis_client = redis.Redis(host='redis', port=6379, db=0)


class RecommendationService:
    @staticmethod
    def cosine_similarity(a, b):
        a = np.array(a)
        b = np.array(b)
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        if norm == 0:
            return 0.0
        return float(dot / norm)

    @staticmethod
    def get_recommendations(user, limit=20):
        try:
            cache_key = f"recommendations:{user.id}"

            # Check Redis cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Get current user's profile
            try:
                my_profile = Profile.objects.get(user=user)
            except Profile.DoesNotExist:
                return []

            if not my_profile.skill_embedding or not my_profile.intent_embedding:
                return []

            # Get IDs of users already connected (any status)
            connected_ids = set(
                Connection.objects.filter(requester=user).values_list('receiver_id', flat=True)
            ) | set(
                Connection.objects.filter(receiver=user).values_list('requester_id', flat=True)
            )

            # Get all other profiles with embeddings
            other_profiles = (
                Profile.objects
                .exclude(user=user)
                .exclude(user_id__in=connected_ids)
                .exclude(skill_embedding__isnull=True)
                .exclude(intent_embedding__isnull=True)
                .select_related('user')
            )

            # Compute scores
            recommendations = []
            for profile in other_profiles:
                skill_sim = RecommendationService.cosine_similarity(
                    my_profile.skill_embedding, profile.skill_embedding
                )
                intent_sim = RecommendationService.cosine_similarity(
                    my_profile.intent_embedding, profile.intent_embedding
                )
                score = (SKILL_WEIGHT * skill_sim) + (INTENT_WEIGHT * intent_sim)

                recommendations.append({
                    "id": str(profile.user.id),
                    "name": profile.user.name,
                    "email": profile.user.email,
                    "profile_pic": profile.user.profile_pic.url if profile.user.profile_pic else None,
                    "skills_text": profile.skills_text,
                    "intent_text": profile.intent_text,
                    "match_score": round(score * 100, 1),
                })

            recommendations.sort(key=lambda x: x["match_score"], reverse=True)
            recommendations = recommendations[:limit]

            # Cache in Redis
            redis_client.setex(cache_key, CACHE_TTL, json.dumps(recommendations))

            return recommendations

        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            raise Exception(f"Failed to get recommendations: {str(e)}")

    @staticmethod
    def invalidate_cache(user_id):
        try:
            redis_client.delete(f"recommendations:{user_id}")
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")