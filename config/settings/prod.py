"""Production settings. Hard-fails on missing secrets rather than silently defaulting."""

from django.core.exceptions import ImproperlyConfigured

from .base import *
from .base import env, env_bool, env_int, env_list

DEBUG = False

SECRET_KEY=env('DJANGO_SECRET_KEY', default=None)
if not SECRET_KEY or SECRET_KEY.startswith("dev-only"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a unique value in production."
    )

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", default=[])
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set in production.")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", default=[])

# --- Transport security ---
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "DENY"

# --- Database connection reuse ---
# The default of 0 opens a new connection per request. That is correct for development
# (schema changes are picked up without stale connections) but wasteful in production.
# A short reuse window is safe with Supavisor because the pooler owns the real pooling:
# this only avoids re-doing the TLS + auth handshake on every request. Kept modest (60s)
# so idle client connections are released promptly and cannot accumulate against the
# pooler's connection budget.
DATABASES["default"]["CONN_MAX_AGE"] = 60

# --- Cache: database-backed, since Redis is deliberately absent ---
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

# --- Static files served by the reverse proxy, never by Django ---
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}
