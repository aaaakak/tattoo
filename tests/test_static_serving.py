"""
Static-asset serving in production.

The production site loaded its HTML but was completely unstyled: every `/static/` URL
returned the 404 page. The cause was routing, not collection.

`vercel.json` routes `/(.*) -> web`, so `/static/*` is delivered to the Django service.
Vercel documents that routing into a service is **final** — it does not fall back to its own
static handler once a service matches. Vercel's Django guide says it "serves the collected
files from the Vercel CDN", which is true for a single-service project but cannot apply
here, because the catch-all intercepts the request first.

Django then received `/static/...` and could not answer: `config/urls.py` registers
`static()` only under `DEBUG`, and nothing else served the directory. So the project needed
to serve its own static files, which is what WhiteNoise is for — and Vercel's Django guide
lists WhiteNoise as compatible.

These tests pin the three things that make that work, because each fails silently on its own:

1. `WhiteNoiseMiddleware` present and ordered immediately after `SecurityMiddleware`.
2. The `staticfiles` storage in both `build` and `prod` understands compressed variants, so
   what the build writes is what the runtime serves.
3. The collected URLs actually resolve — asserted end-to-end against the production
   settings, not inferred from configuration.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent

# The stylesheets and script the base template loads. If any of these 404, the site renders
# unstyled, which is the exact production symptom this file exists to prevent.
STATIC_ASSETS = [
    "css/tokens.css",
    "css/base.css",
    "css/layout.css",
    "css/components.css",
    "css/pages.css",
    "js/main.js",
]


def _venv_python() -> str:
    return str(BASE_DIR / ".venv" / "bin" / "python")


def _run(probe: str, settings: str, extra: dict | None = None) -> tuple[int, str]:
    import secrets

    env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
    env["DJANGO_SETTINGS_MODULE"] = settings
    if settings.endswith("prod"):
        env["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(60)
        env["ALLOWED_HOSTS"] = "testserver"
        # The test client speaks HTTP; production redirects it to HTTPS. Disabled only for
        # this probe so the static assertions are not answered by a 301.
        env["SECURE_SSL_REDIRECT"] = "False"
    else:
        env["DJANGO_SECRET_KEY"] = "x" * 60
    if extra:
        env.update(extra)
    r = subprocess.run([_venv_python(), "-c", probe],
                       cwd=BASE_DIR, capture_output=True, text=True, env=env)
    return r.returncode, f"{r.stdout}{r.stderr}"


# --------------------------------------------------------------------------------------
# Middleware wiring
# --------------------------------------------------------------------------------------
def test_whitenoise_middleware_present_and_immediately_after_security():
    """
    Order is a correctness requirement, not a style preference.

    WhiteNoise must run before the other middleware so it can answer a static request
    directly. Placed later it still imports cleanly and still passes a naive presence check,
    while serving nothing — so the position is asserted explicitly.
    """
    code, out = _run(
        "import django; django.setup();"
        "from django.conf import settings;"
        "print('MW', '|'.join(settings.MIDDLEWARE))",
        "config.settings.dev",
    )
    assert code == 0, out[-600:]
    line = next(ln for ln in out.splitlines() if ln.startswith("MW "))
    chain = line[3:].split("|")

    assert "whitenoise.middleware.WhiteNoiseMiddleware" in chain, (
        "WhiteNoiseMiddleware is missing, so nothing serves /static/ in production:\n"
        f"{chain}"
    )
    assert chain.index("whitenoise.middleware.WhiteNoiseMiddleware") == 1, (
        "WhiteNoiseMiddleware must sit immediately after SecurityMiddleware. Found at "
        f"index {chain.index('whitenoise.middleware.WhiteNoiseMiddleware')} in:\n{chain}"
    )
    assert chain[0].endswith("SecurityMiddleware"), chain[:2]


def test_whitenoise_is_a_runtime_dependency():
    """It must be in main dependencies, not a dev group, or production cannot import it."""
    text = (BASE_DIR / "pyproject.toml").read_text(encoding="utf-8")
    main_deps = text.split("[dependency-groups]")[0]
    assert "whitenoise" in main_deps, (
        "whitenoise must be a production dependency — it runs in the deployed process"
    )


# --------------------------------------------------------------------------------------
# Storage backends
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("settings", ["config.settings.prod", "config.settings.build"])
def test_storage_handles_compressed_manifest_variants(settings):
    """
    Build and runtime must agree on the storage backend.

    WhiteNoise serves the compressed variants, so the build has to generate them. If the
    build collected with plain manifest storage, production would look for `.gz` files that
    were never written. This is the same class of mismatch that previously produced a
    missing `staticfiles.json`.
    """
    code, out = _run(
        "import django; django.setup();"
        "from django.conf import settings;"
        "print('BACKEND', settings.STORAGES['staticfiles']['BACKEND'])",
        settings,
    )
    assert code == 0, out[-600:]
    assert "CompressedManifestStaticFilesStorage" in out, (
        f"{settings} does not use WhiteNoise's compressed manifest storage:\n{out[-300:]}"
    )


# --------------------------------------------------------------------------------------
# End-to-end serving
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("asset", STATIC_ASSETS)
def test_production_serves_each_static_asset(asset):
    """
    The real symptom, asserted directly: request the URL the template would generate and
    require a 200 with a real body.

    Skipped when `staticfiles/` has not been collected, so a fresh clone is not failed for a
    missing build artefact — run `manage.py collectstatic` first to exercise it.
    """
    collected = BASE_DIR / "staticfiles"
    if not collected.exists():
        pytest.skip("staticfiles/ not collected; run collectstatic to exercise this")

    probe = f'''
import django; django.setup()
from django.test import Client
from django.templatetags.static import static

url = static("{asset}")
r = Client().get(url)
body = b"".join(r.streaming_content) if getattr(r, "streaming", False) else r.content
print("URL", url)
print("STATUS", r.status_code)
print("CTYPE", r.headers.get("Content-Type", ""))
print("BYTES", len(body))
print("HEAD", body[:24].decode("utf-8", "replace").replace(chr(10), " "))
'''
    code, out = _run(probe, "config.settings.prod")
    assert code == 0, out[-700:]

    status = next((ln.split()[1] for ln in out.splitlines() if ln.startswith("STATUS ")), "")
    ctype = next((ln.split(" ", 1)[1] for ln in out.splitlines() if ln.startswith("CTYPE ")), "")
    nbytes = next((ln.split()[1] for ln in out.splitlines() if ln.startswith("BYTES ")), "0")
    head = next((ln.split(" ", 1)[1] for ln in out.splitlines() if ln.startswith("HEAD ")), "")

    assert status == "200", (
        f"{asset} returned HTTP {status} under production settings. This is the unstyled-site "
        f"failure: the template references a URL nothing serves.\n{out[-400:]}"
    )
    assert len(head) > 0, f"{asset} returned an empty body"
    assert int(nbytes) > 100, f"{asset} body is suspiciously small ({nbytes} bytes)"

    if asset.endswith(".css"):
        assert "text/css" in ctype, f"{asset} served with content-type {ctype!r}"
    if asset.endswith(".js"):
        assert "javascript" in ctype, f"{asset} served with content-type {ctype!r}"


def test_no_static_url_resolves_to_the_404_page():
    """
    A 404 for a static asset is served as Django's styled 404 HTML, which the browser then
    tries to parse as CSS. Assert the failure mode itself cannot occur.
    """
    if not (BASE_DIR / "staticfiles").exists():
        pytest.skip("staticfiles/ not collected")

    probe = '''
import django; django.setup()
from django.test import Client
from django.templatetags.static import static
c = Client()
bad = []
for a in ["css/tokens.css","css/base.css","css/layout.css","css/components.css",
          "css/pages.css","js/main.js"]:
    r = c.get(static(a))
    ct = r.headers.get("Content-Type","")
    if r.status_code != 200 or "text/html" in ct:
        bad.append(f"{a} -> {r.status_code} {ct}")
print("BAD", bad)
'''
    code, out = _run(probe, "config.settings.prod")
    assert code == 0, out[-700:]
    line = next(ln for ln in out.splitlines() if ln.startswith("BAD "))
    assert line.strip() == "BAD []", (
        f"static assets are not being served as assets:\n{line}"
    )
