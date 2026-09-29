"""
Build-time settings.

`vercel build` runs `collectstatic` before the deployment exists, which means two things
must hold that the other settings modules do not satisfy:

1. **No secret may be required.** `prod.py` deliberately raises ImproperlyConfigured when
   `DJANGO_SECRET_KEY` is absent -- correct for a server, fatal for a build. A build
   machine must not depend on production secrets.

2. **No dev-only package may be imported.** `dev.py` conditionally installs the debug
   toolbar, but `django-debug-toolbar` is a dev-group dependency and must not be installed
   in a production build, so `dev` is not a safe build target.

This module exists only to let static files be collected. It inherits `base`, keeps DEBUG
off, and grants nothing else. It is never used to *serve* anything: the WSGI entrypoint that
Vercel loads resolves to `config.settings.prod`, which still hard-fails on a missing secret.
Nothing here weakens production.
"""

from .base import *
from .base import media_storage_config

# A build must not need a real secret. This value is fixed, obviously non-production, and
# used nowhere else -- it exists only so the settings module can import on a build machine.
SECRET_KEY = "build-only-not-a-production-secret"

DEBUG = False

ALLOWED_HOSTS = ["*"]

# Manifest storage, deliberately, even though this module never serves a request.
#
# Production serves with ManifestStaticFilesStorage, so `{% static %}` resolves filenames
# through the generated `staticfiles.json`. If the build collected without producing that
# manifest, every stylesheet and script URL would fail at runtime with:
#
#     ValueError: Missing staticfiles manifest entry for 'css/base.css'
#
# That is a broken site rather than a failed build, which is strictly worse: the
# deployment would look healthy while serving unstyled pages.
#
# An earlier version of this module used plain StaticFilesStorage, on the untested
# assumption that Vercel hashes and serves the collected files itself. The assumption was
# wrong, and it is recorded here so it is not repeated.
STORAGES = {
    "default": media_storage_config(),
    # Must match prod.py: WhiteNoise serves the compressed variants, so the build has to
    # generate them. Using a different storage here would collect files production cannot
    # serve -- the failure this module already documents once for the manifest.
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
