"""
Base Django settings -- shared by dev, test and prod.

Everything environment-specific lives in the leaf modules (dev.py / test.py / prod.py).
prod.py hard-fails on a missing secret key. See docs/architecture.md section 6.
"""

from pathlib import Path

import environ

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# --------------------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------------------
SECRET_KEY=env('DJANGO_SECRET_KEY', default="dev-only-insecure-key-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

SITE_NAME = env("SITE_NAME", default="TattoWeb")

# --------------------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------------------
DJANGO_APPS = [
    # Replace the default admin site via AdminConfig.default_site rather than by
    # reassigning admin.site in an AppConfig.ready(). Django's AdminConfig.ready()
    # runs autodiscover() against default_site, so every @admin.register decorator
    # targets the custom site from the start -- whereas swapping admin.site afterwards
    # leaves the real site empty because the modules were already imported.
    "apps.core.admin_config.TattoWebAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "rest_framework",
]

LOCAL_APPS = [
    "apps.core",
    "apps.artists",
    "apps.tattoos",
    "apps.artworks",
    "apps.gallery",
    "apps.clients",
    "apps.booking",
    "apps.shop",
    "apps.contact",
    "apps.accounts",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.gzip.GZipMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Site-wide CMS data: nav, SiteSettings, ArtistProfile.
                # Must never raise on an empty database, or every page 500s before
                # the artist has logged in and created content.
                "apps.core.context_processors.site_context",
            ],
            # Registered as builtins so templates never need {% load tw_tags %}.
            "builtins": [
                "apps.core.templatetags.tw_tags",
            ],
        },
    },
]

# --------------------------------------------------------------------------------------
# Database -- PostgreSQL 15
# --------------------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        'DATABASE_URL',
        default='postgres://temurbek@127.0.0.1:5432/tattoweb',
    )
}

# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "services": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}


# --------------------------------------------------------------------------------------
# Static and media
# --------------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Cache-busting stamp appended to static asset URLs as ?v=<stamp>.
#
# Without this, a browser caches layout.css / main.js and a code change appears to have
# no effect -- which produces phantom bugs that look like logic errors. Production uses
# ManifestStaticFilesStorage (content hashes) instead; this covers DEBUG where manifests
# are not generated.
STATIC_VERSION = env("STATIC_VERSION", default="dev1")

MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Upload cap, enforced server-side. See docs/architecture.md section 8.
IMAGE_MAX_UPLOAD_MB = env.int("IMAGE_MAX_UPLOAD_MB", default=12)

# --------------------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "admin:index"
LOGOUT_REDIRECT_URL = "core:home"

# --------------------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("SITE_TIMEZONE", default="Europe/Berlin")
USE_I18N = True
USE_TZ = True   # all datetimes tz-aware in Postgres -- required by the availability engine

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------------------
# Email (optional -- booking notifications log instead when unset)
# --------------------------------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
default_from = env("DEFAULT_FROM_EMAIL", default="studio@example.com")
DEFAULT_FROM_EMAIL = default_from
SERVER_EMAIL = default_from

# --------------------------------------------------------------------------------------
# Django REST Framework -- authenticated, administrative JSON only.
# The public API belongs to FastAPI at /api/v1. See docs/fastapi.md section 2.
# --------------------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 24,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/hour"},
}

# --------------------------------------------------------------------------------------
# Cross-layer integration
# --------------------------------------------------------------------------------------
# Internal visual-system reference page. Defaults to DEBUG; force off in production.
DESIGN_SYSTEM_ENABLED = env.bool("DESIGN_SYSTEM_ENABLED", default=DEBUG)

FASTAPI_BASE_URL = env("FASTAPI_BASE_URL", default="http://127.0.0.1:8001")
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://127.0.0.1:8000", "http://localhost:8000"],
)

# --------------------------------------------------------------------------------------
# Rate limiting (django-ratelimit) -- booking and contact are the abuse surfaces
# --------------------------------------------------------------------------------------
RATELIMIT_ENABLE = env.bool("RATELIMIT_ENABLE", default=True)
RATELIMIT_USE_CACHE = "default"
