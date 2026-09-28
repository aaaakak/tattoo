"""
Secret and configuration guards.

Two of these tests exist because the configuration has a real failure mode that is
invisible until it is expensive:

1. `test_env_is_gitignored` -- `.env` holds the real `DJANGO_SECRET_KEY`. The moment it
   is tracked, that key is in history for ever and the only remedy is rotation. There is
   no second chance on this one, so it is asserted rather than assumed.

2. `test_prod_settings_refuse_to_boot_without_secrets` -- `config/settings/prod.py`
   promises to hard-fail on a missing secret key instead of falling back to a
   development default. That promise is the only thing standing between a forgotten
   environment variable and a production site running with `DEBUG=True` and a
   publicly-known secret key. A promise that is not tested is a comment.

The entropy scan is deliberately a heuristic: it looks for long, high-variety literals
that no human writes on purpose. It is a tripwire for accidental commits, not a proof.
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent

# Directories that are not source: generated, vendored, or local-only.
# `migrations` is excluded deliberately and is safe to exclude: Django generates those
# files from the model definitions, so a literal there is a constraint or dependency
# name, never a credential typed by a human. (ruff excludes it for the same reason.)
SKIP_DIRS = {
    ".venv", ".git", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".idea", "media", "staticfiles", "node_modules", ".mypy_cache",
    "migrations",
}

SCAN_SUFFIXES = {".py", ".html", ".js", ".css", ".md", ".toml", ".yml", ".yaml", ".json", ".cfg", ".ini"}

# Prefixes that identify a credential regardless of entropy.
SECRET_PREFIXES = (
    "sk-", "pk_live_", "pk_test_", "ghp_", "gho_", "github_pat_",
    "xoxb-", "xoxp-", "AKIA", "AIza", "-----BEGIN",
)

# A literal must be at least this long before entropy is even considered, so that
# ordinary words and CSS values are never flagged.
MIN_LITERAL_LEN = 32
MIN_ENTROPY_BITS_PER_CHAR = 3.6

# Values that are intentionally present in the tree and must not trip the scan.
ALLOWED_LITERALS = {
    "dev-only-insecure-key-change-me",
    "replace-me-with-a-long-random-string",
    "django-insecure-",
}

_LITERAL_RE = re.compile(r"""["']([^"'\n]{32,200})["']""")


def _iter_source_files():
    for path in BASE_DIR.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in SCAN_SUFFIXES:
            continue
        yield path


def _shannon_entropy(value: str) -> float:
    """Bits of entropy per character. Long random strings score high; prose scores low."""
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def _looks_like_a_secret(value: str) -> bool:
    """
    Decide whether a literal looks like a credential rather than ordinary code.

    Entropy alone is not enough: a dotted import path, a `reverse("admin:...")` name
    and a deliberately unambiguous reference alphabet are all long and all benign, and
    a scanner that flags them is a scanner that gets switched off. A credential has a
    further property -- it mixes character *classes* for no structural reason.

    So the test is: high entropy AND at least three of the four classes
    (lower, upper, digit, symbol) AND not a dotted/colon-separated identifier path.
    """
    if any(allowed in value for allowed in ALLOWED_LITERALS):
        return False
    # URLs, filesystem paths, hex-colour values and sentences are never secrets.
    if value.startswith(("http://", "https://", "/", "./", "#")):
        return False
    if " " in value or value.startswith("{{"):
        return False
    if not re.fullmatch(r"[A-Za-z0-9_\-+/=.]+", value):
        return False

    # A dotted or colon-separated identifier path (django.middleware.csrf.Foo,
    # admin:index, apps.core.admin_site.TattoWebAdminSite) is structure, not a secret.
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*|:[A-Za-z_][A-Za-z0-9_]*)+", value):
        return False

    classes = sum([
        bool(re.search(r"[a-z]", value)),
        bool(re.search(r"[A-Z]", value)),
        bool(re.search(r"[0-9]", value)),
        bool(re.search(r"[_\-+/=]", value)),
    ])
    if classes < 3:
        return False

    return _shannon_entropy(value) >= MIN_ENTROPY_BITS_PER_CHAR


def test_the_scan_actually_finds_files():
    """Guard against the discovery loop silently scanning nothing and passing vacuously."""
    files = list(_iter_source_files())
    assert len(files) > 40, f"expected to scan the source tree, found {len(files)} files"


def test_no_high_entropy_secrets_in_source():
    """
    No long, high-entropy literal anywhere in the tree.

    A hit here means a credential was almost certainly pasted into source. Rotate it --
    removing the line is not enough once it has been committed.
    """
    offenders: list[str] = []

    for path in _iter_source_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for literal in _LITERAL_RE.findall(line):
                if len(literal) < MIN_LITERAL_LEN:
                    continue
                if _looks_like_a_secret(literal):
                    rel = path.relative_to(BASE_DIR)
                    offenders.append(f"{rel}:{lineno} ({len(literal)} chars, high entropy)")

    assert not offenders, (
        "Possible hard-coded secret(s) found. Do not print the value; rotate it and "
        "move it to the environment:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("prefix", SECRET_PREFIXES)
def test_no_known_credential_prefixes(prefix):
    """Known key prefixes are unambiguous, so they are checked separately from entropy."""
    hits: list[str] = []
    for path in _iter_source_files():
        # This file defines the prefixes, so it necessarily contains them.
        if path.name == "test_secrets.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if prefix in line:
                hits.append(f"{path.relative_to(BASE_DIR)}:{lineno}")
    assert not hits, f"credential prefix {prefix!r} found in: {hits}"


def test_env_file_exists_locally():
    """The real .env is expected on a working checkout; if it is gone, setup was skipped."""
    assert (BASE_DIR / ".env").exists(), ".env is missing -- cp .env.example .env"


def test_env_is_gitignored():
    """
    `.env` must be ignored before the first commit, not after.

    Once a secret is committed, rewriting history is the only removal, so this is
    checked against Git itself rather than by reading .gitignore text.
    """
    git = shutil.which("git")
    assert git, "git is required for this check"

    inside = subprocess.run(
        [git, "rev-parse", "--is-inside-work-tree"],
        cwd=BASE_DIR, capture_output=True, text=True,
    )
    if inside.returncode != 0:
        pytest.skip("not a git repository yet")

    for name in (".env", ".env.local"):
        result = subprocess.run(
            [git, "check-ignore", "--quiet", name],
            cwd=BASE_DIR, capture_output=True, text=True,
        )
        assert result.returncode == 0, f"{name} is NOT gitignored"

    tracked = subprocess.run(
        [git, "ls-files", "--error-unmatch", ".env"],
        cwd=BASE_DIR, capture_output=True, text=True,
    )
    assert tracked.returncode != 0, ".env is TRACKED by git -- rotate the secret key now"


def test_env_example_has_no_real_values():
    """The committed example must contain placeholders only."""
    example = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
    _, _, real = (BASE_DIR / ".env").read_text(encoding="utf-8").partition("\n")
    secret_line = next(
        (line for line in real.splitlines() if line.startswith("DJANGO_SECRET_KEY=")),
        "",
    )
    real_key = secret_line.partition("=")[2].strip()
    if real_key:
        assert real_key not in example, (
            "The real DJANGO_SECRET_KEY value appears in .env.example. "
            "Rotate it and replace the example with a placeholder."
        )


def test_prod_settings_refuse_to_boot_without_secrets():
    """
    `config.settings.prod` must raise rather than fall back to a development default.

    Loaded in a subprocess with the secret deliberately blanked, because importing it
    in-process would poison `sys.modules` for every later test.
    """
    import os
    import sys

    env = dict(os.environ)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"
    env["DJANGO_SECRET_KEY"] = ""
    env["ALLOWED_HOSTS"] = ""

    probe = (
        "import django; django.setup();"
        "print('BOOTED-WITHOUT-SECRETS')"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=BASE_DIR, capture_output=True, text=True, env=env,
    )
    # The probe's own source is echoed in any traceback, so the exit status is the
    # signal: a non-zero exit means django.setup() raised, which is the contract.
    assert result.returncode != 0, (
        "config.settings.prod booted successfully with no DJANGO_SECRET_KEY. "
        "It must raise ImproperlyConfigured instead of falling back to a dev default."
    )
    combined = result.stdout + result.stderr
    assert "ImproperlyConfigured" in combined, (
        f"prod settings refused to boot, but not for the expected reason:\n{combined[-800:]}"
    )
