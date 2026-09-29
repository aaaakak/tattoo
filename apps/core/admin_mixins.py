"""
Shared admin building blocks.

Registered as mixins and inlines so the five content apps (tattoos, artworks, gallery,
shop, core) present a consistent, learned-once interface. Without this, each app's admin
drifts and the artist has to relearn the CMS for every content type.
"""

from __future__ import annotations

from django import forms
from django.contrib import admin
from django.utils.html import format_html


class PublishedAdminMixin:
    """
    Common controls for the content models that share PublishableModel.

    Exposes status and featured as inline-editable list columns so the artist can publish
    and feature work from the changelist without opening each record.
    """

    list_editable = ("status", "is_featured")
    list_filter = ("status", "is_featured")
    date_hierarchy = "created_at"
    save_on_top = True
    actions = ("action_publish", "action_unpublish", "action_feature", "action_unfeature")

    @admin.action(description="Publish selected items")
    def action_publish(self, request, queryset):
        for obj in queryset:
            obj.publish()
        self.message_user(request, f"Published {queryset.count()} item(s).")

    @admin.action(description="Unpublish selected items")
    def action_unpublish(self, request, queryset):
        updated = queryset.update(status="draft")
        self.message_user(request, f"Moved {updated} item(s) back to draft.")

    @admin.action(description="Mark selected as featured")
    def action_feature(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f"Featured {updated} item(s).")

    @admin.action(description="Remove featured flag")
    def action_unfeature(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f"Unfeatured {updated} item(s).")


@admin.display(description="content", ordering="is_placeholder")
def placeholder_column(obj) -> str:
    """
    Visible marker for demonstration content, so generated sample work can never be
    mistaken for the artist's real work. Used as a `list_display` entry.

    CRITICAL — why this is a staticmethod:

    Django's changelist resolves each `list_display` entry via `lookup_field`, which
    fetches the attribute from the admin *instance*. A plain module-level function
    assigned as a class attribute becomes a bound method and is then called with
    (self, obj) — raising "takes 1 positional argument but 2 were given" and returning a
    500 on the changelist.

    A unit test that calls the function directly will NOT catch this: it passes while the
    real admin page crashes. The staticmethod prevents the binding entirely, and
    `tests/test_admin.py::test_content_changelists_load` covers the real HTTP path.

    Declared with @admin.display directly (not wrapped after the fact) so the description
    and ordering survive the staticmethod decoration.
    """
    if getattr(obj, "is_placeholder", False):
        return format_html(
            '<span style="color:#B45309;font-weight:600" title="Demonstration content">'
            "PLACEHOLDER</span>"
        )
    return "—"


# staticmethod must be applied outermost: admin.display returns an AdminDisplay object,
# and binding that as a class attribute would otherwise still inject `self`.
placeholder_column = staticmethod(placeholder_column)


def primary_image_of(obj):
    """Resolve a primary image asset for the changelist thumbnail."""
    getter = getattr(obj, "primary_image", None)
    return getter() if callable(getter) else getter


