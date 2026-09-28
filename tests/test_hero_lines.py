"""Hero headline splitting drives the per-line masked reveal."""

import pytest

from apps.core.models import SiteSettings


@pytest.mark.django_db
def test_hero_lines_split_on_newlines():
    site = SiteSettings.load()
    site.hero_title = "ART\nTHAT\nMOVES\nWITH YOU"
    site.save()
    assert site.hero_lines == ["ART", "THAT", "MOVES", "WITH YOU"]


@pytest.mark.django_db
def test_hero_lines_ignores_blank_lines():
    site = SiteSettings.load()
    site.hero_title = "ART\n\n\nMOVES"
    site.save()
    assert site.hero_lines == ["ART", "MOVES"]


@pytest.mark.django_db
def test_hero_lines_empty_is_safe():
    site = SiteSettings.load()
    site.hero_title = ""
    site.save()
    assert site.hero_lines == []
