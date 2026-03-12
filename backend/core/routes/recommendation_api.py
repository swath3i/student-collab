import logging
from ninja import Router
from core.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)
router = Router()


@router.get("/", response={200: list, 400: dict})
def get_recommendations(request):
    try:
        data = RecommendationService.get_recommendations(request.user)
        return data
    except Exception as e:
        logger.error(f"Recommendations error: {e}")
        return 400, {"detail": str(e)}