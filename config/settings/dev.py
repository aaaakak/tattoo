"""
Development settings: DEBUG on, permissive hosts, console email.

The debug toolbar is attached **only when the package is installed**. It is a dev-group
dependency, so it is absent wherever dev groups are excluded -- a production install, a CI
build, and Vercel's build environment. Importing it unconditionally made this module
unimportable there, which broke every Django management command that resolved to dev
settings. The most visible casualty was Vercel's automatic `collectstatic`, which invokes
bare `manage.py` (no `--settings`) and therefore lands on this module:

    ModuleNotFoundError: No module named 'debug_toolbar'

Guarding the import is strictly better than the alternatives: it does not add a dev
dependency to production, and it means `uv sync` without dev groups still yields a working
`manage.py`. Nothing about production changes -- `config.settings.prod` never imported the
toolbar and still does not.
"""

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

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)


def _debug_toolbar_available() -> bool:
    """
    True only when django-debug-toolbar is importable in this environment.

    `find_spec` normally returns None for a missing module, but it *propagates* an
    ImportError when an import hook raises one -- which is what a blocked or partially
    installed package does. So the call is wrapped: absence must yield False, never an
    exception, because this runs during settings import.
    """
    import importlib.util

    try:
        return importlib.util.find_spec("debug_toolbar") is not None
    except (ImportError, ValueError):
        return False


if _debug_toolbar_available():
    INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]

    # DebugToolbarMiddleware must sit AFTER GZipMiddleware (debug_toolbar.W003): it needs to
    # observe uncompressed responses.
    MIDDLEWARE = [*MIDDLEWARE, "debug_toolbar.middleware.DebugToolbarMiddleware"]

    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
        "RESULTS_CACHE_SIZE": 50,
    }
