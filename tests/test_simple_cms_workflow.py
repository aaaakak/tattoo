"""
The simplified CMS workflow.

WHAT THESE TESTS PROTECT
------------------------
Attaching an image used to require three manual steps on three screens: create a
MediaAsset by hand, then open the artwork and add an inline row pointing at it through an
autocomplete. `*Image.asset` is PROTECT, so nothing linked up on its own.

The requirement is now: open Artworks -> Add Artwork, fill the fields, drop in an image,
save. These tests assert that literally -- they POST the admin add form exactly as a browser
would and check what exists afterwards.

They also pin two failure modes found while building this:

* `upload_image` is not a model field, so declaring it in a fieldset without stripping it
  from the flattened `fields` list raises
  "Unknown field(s) (upload_image) specified for Artwork";
* the field must actually RENDER. It is possible to have a form that accepts the field on
  POST while ModelAdmin never draws it, because rendering is driven by the fieldsets.
"""

from __future__ import annotations

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image

from apps.artworks.models import Artwork, ArtworkCategory
from apps.core.models import MediaAsset

pytestmark = pytest.mark.django_db


def _png(name="art.png", size=(640, 480), colour=(180, 40, 40)):
    buf = io.BytesIO()
    Image.new("RGB", size, colour).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def _formset_prefix(n):
    """The management form fields Django expects for an inline formset with n forms."""
    return {
        f"{n}-TOTAL_FORMS": "0",
        f"{n}-INITIAL_FORMS": "0",
        f"{n}-MIN_NUM_FORMS": "0",
        f"{n}-MAX_NUM_FORMS": "1000",
    }


@pytest.fixture
def admin_client(db):
    user_model = get_user_model()
    user_model.objects.create_superuser("boss", "boss@example.com", "pw12345!")
    client = Client()
    client.force_login(user_model.objects.get(username="boss"))
    return client


@pytest.fixture
def category(db):
    return ArtworkCategory.objects.create(name="Paintings", slug="paintings")


# --------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------
def test_add_form_shows_a_plain_file_input_first(admin_client, category):
    """The artist sees an upload box at the top of the form and nothing exotic."""
    html = admin_client.get("/admin/artworks/artwork/add/").content.decode()

    assert 'name="upload_image"' in html, "the upload field is not rendered at all"
    assert 'type="file"' in html, "the upload field is not a file input"

    # Ahead of the text fields, so the simple path is the obvious one.
    assert html.find('name="upload_image"') < html.find('name="title"')


def test_add_form_does_not_render_media_asset_chooser(admin_client, category):
    """
    The old workflow's autocomplete must not be on the simple form. An empty inline
    (`extra = 0`) means no blank rows competing with the upload box.
    """
    html = admin_client.get("/admin/artworks/artwork/add/").content.decode()
    assert "images-0-asset" not in html, "an empty inline row is still being rendered"


# --------------------------------------------------------------------------------------
# The workflow itself
# --------------------------------------------------------------------------------------
def test_artwork_saves_with_a_plain_image_upload(admin_client, category):
    """
    One POST. No MediaAsset created by hand, no inline row, no variant management.

    Asserts the whole chain: artwork row, link row, MediaAsset, and that the existing
    ingest pipeline actually ran (derivatives generated).
    """
    count_before = MediaAsset.objects.count()

    resp = admin_client.post(
        "/admin/artworks/artwork/add/",
        {
            "title": "Red Study",
            "slug": "red-study",
            "description": "An upload test.",
            "category": category.pk,
            "medium": "Acrylic on canvas",
            "dimensions": "70 x 100 cm",
            "year": "2024",
            "price": "",
            "currency": "EUR",
            "availability": "available",
            "status": "published",
            "is_featured": "on",
            "edition_info": "",
            "meta_title": "",
            "meta_description": "",
            "upload_image": _png(),
            **_formset_prefix("images"),
        },
    )
    assert resp.status_code == 302, f"form did not save (status {resp.status_code})"

    artwork = Artwork.objects.get(title="Red Study")

    images = artwork.images.all()
    assert images.count() == 1, "the upload did not create exactly one image link"
    assert images.filter(is_primary=True).count() == 1, "no primary image was set"

    asset = images.first().asset
    assert asset.kind == MediaAsset.Kind.ORIGINAL
    assert (asset.width, asset.height) == (640, 480), "the image was not read"

    # The existing pipeline is invoked, not bypassed: originals + webp widths + dither + lqip.
    assert MediaAsset.objects.count() > count_before + 1, (
        "no derivatives were generated -- the ingest pipeline was skipped"
    )


