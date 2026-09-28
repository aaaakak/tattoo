"""
ASGI entrypoint (Django). FastAPI runs as its own process -- see docs/fastapi.md.

The default is ``config.settings.prod`` for the same reason as ``config/wsgi.py``:
an unconfigured production launch must fail on missing secrets rather than fall
back to development settings.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