class SimpleImageUploadMixin(admin.ModelAdmin):
    """
    A plain image upload field on the parent content form.

    Inherits ModelAdmin so the `super()` calls below and any static analysis both resolve
    against the real API. Mix it in *before* the concrete admin class:

        class ArtworkAdmin(SimpleImageUploadMixin, PublishedAdminMixin, admin.ModelAdmin)

    Attribute resolution follows the MRO, and because every other base is also a ModelAdmin
    the diamond resolves cleanly.

    WHY THIS EXISTS
    ---------------
    Attaching an image used to take three manual steps on three different screens: create a
    MediaAsset by hand, then open the artwork/tattoo and add an inline row pointing at it
    through an autocomplete. `*Image.asset` is PROTECT, so nothing linked up on its own and
    the artist was doing work the machine should do.

    Now the artist drops a file into the ordinary form field and saves. The mixin calls the
    existing `ingest_image` pipeline, which validates the upload (extension allow-list, size
    cap, magic bytes, Pillow verify), deduplicates by content hash, and generates every
    derivative -- five WebP widths, the halftone dither plate and the LQIP. None of that
    changes; it is invoked, not reimplemented.

    The inline stays available for adding *extra* images after the fact, but it starts empty
    (`extra = 0`) so a fresh form shows one obvious upload box and nothing else.

    Subclasses must set:
        image_rel_name  -- the related_name on the image model, e.g. "images"
        image_model     -- the image model class, e.g. ArtworkImage
        image_fk_name   -- the FK field on that model pointing back, e.g. "artwork"
    """

    image_rel_name = ""     # related_name on the image model, e.g. "images"
    image_model = None      # the image model class, e.g. ArtworkImage
    image_fk_name = ""      # the FK field on that model pointing back, e.g. "artwork"
    image_upload_label = "Image"

    def get_form(self, request, obj=None, change=False, **kwargs):
        """
        Add the upload field to the form, keeping it invisible to the model-form machinery.

        Deliberately NOT a model field -- the file is not stored on Artwork/Tattoo. It is
        ingested into MediaAsset and linked through the image model, so the schema and every
        existing query are untouched.

        HOW THE NAME GETS INTO THE LAYOUT BUT NOT INTO `fields`
        ------------------------------------------------------
        Two things must both be true, and they pull in opposite directions:

        * the field must be in a fieldset, or ModelAdmin never renders it;
        * the field must NOT be in `fields`, or the model form raises
            "Unknown field(s) (upload_image) specified for Artwork".

        ModelAdmin computes `fields = flatten_fieldsets(fieldsets)` and passes it here, so
        the name is stripped from that argument before delegating, and the field is declared
        on the returned subclass. The fieldset entry supplies the layout; the subclass
        supplies the field.
        """
        field_name = "upload_image"
        if "fields" in kwargs and kwargs["fields"] is not None:
            kwargs["fields"] = [f for f in kwargs["fields"] if f != field_name]

        form = super().get_form(request, obj, change=change, **kwargs)

        clean_upload = self._clean_upload

        class WithImage(form):  # type: ignore[misc,valid-type]
            upload_image = forms.ImageField(
                label=self.image_upload_label,
                required=False,
                help_text=(
                    "Upload an image. It is validated and resized automatically — you do "
                    "not need to create anything else first."
                    if obj is None
                    else "Optional. Uploading here replaces the primary image."
                ),
            )

            def clean(self):
                """
                Validate the file here, before ModelAdmin's transaction has written anything.

                Doing it in save_model is too late -- see _clean_upload for why an exception
                raised after the object is saved rolls the whole request back, including the
                artwork.
                """
                cleaned = super().clean()
                cleaned["upload_image_bytes"] = clean_upload(cleaned.get("upload_image"))
                return cleaned

        return WithImage

    def _clean_upload(self, upload):
        """
        Validate the uploaded bytes during form validation, before anything is written.

        WHY THIS IS NOT JUST A NICETY
        -----------------------------
        `ingest_image` is decorated `@transaction.atomic` and raises `UploadValidationError`
        from inside it. The admin's changeform_view already wraps the whole request in a
        transaction, so an exception raised there marks that OUTER transaction for rollback.
        Catching it in save_model cannot undo that -- the entire request rolls back and the
        artwork is lost along with the bad image.

        Validating here instead means a bad file is refused while the form is being cleaned,
        before a single row is written.
        """
        from apps.core.ingest import UploadValidationError, validate_upload

        if not upload:
            return None
        try:
            upload.seek(0)
            content = upload.read()
            validate_upload(upload.name, content)
        except UploadValidationError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return content

    def get_fieldsets(self, request, obj=None):
        """
        Show the upload box first, above the text fields.

        Adding the name here is safe *because* get_form strips it from the flattened `fields`
        list before the model form is built. The two methods are a pair -- changing one
        without the other reintroduces the FieldError.
        """
        fieldsets = super().get_fieldsets(request, obj)
        if not fieldsets:
            return fieldsets
        head, options = fieldsets[0]
        fields = list(options.get("fields", ()))
        if "upload_image" not in fields:
            fields = ["upload_image", *fields]
        return [(head, {**options, "fields": tuple(fields)}), *fieldsets[1:]]

    def save_model(self, request, obj, form, change):
        """
        Save the object (it needs a pk), then attach the already-validated image.

        The file was validated in the form's clean(), so `ingest_image` is not expected to
        reject it. The try/except remains as a last line of defence for the decode step --
        bytes can pass the header checks and still fail to open -- but it no longer has to
        carry the "the artist lost their work" case, which is handled before any write.
        """
        import logging

        from django.contrib import messages

        super().save_model(request, obj, form, change)

        content = form.cleaned_data.get("upload_image_bytes")
        upload = form.cleaned_data.get("upload_image")
        if not upload or content is None:
            return

        from apps.core.ingest import ingest_image

        try:
            asset = ingest_image(
                filename=upload.name,
                content=content,
                alt_text=getattr(obj, "title", None) or str(obj),
            )
        except Exception as exc:
            # Should be unreachable for validated files; logged rather than swallowed so a
            # genuine pipeline fault is visible instead of silently producing a bare record.
            logging.getLogger(__name__).exception("ingest failed for %s", upload.name)
            self.message_user(
                request,
                f"{obj} was saved, but the image could not be processed: {exc}",
                level=messages.WARNING,
            )
            return

        manager = getattr(obj, self.image_rel_name)
        # First image becomes primary; a later upload replaces the primary and demotes the
        # previous one, so the artist never has to think about the is_primary flag.
        existing_primary = manager.filter(is_primary=True).first()
        if existing_primary is not None:
            existing_primary.is_primary = False
            existing_primary.save(update_fields=["is_primary"])
            last = manager.order_by("-order").first()
            order = (last.order if last else -1) + 1
        else:
            order = 0

        # Explicit FK name rather than deriving it from the class name: `Artwork -> artwork`
        # happens to hold today, but a rename would silently break the link and the failure
        # would only appear at save time.
        self.image_model.objects.create(
            **{self.image_fk_name: obj},
            asset=asset,
            order=order,
            is_primary=True,
        )
