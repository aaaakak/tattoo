"""Test settings: fast hashing, no toolbar, in-memory-ish DB behaviour."""

from .base import *

DEBUG = False

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

# Fast password hashing -- test runs should not spend time on PBKDF2.
PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "tattoweb-test",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MEDIA_ROOT = BASE_DIR / "media" / "_test"

# Rate limiting would make tests flaky; it is exercised explicitly in its own test module.
RATELIMIT_ENABLE = False

LOGGING["root"]["level"] = "ERROR"
