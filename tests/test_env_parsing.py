"""
Empty-environment-variable guards.

The first Vercel deployment failed at settings import with:

    IMAGE_MAX_UPLOAD_MB = env.int("IMAGE_MAX_UPLOAD_MB", default=12)
    ValueError: invalid literal for int() with base 10: ''

Vercel had defined the variable with an **empty value** rather than omitting it, and
`django-environ` treats an empty variable as present — so the declared default was skipped
and `int("")` was evaluated.

That was only one of three consequences of the same mistake. Investing empty values:

    env.int(..., default=12)      -> ValueError, the settings import dies
    env.bool(..., default=True)   -> False, silently disabling SECURE_SSL_REDIRECT
    env.list(..., default=[...])  -> [], silently discarding the default

The settings modules now route every typed read through the `env_int` / `env_bool` /
`env_str` / `env_list` helpers, which treat an empty value as "not supplied". These tests
pin that behaviour for the specific variables involved, and -- more importantly -- assert
that an empty SECURE_SSL_REDIRECT can no longer downgrade production silently, which is a
security property rather than a convenience one.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent

# Variables whose empty-string behaviour is asserted here.
INT_VARS = ["IMAGE_MAX_UPLOAD_MB", "SECURE_HSTS_SECONDS", "EMAIL_PORT"]
BOOL_VARS = ["SECURE_SSL_REDIRECT", "EMAIL_USE_TLS", "RATELIMIT_ENABLE", "DEBUG"]

# The Vercel build settings must import with nothing configured at all.
CLEARED = {
    "DJANGO_SECRET_KEY", "ALLOWED_HOSTS", "DJANGO_SETTINGS_MODULE",
    *INT_VARS, *BOOL_VARS,
}


def _run(probe: str, settings_module: str, extra: dict[str, str] | None = None) -> str:
    """
    Run a probe in a clean subprocess so os.environ edits cannot leak between tests.

    A real `.env` is moved aside for the duration, because `environ.Env.read_env()` loads
    it and would otherwise re-supply values the test deliberately removed -- which would
    make "no secret configured" impossible to express.
    """
    import shutil

    env_file = BASE_DIR / ".env"
    stash = BASE_DIR / ".env.test-stash"
    moved = False
    if env_file.exists():
        shutil.move(str(env_file), str(stash))
        moved = True
    try:
        env = {k: v for k, v in os.environ.items() if k not in CLEARED}
        env["DJANGO_SETTINGS_MODULE"] = settings_module
        if extra:
            env.update(extra)
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=BASE_DIR, capture_output=True, text=True, env=env,
        )
        return f"exit={result.returncode}\n{result.stdout}{result.stderr}"
    finally:
        if moved:
            shutil.move(str(stash), str(env_file))


@pytest.mark.parametrize("value", ["", "   "])
@pytest.mark.parametrize("var", INT_VARS)
def test_empty_int_variable_falls_back_to_default(var, value):
    """
    An empty value must behave like an unset one, for every integer setting.

    This is the exact failure that broke the first deployment: before the fix,
    IMAGE_MAX_UPLOAD_MB="" raised ValueError during settings import.
    """
    probe = (
        "from django.conf import settings;"
        'from django.conf import settings; print("VALUE", getattr(settings, "' + var + '"))'
    )
    out = _run(probe, "config.settings.build", {var: value})
    assert "ValueError" not in out, f"{var}={value!r} crashed settings import:\n{out}"
    assert "exit=0" in out, f"{var}={value!r} did not import:\n{out}"


def test_image_max_upload_mb_semantics():
    """
    The contract the task specifies: default 12 when missing or empty, an explicit valid
    integer overrides, and a genuinely malformed value still fails loudly.
    """
    probe = "from django.conf import settings; print('VALUE', settings.IMAGE_MAX_UPLOAD_MB)"

    for label, extra, expected in [
        ("omitted",  {},                     "VALUE 12"),
        ("empty",    {"IMAGE_MAX_UPLOAD_MB": ""},   "VALUE 12"),
        ("spaces",   {"IMAGE_MAX_UPLOAD_MB": "  "}, "VALUE 12"),
        ("12",       {"IMAGE_MAX_UPLOAD_MB": "12"}, "VALUE 12"),
        ("25",       {"IMAGE_MAX_UPLOAD_MB": "25"}, "VALUE 25"),
    ]:
        out = _run(probe, "config.settings.build", extra)
        assert expected in out, f"{label} did not yield {expected!r}:\n{out}"

    # Garbage is a mistake, not an ambiguity, and must not be silently swallowed.
    out = _run(probe, "config.settings.build", {"IMAGE_MAX_UPLOAD_MB": "abc"})
    assert "ValueError" in out, (
        "A malformed IMAGE_MAX_UPLOAD_MB was accepted silently; it must raise so the "
        "operator notices the typo:\n" + out
    )


def test_empty_security_flag_cannot_downgrade_production():
    """
    The dangerous half of the bug, and the reason this test exists.

    With an empty SECURE_SSL_REDIRECT, the raw `env.bool(..., default=True)` returns False
    *without any warning*, so a production deployment configured by a platform that creates
    empty variables would silently stop redirecting to HTTPS. Empty must mean "use the
    default", which is True.
    """
    import secrets

    probe = (
        "from django.conf import settings;"
        "print('SSL', settings.SECURE_SSL_REDIRECT);"
        "print('HSTS', settings.SECURE_HSTS_SECONDS)"
    )
    extra = {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(60),
        "ALLOWED_HOSTS": "example.com",
        "SECURE_SSL_REDIRECT": "",
        "SECURE_HSTS_SECONDS": "",
    }
    out = _run(probe, "config.settings.prod", extra)
    assert "exit=0" in out, f"prod did not import with empty security vars:\n{out}"
    assert "SSL True" in out, (
        "An empty SECURE_SSL_REDIRECT disabled HTTPS redirection in production:\n" + out
    )
    assert "HSTS 31536000" in out, (
        "An empty SECURE_HSTS_SECONDS discarded the HSTS default:\n" + out
    )


def test_explicit_false_is_still_honoured():
    """
    The fix must not make the settings stubborn: an operator who explicitly sets False
    gets False. Only *ambiguity* is resolved, never a deliberate choice.
    """
    import secrets

    out = _run(
        "from django.conf import settings; print('SSL', settings.SECURE_SSL_REDIRECT)",
        "config.settings.prod",
        {
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(60),
            "ALLOWED_HOSTS": "example.com",
            "SECURE_SSL_REDIRECT": "False",
        },
    )
    assert "SSL False" in out, f"an explicit False was overridden:\n{out}"


def test_prod_still_refuses_without_a_secret_key():
    """
    The empty-value tolerance must not have softened the hard failure that protects
    production from a forgotten secret.
    """
    out = _run("import django; django.setup()", "config.settings.prod")
    assert "exit=1" in out, f"prod booted without a secret key:\n{out}"
    assert "ImproperlyConfigured" in out, f"prod failed for the wrong reason:\n{out}"


def test_settings_modules_do_not_call_raw_typed_env_reads():
    """
    A guard against regression by future edits: the typed reads must go through the
    empty-tolerant helpers, not `env.int` / `env.bool` / `env.list` directly.
    """
    # The helper implementations themselves call env.int/env.bool/env.list by design --
    # that is what makes the empty-value handling work -- and three email settings have an
    # intentional default of "", documented inline. Only a *settings assignment* that
    # bypasses the helpers is a defect.
    allowed_intentional = (
        "EMAIL_HOST = env(",
        "EMAIL_HOST_USER = env(",
        "EMAIL_HOST_PASSWORD = env(",
    )
    offenders = []
    for name in ("base.py", "prod.py"):
        path = BASE_DIR / "config" / "settings" / name
        in_helper = False
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("def env_"):
                in_helper = True
            elif stripped.startswith("def ") and in_helper:
                in_helper = False
            if stripped.startswith("#") or in_helper:
                continue
            if any(stripped.startswith(a) for a in allowed_intentional):
                continue
            if not stripped.startswith(stripped.split(" =")[0] + " ="):
                continue
            for raw in ("env.int(", "env.bool(", "env.list("):
                if raw in stripped and " = " in stripped:
                    offenders.append(f"{name}:{lineno} {stripped[:70]}")
    assert not offenders, (
        "Raw typed env reads bypass the empty-value handling and can crash or silently "
        "downgrade a setting:\n  " + "\n  ".join(offenders)
    )
