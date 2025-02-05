import os
import django

# Thiết lập Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'subprocess_admin.settings')

# Khởi tạo Django
django.setup()

# Import các module sau khi Django đã được khởi tạo
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from subprocess_app.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})