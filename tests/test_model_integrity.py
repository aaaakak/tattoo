"""
Model integrity guards.

`test_every_save_override_calls_super` exists because of a real, silent bug: two models
(`TattooStyle`, `ArtworkCategory`) had a `save()` override that generated a slug and then
returned WITHOUT calling `super().save()`. Nothing was written to the database — no
exception, no warning, `pk` simply stayed None.

The symptom was a permanently empty Styles page while the seeder cheerfully reported
"tattoo styles: 12". It was found only by probing `obj.pk` after a create, which is why
these tests assert *persistence*, not just absence of errors.
"""

from __future__ import annotations

import inspect

import pytest
from django.apps import apps

LOCAL_APPS = [
    "core", "artists", "tattoos", "artworks",
    "gallery", "clients", "booking", "shop", "contact",
]


def _models_with_save_override():
    for app_label in LOCAL_APPS:
        for model in apps.get_app_config(app_label).get_models():
            if "save" in model.__dict__:
                yield model


def test_models_were_discovered():
    """Guard against the discovery loop silently finding nothing."""
    assert len(list(_models_with_save_override())) >= 5


@pytest.mark.parametrize(
    "model", list(_models_with_save_override()), ids=lambda m: m._meta.label
)
def test_every_save_override_calls_super(model):
    """
    A save() override that does not call super().save() silently discards the write.

    This is the highest-value model test in the suite: the failure mode produces no
    exception at all, so only an explicit check catches it.
    """
    source = inspect.getsource(model.__dict__["save"])
    assert "super().save(" in source, (
        f"{model._meta.label}.save() does not call super().save(). "
        "Objects of this model will never be persisted, silently."
    )


# --------------------------------------------------------------------------------------
# Persistence proofs — the behaviour the guard above protects
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_tattoo_style_actually_persists():
    """Regression: this returned pk=None and wrote nothing."""
    from apps.tattoos.models import TattooStyle

    style = TattooStyle.objects.create(name="Persisted Style")
    assert style.pk is not None, "TattooStyle.save() did not write the row"
    assert TattooStyle.objects.filter(pk=style.pk).exists()
    assert style.slug, "slug should be generated when omitted"


@pytest.mark.django_db
def test_artwork_category_actually_persists():
    """Regression: same defect as TattooStyle."""
    from apps.artworks.models import ArtworkCategory

    cat = ArtworkCategory.objects.create(name="Persisted Category")
    assert cat.pk is not None, "ArtworkCategory.save() did not write the row"
    assert ArtworkCategory.objects.filter(pk=cat.pk).exists()


@pytest.mark.django_db
def test_style_update_persists():
    """A second save must update, not vanish."""
    from apps.tattoos.models import TattooStyle

    style = TattooStyle.objects.create(name="Update Me")
    style.description = "changed"
    style.save()
    style.refresh_from_db()
    assert style.description == "changed"
    assert TattooStyle.objects.filter(name="Update Me").count() == 1


@pytest.mark.django_db
def test_style_does_not_overwrite_an_explicit_slug():
    """An editor's custom slug must survive: changing it breaks indexed URLs."""
    from apps.tattoos.models import TattooStyle

    style = TattooStyle.objects.create(name="My Style", slug="custom-slug")
    assert style.slug == "custom-slug"
    style.name = "My Style Renamed"
    style.save()
    style.refresh_from_db()
    assert style.slug == "custom-slug", "save() must not clobber an explicit slug"


@pytest.mark.django_db
def test_category_piece_count_reflects_persisted_rows():
    """The annotate() count the Styles page renders must see real rows."""
    from django.db.models import Count, Q

    from apps.tattoos.models import Tattoo, TattooStyle

    style = TattooStyle.objects.create(name="Counted")
    tattoo = Tattoo.objects.create(title="Piece", status=Tattoo.Status.PUBLISHED)
    tattoo.styles.add(style)

    annotated = TattooStyle.objects.annotate(
        piece_count=Count("tattoos", filter=Q(tattoos__status="published"))
    ).get(pk=style.pk)
    assert annotated.piece_count == 1
