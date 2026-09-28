"""
Template tags for TattoWeb.

Registered as a builtin in config/settings/base.py, so templates never need
{% load tw_tags %}.
"""

from __future__ import annotations

import re

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Matches a leading "// NNN — LABEL" style prefix so it can be styled in cobalt.
_META_PREFIX = re.compile(r"^(//\s*\S+)\s*[—-]\s*(.*)$")


@register.simple_tag
def section_marker(index: str, label: str) -> str:
    """
    Render the mono technical metadata marker: // 003 — PLACEMENT: FOREARM

    Used on every major section. This is one of the five core devices of the
    visual identity (see docs/design-system.md section 2).
    """
    return format_html(
        '<span class="meta"><span class="meta__index">// {}</span>'
        '<span class="meta__sep"> — </span>'
        '<span class="meta__label">{}</span></span>',
        index,
        label,
    )


@register.filter
def meta_line(value: str) -> str:
    """Colour the leading technical prefix of a metadata line."""
    if not value:
        return ""
    match = _META_PREFIX.match(value.strip())
    if not match:
        return value
    prefix, rest = match.groups()
    return mark_safe(
        f'<span class="meta__prefix">{prefix}</span> — <span class="meta__rest">{rest}</span>'
    )


@register.filter
def aspect_class(asset) -> str:
    """Return an aspect-ratio utility class from a MediaAsset-like object."""
    if not asset or not getattr(asset, "height", 0):
        return "ratio--square"
    ratio = asset.width / asset.height
    if ratio > 1.2:
        return "ratio--landscape"
    if ratio < 0.85:
        return "ratio--portrait"
    return "ratio--square"


@register.filter
def money(value, currency: str = "EUR") -> str:
    """Format a Decimal price with its currency. Never guesses a currency."""
    if value is None:
        return ""
    symbols = {"EUR": "€", "USD": "$", "GBP": "£"}
    symbol = symbols.get(currency, "")
    try:
        return f"{symbol}{value:,.0f}" if symbol else f"{value:,.0f} {currency}"
    except (TypeError, ValueError):
        return str(value)


@register.filter
def pluralize_count(value) -> str:
    """Mono-friendly count, zero-padded to two digits for the technical aesthetic."""
    try:
        return f"{int(value):02d}"
    except (TypeError, ValueError):
        return str(value)

@register.simple_tag
def variants_for(asset):
    """
    Resolve the sibling assets (derivatives, dither plate, LQIP) for one MediaAsset.

    Exposed as a tag so templates can call it directly:
        {% variants_for asset as v %}
    Returns an empty-ish dict for a None asset so templates never raise.
    """
    if asset is None:
        return {"by_width": {}, "dither": None, "lqip": None, "largest": None}
    from apps.core.ingest import variants_for as _variants_for

    return _variants_for(asset)


@register.simple_tag
def dither_image(
    asset, alt="", ratio="", priority=False, sizes="", resolve="hover", mode="ink",
    placeholder=False,
):
    """
    Render the dither component for an asset.

    Implemented as a tag rather than a recursive include: the resolver runs once, in
    Python, and the template receives a fully-resolved variant chain. A recursive
    {% include %} would re-enter the template engine and is easy to get subtly wrong.
    """
    if asset is None:
        return ""

    from django.template.loader import render_to_string

    v = variants_for(asset)
    return render_to_string(
        "components/dither_image.html",
        {
            "asset": asset,
            "variants": v,
            "alt": alt,
            "ratio": ratio,
            "priority": priority,
            "sizes": sizes,
            "resolve": resolve,
            "mode": mode,
            "placeholder": placeholder,
        },
    )


@register.filter
def json_script_safe(value) -> str:
    """
    Serialise a dict to JSON for embedding in a <script type="application/ld+json">.

    Security note: this is NOT json_script. We are deliberately writing raw JSON into a
    script tag, which is safe here only because the closing-tag sequence is escaped.
    A title containing "</script>" would otherwise terminate the block and allow
    arbitrary markup injection.

    The `<`, `>`, `&` escapes are the standard defence: they are valid JSON string
    escapes, they parse back to the original characters, and they make it impossible for
    the payload to close the script element.
    """
    import json

    from django.utils.safestring import mark_safe

    if value is None:
        return ""
    try:
        raw = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return ""

    # Order matters: ampersand first, or it would double-escape the others.
    raw = (
        raw.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return mark_safe(raw)
