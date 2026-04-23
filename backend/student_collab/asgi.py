import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'student_collab.settings')

django_asgi_app = get_asgi_application()

from core.consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<connection_id>[^/]+)/$', ChatConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns),
})
