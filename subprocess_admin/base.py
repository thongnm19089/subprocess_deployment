import socket
PRODUCTION_SERVERS = ['THOMMY']

def check_env():
    for item in PRODUCTION_SERVERS:
        match = item == socket.gethostname()
        if match:
            return True

if check_env():
    PRODUCTION = True
else:
    PRODUCTION = False

if PRODUCTION:
    from .pro import *
else:
    from .dev import *