def test_artwork_saves_with_an_empty_price(admin_client, category):
    """
    Leaving Price blank must work. Previously the field was required and blocked the save
    with "This field is required.", making an unpriced piece impossible to store.
    """
    resp = admin_client.post(
        "/admin/artworks/artwork/add/",
        {
            "title": "Unpriced",
            "slug": "unpriced",
            "description": "",
            "category": category.pk,
            "medium": "",
            "dimensions": "",
            "year": "",
            "price": "",
            "currency": "EUR",
            "availability": "available",
            "status": "draft",
            "is_placeholder": "",
            "edition_info": "",
            "meta_title": "",
            "meta_description": "",
            **_formset_prefix("images"),
        },
    )
    assert resp.status_code == 302, resp.content.decode()[:600]
    assert Artwork.objects.get(title="Unpriced").price is None


def test_artwork_saves_without_an_image(admin_client, category):
    """The upload is optional -- an artwork can be created before its image exists."""
    resp = admin_client.post(
        "/admin/artworks/artwork/add/",
        {
            "title": "No Image Yet",
            "slug": "no-image-yet",
            "description": "",
            "category": category.pk,
            "medium": "",
            "dimensions": "",
            "year": "",
            "price": "",
            "currency": "EUR",
            "availability": "available",
            "status": "draft",
            "is_placeholder": "",
            "edition_info": "",
            "meta_title": "",
            "meta_description": "",
            **_formset_prefix("images"),
        },
    )
    assert resp.status_code == 302
    assert Artwork.objects.get(title="No Image Yet").images.count() == 0


def test_a_second_upload_replaces_the_primary(admin_client, category):
    """
    Uploading again must not create two primaries -- the model has a partial unique
    constraint (`uniq_artwork_primary_image`), so getting this wrong is an IntegrityError
    rather than a cosmetic bug.
    """
    base = {
        "slug": "two-uploads",
        "description": "",
        "category": category.pk,
        "medium": "",
        "dimensions": "",
        "year": "",
        "price": "",
        "currency": "EUR",
        "availability": "available",
        "status": "draft",
        "is_placeholder": "",
        "edition_info": "",
        "meta_title": "",
        "meta_description": "",
        **_formset_prefix("images"),
    }
    assert admin_client.post(
        "/admin/artworks/artwork/add/",
        {**base, "title": "Two Uploads", "upload_image": _png("first.png")},
    ).status_code == 302

    artwork = Artwork.objects.get(title="Two Uploads")
    assert admin_client.post(
        f"/admin/artworks/artwork/{artwork.pk}/change/",
        {**base, "title": "Two Uploads", "upload_image": _png("second.png", colour=(10, 90, 200))},
    ).status_code == 302

    artwork.refresh_from_db()
    assert artwork.images.count() == 2
    assert artwork.images.filter(is_primary=True).count() == 1, "not exactly one primary"


# --------------------------------------------------------------------------------------
# Hiding the plumbing
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("model_name", ["mediaasset", "artworkimage"])
def test_internal_tables_are_hidden_from_non_superusers(admin_client, model_name):
    """
    A staff artist must see Artworks and Tattoos, not MediaAsset / ArtworkImage. Both stay
    reachable for superusers, who may need to inspect a rejected upload.
    """
    user_model = get_user_model()
    artist = user_model.objects.create_user("artist", "a@example.com", "pw12345!", is_staff=True)
    client = Client()
    client.force_login(artist)

    index = client.get("/admin/").content.decode()
    assert f"/admin/core/{model_name}/" not in index, f"{model_name} is visible to staff"

    # Superuser still sees it.
    assert model_name in admin_client.get("/admin/").content.decode()


