"""
Vercel deployment-configuration guards.

The deploy shape of this project is two services in one Vercel project, and the routing
between them is the only thing keeping Django and FastAPI apart. That separation is
load-bearing and invisible at runtime: if the `/api/v1/` rewrite were dropped, FastAPI
would be unreachable; if the catch-all were dropped, the website would 404.

These tests exist because the original Vercel build error offered a fix that would have
silently deleted half the application -- a single `[tool.vercel] entrypoint` making FastAPI
the entire deployment. Nothing in the test suite would have noticed. Now something does.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
VERCEL_JSON = BASE_DIR / "vercel.json"

EXPECTED_SERVICES = {"web", "api"}


@pytest.fixture(scope="module")
def config() -> dict:
    assert VERCEL_JSON.exists(), "vercel.json is missing -- Vercel would guess the entrypoint"
    return json.loads(VERCEL_JSON.read_text(encoding="utf-8"))


def test_uses_services_not_a_single_entrypoint(config):
    """Two applications require two services; a single entrypoint cannot express both."""
    assert "services" in config, (
        "vercel.json has no `services` block. A single-entrypoint deployment cannot serve "
        "both Django and FastAPI."
    )
    assert set(config["services"]) == EXPECTED_SERVICES


def test_django_is_deployed_and_serves_the_catch_all(config):
    """Django must be present and own every path the API does not claim."""
    web = config["services"]["web"]
    assert web["entrypoint"] == "config.wsgi:application", (
        "The web service must be Django. Naming the FastAPI entrypoint here would delete "
        "the website."
    )

    catch_all = config["rewrites"][-1]
    assert catch_all["source"] == "/(.*)"
    assert catch_all["destination"]["service"] == "web"


def test_fastapi_owns_api_v1_and_is_routed_first(config):
    """
    The API rewrite must precede the catch-all, because rewrites are first-match-wins.

    Reversed, `/api/v1/...` would be swallowed by Django and the API would be unreachable.
    """
    api_rewrite = config["rewrites"][0]
    assert api_rewrite["source"] == "/api/v1/(.*)"
    assert api_rewrite["destination"]["service"] == "api"

    web_rewrite_index = next(
        i for i, r in enumerate(config["rewrites"]) if r["destination"]["service"] == "web"
    )
    assert web_rewrite_index > 0, "the catch-all must not be evaluated before /api/v1/"


def test_every_service_is_publicly_routable(config):
    """A service with no rewrite is dead configuration and would receive no traffic."""
    routed = {
        r["destination"]["service"]
        for r in config["rewrites"]
        if isinstance(r.get("destination"), dict) and "service" in r["destination"]
    }
    unrouted = set(config["services"]) - routed
    assert not unrouted, f"services defined but not routed: {unrouted}"


def test_no_single_service_tool_vercel_entrypoint():
    """
    `[tool.vercel] entrypoint` in pyproject.toml is a single top-level value.

    It cannot describe two services, and setting it alongside `services` is a contradiction
    that would re-create the ambiguity behind the original build failure.
    """
    pyproject = (BASE_DIR / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.vercel]" not in pyproject, (
        "pyproject.toml declares a single Vercel entrypoint while vercel.json declares two "
        "services. Remove the pyproject entry so the services block is authoritative."
    )


def test_build_settings_do_not_require_secrets():
    """
    `collectstatic` runs at build time, before any environment exists.

    `config.settings.prod` correctly refuses to import without a secret key, so the build
    must not use it. The build module is asserted to keep DEBUG off -- a build that shipped
    DEBUG=True would be a far worse outcome than a failed build.
    """
    # Assert on the module's real behaviour rather than on its text: a docstring may
    # legitimately mention debug_toolbar while explaining why it is excluded.
    import os
    import subprocess
    import sys

    probe = (
        "import os;"
        "os.environ['DJANGO_SETTINGS_MODULE']='config.settings.build';"
        "import django; django.setup();"
        "from django.conf import settings;"
        "print('DEBUG', settings.DEBUG);"
        "print('TOOLBAR', 'debug_toolbar' in settings.INSTALLED_APPS);"
        "print('SECRET_OK', bool(settings.SECRET_KEY))"
    )
    env = {k: v for k, v in os.environ.items()
           if k not in ("DJANGO_SECRET_KEY", "ALLOWED_HOSTS")}
    result = subprocess.run([sys.executable, "-c", probe],
                            cwd=BASE_DIR, capture_output=True, text=True, env=env)
    assert result.returncode == 0, (
        f"config.settings.build failed to import without secrets:\n"
        f"{(result.stdout + result.stderr)[-600:]}"
    )
    out = result.stdout
    assert "DEBUG False" in out, "the build module must not enable DEBUG"
    assert "TOOLBAR False" in out, "the build module must not install debug_toolbar"
    assert "SECRET_OK True" in out, "the build module must be importable with no secret set"
