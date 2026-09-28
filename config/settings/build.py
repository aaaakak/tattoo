"""
Build-time settings.

`vercel build` runs `collectstatic` before the deployment exists, which means two things
must hold that the other settings modules do not satisfy:

1. **No secret may be required.** `prod.py` deliberately raises ImproperlyConfigured when
   `DJANGO_SECRET_KEY` is absent -- correct for a server, fatal for a build. A build
   machine must not depend on production secrets.

2. **No dev-only package may be imported.** `dev.py` adds `debug_toolbar` to
   INSTALLED_APPS, but `django-debug-toolbar` is a dev-group dependency and must not be
   installed in a production build, so `dev` cannot be imported there either.

This module exists only to let static files be collected. It inherits `base`, keeps DEBUG
off, and grants nothing else. It is never used to *serve* anything: the WSGI entrypoint
that Vercel loads resolves to `config.settings.prod`, which still hard-fails on a missing
secret. Nothing here weakens production.
"""

from .base import *

# A build must not need a real secret, but it also must not send a debug-looking key to
# production -- hence a fixed, obviously-non-production value used nowhere else.
SECRET_KEY = "build-only-not-a-production-secret"

DEBUG = False

ALLOWED_HOSTS = ["*"]

# Static collection target. Manifest storage is not used here: the manifest would bake the
# build-time hash into the bundle, and Vercel hashes and serves the collected files itself.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
