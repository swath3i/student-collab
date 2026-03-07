import logging
from ninja import Router
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from core.schemas.schemas import LoginSchema
from core.models import Profile

logger = logging.getLogger(__name__)
User = get_user_model()
router = Router()

GOOGLE_CLIENT_ID = "959579794283-n5grmsa1kh3ulmvkk4j3eivr56m3pie4.apps.googleusercontent.com"


@router.post("/login", auth=None, response={200: dict, 400: dict})
def login(request, payload: LoginSchema):
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        idinfo = id_token.verify_oauth2_token(
            payload.idToken,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )

        email = idinfo["email"]
        name = idinfo.get("name", "")
        picture = idinfo.get("picture", "")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "name": name,
            },
        )

        has_profile = Profile.objects.filter(user=user).exists()

        # Update pic if changed
        if not created and user.profile_pic != picture:
            user.profile_pic = picture
            user.save(update_fields=["profile_pic"])

        refresh = RefreshToken.for_user(user)

        return {
            "token": str(refresh.access_token),
            "refresh": str(refresh),
            "has_profile": has_profile,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
            },
        }

    except Exception as e:
        logger.error(f"Login error: {e}")
        return 400, {"detail": str(e)}