"""
Build-time settings guards.

Two failures are pinned here, both discovered during Vercel deployment.

**1. Dev settings must be importable without the debug toolbar.**
Vercel's Django preset runs its own `collectstatic` using bare `manage.py`, which resolves
`DJANGO_SETTINGS_MODULE` to `config.settings.dev`. That module used to install
`debug_toolbar` unconditionally, so the command died with:

    ModuleNotFoundError: No module named 'debug_toolbar'

because `django-debug-toolbar` is a dev-group dependency and is absent from a production
install. The command is now safe to run wherever dev settings are resolvable.

**2. The build must produce a staticfiles manifest.**
Production serves through `ManifestStaticFilesStorage`, so `{% static %}` resolves filenames
through `staticfiles.json`. A build that collected with plain `StaticFilesStorage` produced
no manifest, and every stylesheet then failed at runtime with:

    ValueError: Missing staticfiles manifest entry for 'css/base.css'

That is a broken site rather than a failed build, which is the worse outcome: the deployment
looks healthy while serving unstyled pages.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


def _venv_python() -> str:
    return str(BASE_DIR / ".venv" / "bin" / "python")


def _run(args: list[str], settings: str | None = None, extra: dict | None = None) -> tuple[int, str]:
    """Run a command with an isolated environment so tests cannot leak into each other."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
    if settings:
        env["DJANGO_SETTINGS_MODULE"] = settings
    if extra:
        env.update(extra)
    result = subprocess.run(args, cwd=BASE_DIR, capture_output=True, text=True, env=env)
    return result.returncode, f"{result.stdout}{result.stderr}"


def test_assumption_debug_toolbar_is_a_dev_only_dependency():
    """
    The whole failure depended on the toolbar not being a production dependency.

    If someone promotes it to `[project.dependencies]` to make the build pass, this test
    fails and points at the real problem instead.
    """
    text = (BASE_DIR / "pyproject.toml").read_text(encoding="utf-8")

    main_deps = text.split("[dependency-groups]")[0].split("dependencies = [")[1]
    assert "debug-toolbar" not in main_deps and "debug_toolbar" not in main_deps, (
        "django-debug-toolbar was added to the MAIN dependencies. It is a development tool "
        "and must not ship in production; fix the settings module instead."
    )

    assert "debug-toolbar" in text.split("[dependency-groups]")[1], (
        "django-debug-toolbar should still be present in the dev dependency group"
    )


def test_dev_settings_import_without_debug_toolbar():
    """
    `config.settings.dev` must import even when the toolbar package is absent.

    Simulated by blocking the import rather than uninstalling it, so the real environment
    is untouched.
    """
    probe = (
        "import sys\n"
        "# Force `import debug_toolbar` to fail, exactly as on a production install.\n"
        "class _Block:\n"
        "    def find_module(self, name, path=None):\n"
        "        return self if name == 'debug_toolbar' or name.startswith('debug_toolbar.') else None\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'debug_toolbar' or name.startswith('debug_toolbar.'):\n"
        "            raise ModuleNotFoundError(\"No module named 'debug_toolbar'\")\n"
        "        return None\n"
        "sys.meta_path.insert(0, _Block())\n"
        "import os\n"
        "os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'\n"
        "import django\n"
        "django.setup()\n"
        "from django.conf import settings\n"
        "print('IMPORTED', settings.DEBUG)\n"
        "print('TOOLBAR', 'debug_toolbar' in settings.INSTALLED_APPS)\n"
    )
    code, out = _run([_venv_python(), "-c", probe])
    assert code == 0, f"dev settings failed to import without the toolbar:\n{out[-700:]}"
    assert "IMPORTED True" in out
    assert "TOOLBAR False" in out, (
        "the toolbar is not installed, so it must not appear in INSTALLED_APPS"
    )


def test_dev_settings_still_install_the_toolbar_when_present():
    """The guard must not disable the toolbar for developers who have it installed."""
    code, out = _run(
        [_venv_python(), "-c",
         "import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings.dev';"
         "import django; django.setup();"
         "from django.conf import settings;"
         "print('TOOLBAR', 'debug_toolbar' in settings.INSTALLED_APPS);"
         "print('MW', any('debug_toolbar' in m for m in settings.MIDDLEWARE))"],
    )
    assert code == 0, out[-500:]
    if "No module named 'debug_toolbar'" in out:
        pytest.skip("debug_toolbar is not installed in this environment")
    assert "TOOLBAR True" in out, "the toolbar should be installed locally"
    assert "MW True" in out


def test_bare_manage_py_collectstatic_works_without_debug_toolbar():
    """
    The exact command Vercel's Django preset runs automatically.

    This is the failure that reached the user's build log, so it is asserted directly
    rather than inferred from the settings test.
    """
    probe = (
        "import sys\n"
        "class _Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'debug_toolbar' or name.startswith('debug_toolbar.'):\n"
        "            raise ModuleNotFoundError(\"No module named 'debug_toolbar'\")\n"
        "        return None\n"
        "sys.meta_path.insert(0, _Block())\n"
        "sys.argv = ['manage.py', 'collectstatic', '--noinput', '--dry-run']\n"
        "import runpy\n"
        "runpy.run_path('manage.py', run_name='__main__')\n"
    )
    code, out = _run([_venv_python(), "-c", probe])
    assert code == 0, (
        "bare `manage.py collectstatic` still crashes without the debug toolbar:\n"
        f"{out[-800:]}"
    )
    assert "No module named 'debug_toolbar'" not in out


def test_build_settings_use_manifest_storage():
    """
    The build must collect a manifest, because production serves through one.

    Asserted on real behaviour: importing the module and inspecting the configured storage.
    """
    code, out = _run(
        [_venv_python(), "-c",
         "import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings.build';"
         "import django; django.setup();"
         "from django.conf import settings;"
         "print('BACKEND', settings.STORAGES['staticfiles']['BACKEND']);"
         "print('DEBUG', settings.DEBUG)"],
    )
    assert code == 0, f"build settings failed to import:\n{out[-700:]}"
    assert "ManifestStaticFilesStorage" in out, (
        "config.settings.build must use ManifestStaticFilesStorage, or the deployed site "
        "will have no staticfiles manifest and every {% static %} URL will fail at runtime"
    )
    assert "DEBUG False" in out, "the build must not enable DEBUG"


def test_production_never_installs_the_debug_toolbar():
    """
    Production must be free of the toolbar regardless of what is installed locally.
    """
    import secrets

    code, out = _run(
        [_venv_python(), "-c",
         "import django; django.setup();"
         "from django.conf import settings;"
         "print('DEBUG', settings.DEBUG);"
         "print('TOOLBAR', 'debug_toolbar' in settings.INSTALLED_APPS);"
         "print('MW', any('debug_toolbar' in m for m in settings.MIDDLEWARE))"],
        settings="config.settings.prod",
        extra={
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(60),
            "ALLOWED_HOSTS": "example.com",
        },
    )
    assert code == 0, out[-600:]
    assert "DEBUG False" in out
    assert "TOOLBAR False" in out, "the debug toolbar must never be installed in production"
    assert "MW False" in out, "the toolbar middleware must never be active in production"
