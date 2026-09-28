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

# --- Database connection reuse: disabled, deliberately ---
# CONN_MAX_AGE = 0 means Django opens a connection per request and closes it at the end of
# that request. On a long-running server that looks wasteful; on Vercel it is the only
# correct setting, for four independent reasons -- any one of which is sufficient:
#
# 1. Supavisor is the pooler, and Django's PostgreSQL notes state CONN_MAX_AGE must be 0
#    when connection pooling is used. The pooler owns connection reuse; a second layer of
#    client-side persistence competes with it.
#
# 2. Django's databases reference says persistent connections should be disabled when
#    connection parameters are modified per connection. This project pins the session
#    timezone on connect (SET TIME ZONE 'UTC'), which is exactly that case.
#
# 3. Vercel suspends idle function instances in memory, and Django enforces CONN_MAX_AGE
#    expiry at request boundaries. A suspended instance runs no requests, so the expiry
#    check never fires and the connection stays open until the pooler's own timeout --
#    minutes later. Vercel's own documentation describes this as a leaked connection and
#    notes that Supabase caps concurrent pooler connections, where leaking a fraction of
#    the budget is materially harmful.
#
# 4. Every deployment suspends the previous version's instances permanently. With a
#    non-zero CONN_MAX_AGE each orphaned instance holds its connections until the pooler
#    times them out, so a deploy silently consumes pooler capacity.
#
# Connection reuse is not lost: Supavisor pools server-side, which is what the transaction
# pooler exists to provide. Set explicitly rather than left to Django's default so the
# intent is recorded and a future reader does not "helpfully" raise it.
DATABASES["default"]["CONN_MAX_AGE"] = 0

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
