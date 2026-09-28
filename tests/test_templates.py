"""
Template hygiene tests.

These guard against template-level defects that render as *visible text* rather than
raising an error — the class of bug that passes every unit test while quietly printing
debug notes onto the live page.

The first version of this suite exists because a multi-line Django {# #} comment was
found rendering as literal text in the page head. Django's {# #} is single-line only;
a multi-line note must use {% comment %}{% endcomment %}.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.template.loader import get_template

TEMPLATE_DIR = Path(settings.BASE_DIR) / "templates"

# Every template in the project, discovered rather than hard-coded.
ALL_TEMPLATES = sorted(
    str(p.relative_to(TEMPLATE_DIR))
    for p in TEMPLATE_DIR.rglob("*.html")
)


def test_templates_were_discovered():
    """Guard against a path change silently emptying this suite."""
    assert len(ALL_TEMPLATES) >= 15, f"only found {len(ALL_TEMPLATES)} templates"


@pytest.mark.parametrize("rel", ALL_TEMPLATES)
def test_template_compiles(rel):
    """Every template must parse. A syntax error should fail here, not in production."""
    get_template(rel)


@pytest.mark.parametrize("rel", ALL_TEMPLATES)
def test_no_multiline_hash_comment(rel):
    """
    {# ... #} spanning multiple lines renders as VISIBLE TEXT.

    Django treats the trailing newline as ordinary content, so a multi-line hash comment
    is not a comment at all -- it is a sentence printed into the page. This is exactly
    what happened in base/head.html and it was caught only by reading the rendered output.
    """
    source = (TEMPLATE_DIR / rel).read_text()
    for match in re.finditer(r"\{#(.*?)#\}", source, re.DOTALL):
        assert "\n" not in match.group(1), (
            f"{rel}: multi-line {{# #}} comment renders as visible text. "
            f"Use {{% comment %}} instead. Offending: {match.group(0)[:80]!r}"
        )


@pytest.mark.parametrize("rel", ALL_TEMPLATES)
def test_no_template_debug_notes(rel):
    """
    Templates must not print developer notes, TODO markers or phase scaffolding as text.
    Anything such should live in a comment block.
    """
    source = (TEMPLATE_DIR / rel).read_text()
    # Strip all comment forms before checking, so real comments are not false positives.
    stripped = re.sub(r"\{#.*?#\}", "", source, flags=re.DOTALL)
    stripped = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", stripped, flags=re.DOTALL)
    stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.DOTALL)

    for marker in ("TODO", "FIXME", "XXX", "NOTE:"):
        assert marker not in stripped, (
            f"{rel}: '{marker}' appears as rendered text (move it inside a comment block)"
        )


@pytest.mark.django_db
def test_rendered_pages_contain_no_comment_syntax(client):
    """
    Rendered HTML must never contain template comment syntax or raw template tags.

    This is the end-to-end version of the checks above: it catches a comment that leaks
    through in any template reachable from a public URL.
    """
    from django.urls import reverse

    urls = ["core:home", "tattoos:list", "artworks:list", "gallery:index", "artists:about"]
    for name in urls:
        body = client.get(reverse(name)).content.decode()
        assert "{#" not in body, f"{name}: leaked {{# #}} comment syntax"
        assert "{%" not in body, f"{name}: leaked template tag syntax"
        assert "{% comment %}" not in body
        assert "endcomment" not in body
