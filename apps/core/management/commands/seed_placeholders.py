"""
Seed placeholder CMS content.

Everything created here is a PLACEHOLDER the artist replaces through the Django admin.
The purpose is that the site renders realistically from the first run instead of showing
empty states, so the design can be judged against real proportions.

Idempotent: safe to run repeatedly.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.artists.models import ArtistProfile, Statistic
from apps.artworks.models import ArtworkCategory
from apps.core.models import SiteSettings, SocialLink
from apps.shop.models import ProductCategory
from apps.tattoos.models import TattooStyle

STYLES = [
    ("Blackwork", "Dense black ink, high contrast, no colour."),
    ("Fine Line", "Delicate single-needle work with precise geometry."),
    ("Gothic", "Dark ornamental imagery with architectural detail."),
    ("Neo-Gothic", "Contemporary gothic with illustrative depth."),
    ("Illustrative", "Narrative, drawing-led tattoo work."),
    ("Traditional", "Bold lines, limited palette, classic motifs."),
    ("Neo-Traditional", "Traditional structure with expanded colour and depth."),
    ("Japanese", "Irezumi-influenced composition and motif."),
    ("Abstract", "Form, texture and gesture over representation."),
    ("Geometric", "Mathematical structure, symmetry and precision."),
    ("Ornamental", "Decorative filigree, lace and mandala work."),
    ("Custom", "Bespoke pieces designed from a blank page."),
]

ARTWORK_CATEGORIES = [
    "Paintings", "Drawings", "Illustration", "Digital Art", "Prints", "Experimental",
]

PRODUCT_CATEGORIES = ["Prints", "Originals", "Merchandise", "Digital"]


class Command(BaseCommand):
    help = "Create placeholder site content, fully editable from the Django admin."

    @transaction.atomic
    def handle(self, *args, **options):
        # --- Site settings ---------------------------------------------------
        site = SiteSettings.load()
        site.site_name = site.site_name or "TattoWeb"
        site.tagline = site.tagline or "Tattoo artist and visual artist"
        site.hero_kicker = site.hero_kicker or "TATTOO ARTIST / VISUAL ARTIST"
        site.hero_title = site.hero_title or "ART\nTHAT\nMOVES\nWITH YOU"
        site.default_meta_description = site.default_meta_description or (
            "Tattoo work, paintings, illustration and digital art. "
            "An artist's archive and studio booking."
        )
        site.contact_email = site.contact_email or "studio@example.com"
        site.studio_address = site.studio_address or "Studio address to be added"
        site.booking_open = True
        site.save()
        self.stdout.write(self.style.SUCCESS(f"site settings: {site.site_name}"))

        # --- Artist profile --------------------------------------------------
        artist = ArtistProfile.load()
        artist.display_name = artist.display_name or "STUDIO NAME"
        artist.monogram = artist.monogram or "SN"
        artist.role_line = artist.role_line or "TATTOO ARTIST / VISUAL ARTIST"
        artist.statement = artist.statement or "INK IS ONLY THE MEDIUM."
        artist.biography = artist.biography or (
            "This is placeholder biography text. Replace it from the Django admin under "
            "Artist profile.\n\n"
            "The layout is final: the first paragraph is used as the homepage excerpt, and "
            "every paragraph separated by a blank line becomes its own block here and on "
            "the About page.\n\n"
            "Location, experience and contact details are all editable without touching code."
        )
        artist.location_city = artist.location_city or "City"
        artist.location_country = artist.location_country or "Country"
        artist.years_experience = artist.years_experience or 10
        artist.email = artist.email or "studio@example.com"
        artist.is_booking_open = True
        artist.save()
        self.stdout.write(self.style.SUCCESS(f"artist: {artist.display_name}"))

        # --- Statistics ------------------------------------------------------
        for order, (value, label) in enumerate(
            [("10+", "YEARS"), ("1200+", "TATTOOS"), ("08", "SIGNATURE STYLES"), ("01", "VISION")]
        ):
            Statistic.objects.update_or_create(
                artist=artist, order=order, defaults={"value": value, "label": label}
            )
        self.stdout.write(self.style.SUCCESS("statistics: 4"))

        # --- Social links ----------------------------------------------------
        socials = [
            ("instagram", "@studio", "https://instagram.com/"),
            ("telegram", "@studio", "https://t.me/"),
            ("email", "studio@example.com", "mailto:studio@example.com"),
        ]
        for order, (platform, label, url) in enumerate(socials):
            SocialLink.objects.update_or_create(
                platform=platform,
                defaults={"label": label, "url": url, "order": order, "is_active": True},
            )
        self.stdout.write(self.style.SUCCESS("social links: 3"))

        # --- Taxonomy --------------------------------------------------------
        for order, (name, description) in enumerate(STYLES):
            TattooStyle.objects.update_or_create(
                name=name,
                defaults={
                    "description": description,
                    "order": order,
                    "is_featured": order < 4,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"tattoo styles: {len(STYLES)}"))

        for order, name in enumerate(ARTWORK_CATEGORIES):
            ArtworkCategory.objects.update_or_create(
                name=name, defaults={"order": order, "is_featured": order < 3}
            )
        self.stdout.write(self.style.SUCCESS(f"artwork categories: {len(ARTWORK_CATEGORIES)}"))

        for order, name in enumerate(PRODUCT_CATEGORIES):
            ProductCategory.objects.update_or_create(name=name, defaults={"order": order})
        self.stdout.write(self.style.SUCCESS(f"product categories: {len(PRODUCT_CATEGORIES)}"))

        # --- Availability: a realistic working week --------------------------
        from datetime import time

        from apps.booking.models import Availability

        week = [
            (1, time(10, 0), time(18, 0)),  # Tuesday
            (2, time(10, 0), time(18, 0)),  # Wednesday
            (3, time(10, 0), time(20, 0)),  # Thursday
            (4, time(10, 0), time(18, 0)),  # Friday
            (5, time(11, 0), time(16, 0)),  # Saturday
        ]
        for weekday, start, end in week:
            Availability.objects.update_or_create(
                weekday=weekday, start_time=start,
                defaults={"end_time": end, "slot_minutes": 60, "is_active": True},
            )
        self.stdout.write(self.style.SUCCESS(f"availability: {len(week)} working days"))

        self.stdout.write(self.style.SUCCESS("\nPlaceholder content seeded. All values are"))
        self.stdout.write(self.style.SUCCESS("editable at /admin/ — nothing is hard-coded."))
