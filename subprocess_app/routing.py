from django.urls import path
from .consumers import TerminalConsumer,TerminalConsumerID
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Đặt pattern cụ thể (với deployment_id) lên trước
    re_path(r'^ws/terminal/(?P<deployment_id>\d+)/$', consumers.TerminalConsumerID.as_asgi()),
    # Pattern chung đặt sau
    re_path(r'^ws/terminal/$', consumers.TerminalConsumer.as_asgi()),
]