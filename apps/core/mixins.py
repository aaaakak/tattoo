"""
View mixins for the public site.

`MetadataMixin` is the single way a view supplies SEO metadata. Without it, each view
would have to remember to set title, description, canonical, og_type and structured data
individually — and would eventually forget one.
"""

from __future__ import annotations

from typing import Any

from django.views.generic.base import ContextMixin

from services import seo


class MetadataMixin(ContextMixin):
    """
    Adds the `meta_*` context keys consumed by base/head.html.

    Subclasses set:
      meta_title        — short title fragment (the site suffix is appended by seo)
      meta_description  — plain-text description
      meta_robots       — e.g. "noindex, nofollow" for confirmation pages

    or override `get_meta_object()` to return the model instance whose own SEO fields
    should take precedence.
    """

    meta_title: str = ""
    meta_description: str = ""
    meta_robots: str = ""
    meta_og_type: str = ""

    def get_meta_object(self) -> Any | None:
        """Return the object whose meta_title/meta_description should win, if any."""
        return getattr(self, "object", None)

    def get_structured_data(self) -> list[dict]:
        """Objects to embed as JSON-LD. Override per view for richer schema."""
        return []

    def get_meta_title(self) -> str:
        return self.meta_title

    def get_meta_description(self) -> str:
        return self.meta_description

    def get_meta_context(self) -> dict[str, Any]:
        obj = self.get_meta_object()
        return seo.build_context(
            self.request,
            obj=obj,
            title=self.get_meta_title(),
            description=self.get_meta_description(),
            og_type=self.meta_og_type,
            robots=self.meta_robots,
            structured_data=self.get_structured_data(),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_meta_context())
        return ctx
