"""
Booking forms.

The form is the artist's intake. Two things matter beyond field coverage:

  1. It must work with JavaScript disabled — a plain multipart POST, validated
     server-side. The reference-image widget is an enhancement, not a requirement.
  2. Uploads must be validated before they reach the filesystem. The form delegates to
     apps.core.ingest.validate_upload, so the same four checks (extension, size, magic
     bytes, Pillow verify) apply here as everywhere else.
"""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from apps.core.ingest import UploadValidationError, validate_upload
from apps.tattoos.models import TattooStyle

from .models import Booking

MAX_REFERENCE_IMAGES = 8

# A honeypot field. Bots fill every input they find; humans never see this one.
HONEYPOT_FIELD = "website"
HONEYPOT_ERROR = "Submission rejected."


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    """
    A file field accepting several images.

    Django's own multiple-file support requires a widget subclass, but validation still
    runs per file, which is what we want: one bad file is rejected with its own message
    rather than failing the whole submission opaquely.
    """

    widget = MultipleFileInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data]
        return single(data, initial) if data else []


class BookingForm(forms.ModelForm):
    """The tattoo request form."""

    style = forms.ModelChoiceField(
        queryset=TattooStyle.objects.order_by("order", "name"),
        required=False,
        empty_label="Select a style (optional)",
        help_text="Not sure? Leave it empty and describe the idea below.",
    )

    references = MultipleImageField(
        required=False,
        help_text=f"Up to {MAX_REFERENCE_IMAGES} images. JPEG, PNG or WebP, max 12 MB each.",
    )

    # `is_color` has a model default of "undecided". A ModelForm makes the field required
    # by default, which would force every client to answer a question they may legitimately
    # not have decided yet -- and would reject a valid request. Not required, defaulted.
    is_color = forms.ChoiceField(
        choices=Booking.ColorChoice.choices,
        required=False,
        initial=Booking.ColorChoice.UNDECIDED,
        label="Colour or black & grey",
    )

    # Honeypot: hidden in the template via CSS, never via type="hidden" (bots skip those).
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = Booking
        fields = (
            "style", "placement", "approx_size", "is_color", "description",
            "budget_min", "budget_max", "preferred_date", "preferred_time",
            "contact_consent",
        )
        labels = {
            "approx_size": "Approximate size",
            "is_color": "Colour or black & grey",
            "budget_min": "Budget from",
            "budget_max": "Budget to",
            "preferred_date": "Preferred date",
            "preferred_time": "Preferred time of day",
            "contact_consent": "I agree to be contacted about this request",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "preferred_date": forms.DateInput(attrs={"type": "date"}),
            "preferred_time": forms.Select(choices=[
                ("", "No preference"),
                ("morning", "Morning"),
                ("afternoon", "Afternoon"),
                ("evening", "Evening"),
            ]),
        }

    # --- Client identity fields: not on Booking (they live on Client) -----------------
    name = forms.CharField(max_length=160, label="Your name")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(max_length=40, required=False, label="Phone")
    instagram = forms.CharField(max_length=80, required=False, label="Instagram username")
    telegram = forms.CharField(max_length=80, required=False, label="Telegram username")

    def clean_website(self):
        """Honeypot: any value means a bot."""
        value = self.cleaned_data.get("website", "")
        if value:
            raise ValidationError(HONEYPOT_ERROR)
        return value

    def clean_contact_consent(self):
        consent = self.cleaned_data.get("contact_consent")
        if not consent:
            raise ValidationError("Please confirm you agree to be contacted.")
        return consent

    def clean_references(self):
        """
        Validate every uploaded image, before any file is written.

        Deliberately runs the same function the admin and the API use. A second
        implementation here would eventually diverge from the first, and the divergence
        would be a security hole.
        """
        files = self.cleaned_data.get("references") or []
        if len(files) > MAX_REFERENCE_IMAGES:
            raise ValidationError(
                f"Please upload at most {MAX_REFERENCE_IMAGES} images "
                f"(you selected {len(files)})."
            )
        for f in files:
            content = f.read()
            f.seek(0)
            try:
                validate_upload(f.name, content)
            except UploadValidationError as exc:
                raise ValidationError(f"{f.name}: {exc.messages[0]}") from exc
        return files

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("budget_min"), cleaned.get("budget_max")
        if low is not None and high is not None and high < low:
            self.add_error("budget_max", "The upper budget must be at least the lower one.")
        return cleaned


class AppointmentForm(forms.ModelForm):
    """Artist-side scheduling. Overlap correctness is left to the database constraint."""

    class Meta:
        from .models import Appointment

        model = Appointment
        fields = ("client", "start_at", "end_at", "status", "internal_notes")
        widgets = {
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_at"), cleaned.get("end_at")
        if start and end and end <= start:
            self.add_error("end_at", "The end time must be after the start time.")
        return cleaned
