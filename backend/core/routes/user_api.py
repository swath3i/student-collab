import logging
from ninja import Router, File
from ninja.files import UploadedFile
from core.schemas.schemas import UserSchemaIn
from core.services.user_service import UserService

logger = logging.getLogger(__name__)
router = Router()


@router.get("/", response={200: dict, 400: dict})
def get_user(request):
    try:
        data = UserService.get_user(request.user)
        return data
    except Exception as e:
        logger.error(f"Get user error: {e}")
        return 400, {"detail": str(e)}


@router.put("/", response={200: dict, 400: dict})
def update_user(request, payload: UserSchemaIn):
    try:
        user = request.user
        UserService.update_user(user, payload.name)
        return {
            "status": "success",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
            }
        }
    except Exception as e:
        logger.error(f"User update error: {e}")
        return 400, {"detail": str(e)}


@router.put("/photo", response={200: dict, 400: dict})
def update_photo(request, profile_pic: UploadedFile = File(...)):
    try:
        UserService.update_profile_pic(request.user, profile_pic)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Photo upload error: {e}")
        return 400, {"detail": str(e)}


@router.get("/search", response={200: list, 400: dict})
def search_users(request, q: str = ""):
    try:
        return UserService.search_users(request.user, q)
    except Exception as e:
        logger.error(f"User search error: {e}")
        return 400, {"detail": str(e)}


@router.get("/{user_id}", response={200: dict, 404: dict, 400: dict})
def get_user_by_id(request, user_id: str):
    try:
        from django.contrib.auth import get_user_model
        data = UserService.get_user_profile(user_id)
        return data
    except get_user_model().DoesNotExist:
        return 404, {"detail": "User not found"}
    except Exception as e:
        logger.error(f"Get user by id error: {e}")
        return 400, {"detail": str(e)}