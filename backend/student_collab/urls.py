from ninja import NinjaAPI, Router
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.routes.social_auth import router as auth_router
from core.routes.user_api import router as user_router
from core.routes.profile_api import router as profile_router
from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from django.conf import settings

api = NinjaAPI(
    version="1.0",
    title="TeamUp API",
    description="Student Collaboration & Project Matching Platform",
    urls_namespace="private_api",
)


class AuthBearer:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, request):
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return None
        token = auth.split("Bearer ")[1]
        authenticator = JWTAuthentication()
        try:
            validated_token = authenticator.get_validated_token(token)
            user = authenticator.get_user(validated_token)
            if not user.is_active:
                return None
            request.user = user
            return user
        except Exception:
            return None


# Public routes (no auth)
api.add_router("v1/auth/", auth_router)

# Protected routes (auth required)
router = Router()
api.add_router("v1/", router, auth=[AuthBearer()])
router.add_router("profile", profile_router, tags=["profile"])
router.add_router("user", user_router, tags=["user"])


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)