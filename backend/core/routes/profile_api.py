import logging
from ninja import Router
from core.schemas.schemas import ProfileSchemaIn
from core.services.profile_service import ProfileService

logger = logging.getLogger(__name__)
router = Router()


@router.post("/", response={200: dict, 400: dict})
def create_profile(request, payload: ProfileSchemaIn):
    try:
        ProfileService.create_profile(
            request.user,
            payload.skills_text,
            payload.intent_text,
        )
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Profile creation error: {e}")
        return 400, {"detail": str(e)}