import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
import subprocess_app.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'subprocess_admin.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                subprocess_app.routing.websocket_urlpatterns
            )
        )
    ),
})