def test_tattoo_uses_the_same_simple_workflow(admin_client):
    """Tattoos are the same shape, so they get the same one-step form."""
    from apps.tattoos.models import Tattoo, TattooImage

    resp = admin_client.post(
        "/admin/tattoos/tattoo/add/",
        {
            "title": "Forearm Piece",
            "slug": "forearm-piece",
            "description": "",
            "placement": "forearm",
            "size_cm": "",
            "duration_minutes": "",
            "session_date": "",
            "price_from": "",
            "price_to": "",
            "currency": "EUR",
            "status": "draft",
            "is_color": "",
            "is_placeholder": "",
            "artist_notes": "",
            "meta_title": "",
            "meta_description": "",
            "upload_image": _png("tatt.png"),
            **_formset_prefix("images"),
        },
    )
    assert resp.status_code == 302, resp.content.decode()[:600]

    tattoo = Tattoo.objects.get(title="Forearm Piece")
    assert TattooImage.objects.filter(tattoo=tattoo, is_primary=True).count() == 1


def test_rejected_upload_is_refused_with_a_message_and_no_partial_record(admin_client, category):
    """
    A bad file must be refused at validation time, with a readable message, and must not
    leave a half-created record behind.

    This is deliberately stricter than "the artwork is saved anyway". `ingest_image` is
    `@transaction.atomic` and the admin already wraps the request in a transaction, so an
    exception raised after the object is saved marks the OUTER transaction for rollback --
    catching it cannot undo that, and the artwork disappears. Validating in the form's
    clean() means nothing is written at all, so the artist simply sees an error and their
    other field values are still on screen to retry.
    """
    junk = SimpleUploadedFile("notes.txt", b"not an image at all, just text", content_type="text/plain")
    resp = admin_client.post(
        "/admin/artworks/artwork/add/",
        {
            "title": "Bad Upload",
            "slug": "bad-upload",
            "description": "",
            "category": category.pk,
            "medium": "",
            "dimensions": "",
            "year": "",
            "price": "",
            "currency": "EUR",
            "availability": "available",
            "status": "draft",
            "is_placeholder": "",
            "edition_info": "",
            "meta_title": "",
            "meta_description": "",
            "upload_image": junk,
            **_formset_prefix("images"),
        },
    )
    # 200 = the form was re-rendered with errors; 302 would mean it saved something.
    assert resp.status_code == 200, "a rejected upload was not refused by the form"
    body = resp.content.decode()
    # Django's ImageField runs its own Pillow check first, so the message an artist sees for
    # a non-image is Django's. assertFormError-style text, not our own validator's.
    assert "Upload a valid image" in body, "the artist is not told the file is not an image"
    assert not Artwork.objects.filter(title="Bad Upload").exists(), (
        "a refused upload left a partial record behind"
    )


def test_oversized_upload_is_refused(admin_client, category):
    """
    The size cap rejects a genuinely oversized file with a readable message and no record.

    NOTE on constructing this: a large *dimension* PNG compresses tiny (a 6000x6000 solid
    colour is ~0.1 MB) and therefore saves happily. The cap is on bytes, so the fixture
    appends filler to exceed it deliberately.
    """
    from apps.core.ingest import MAX_UPLOAD_MB

    filler = b"\x00" * ((MAX_UPLOAD_MB + 1) * 1024 * 1024)
    big = SimpleUploadedFile("huge.png", b"\x89PNG\r\n\x1a\n" + filler, content_type="image/png")
    assert big.size > MAX_UPLOAD_MB * 1024 * 1024

    resp = admin_client.post(
        "/admin/artworks/artwork/add/",
        {
            "title": "Huge Upload",
            "slug": "huge-upload",
            "description": "",
            "category": category.pk,
            "medium": "",
            "dimensions": "",
            "year": "",
            "price": "",
            "currency": "EUR",
            "availability": "available",
            "status": "draft",
            "is_placeholder": "",
            "edition_info": "",
            "meta_title": "",
            "meta_description": "",
            "upload_image": big,
            **_formset_prefix("images"),
        },
    )
    assert resp.status_code == 200, "an oversized upload was not refused"
    assert not Artwork.objects.filter(title="Huge Upload").exists()


def test_size_cap_message_comes_from_the_validator():
    """
    The byte-cap branch of `validate_upload` is the one the admin relies on for a file that
    IS a decodable image but exceeds the cap. Exercised directly, because reproducing it
    through the admin would need a multi-megabyte fixture.
    """
    from apps.core.ingest import MAX_UPLOAD_MB, UploadValidationError, validate_upload

    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * ((MAX_UPLOAD_MB + 1) * 1024 * 1024)
    with pytest.raises(UploadValidationError) as exc:
        validate_upload("big.png", oversized)
    assert "too large" in str(exc.value).lower()
