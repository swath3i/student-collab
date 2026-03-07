from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI
from ninja_jwt.authentication import JWTAuth

api = NinjaAPI(auth=JWTAuth())

# Public routes (no auth needed)
from core.routes.social_auth import router as auth_router
api.add_router("/auth", auth_router, auth=None)

# Protected routes
from core.routes.user_api import router as user_router
api.add_router("/users", user_router)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
]