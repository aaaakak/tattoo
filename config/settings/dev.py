"""Development settings: DEBUG on, permissive hosts, console email."""

from .base import *
from .base import INSTALLED_APPS, MIDDLEWARE, env

DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0"]

INTERNAL_IPS = ["127.0.0.1"]

# In-process cache. No Redis at this scale -- see docs/architecture.md section 2.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "tattoweb-dev",
    }
}

INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]

# DebugToolbarMiddleware must sit AFTER GZipMiddleware (debug_toolbar.W003): it needs to
# observe uncompressed responses.
MIDDLEWARE = [*MIDDLEWARE, "debug_toolbar.middleware.DebugToolbarMiddleware"]

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
    "RESULTS_CACHE_SIZE": 50,
}

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
