"""
Singleton and base-model behaviour.

These are the invariants every other model relies on, so they are tested directly.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.artists.models import ArtistProfile
from apps.core.models import SiteSettings


@pytest.mark.django_db
def test_site_settings_is_a_true_singleton():
    a = SiteSettings.load()
    b = SiteSettings.load()
    assert a.pk == 1
    assert b.pk == 1
    assert SiteSettings.objects.count() == 1


@pytest.mark.django_db
def test_singleton_save_always_targets_pk_1():
    """A second row can never be created, even by explicit pk assignment."""
    SiteSettings.load()
    other = SiteSettings(site_name="Sneaky")
    other.save()
    assert SiteSettings.objects.count() == 1
    assert SiteSettings.objects.get().site_name == "Sneaky"


@pytest.mark.django_db
def test_singleton_cannot_be_deleted():
    site = SiteSettings.load()
    with pytest.raises(ValidationError):
        site.delete()


@pytest.mark.django_db
def test_artist_profile_singleton_and_location():
    artist = ArtistProfile.load()
    artist.location_city = "Berlin"
    artist.location_country = "Germany"
    artist.save()
    assert artist.location == "Berlin, Germany"
    assert ArtistProfile.objects.count() == 1


@pytest.mark.django_db
def test_biography_split_into_paragraphs():
    artist = ArtistProfile.load()
    artist.biography = "First para.\n\nSecond para.\n\n\nThird para."
    artist.save()
    assert artist.biography_paragraphs == ["First para.", "Second para.", "Third para."]
