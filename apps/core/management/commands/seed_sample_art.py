"""
Seed sample tattoo artwork and portfolio entries.

PURPOSE: give the development site realistic content so layout, aspect ratios, dither
thresholds and the resolve transition can be evaluated at real proportions.

THIS IS DEMONSTRATION CONTENT. Every record it creates carries ``is_placeholder=True``,
which drives a visible notice on the public site. None of it is presented as real work by
a real artist, and none of it reproduces any individual artist's portfolio.

Idempotent: re-running replaces the placeholder records rather than duplicating them.

Run:  manage.py seed_sample_art
      manage.py seed_sample_art --reset   (delete placeholders first)
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.artworks.models import Artwork, ArtworkCategory
from apps.core.ingest import ingest_image
from apps.core.models import MediaAsset
from apps.tattoos.models import Tattoo, TattooImage, TattooStyle

SAMPLE_DIR = Path("media") / "sample_art"

# Composition slug -> tattoo metadata. Thresholds are tuned per piece: dark-ground work
# (dark-winged-figure) needs a high threshold or it crushes; paper-ground engraving needs
# a low one to keep its thin lines.
SAMPLE_TATTOOS: tuple[dict, ...] = (
    {
        "slug": "gothic-angel-winged",
        "title": "Winged Figure, Study I",
        "styles": ["Gothic", "Blackwork"],
        "placement": "Back",
        "size_cm": "28 x 36 cm",
        "duration_minutes": 480,
        "description": (
            "A winged figure with an upright sword, framed by ornamental filigree and a "
            "sacred-geometry halo. Composed as a full back piece: the composition is "
            "axial, so it reads as a single image from a distance and resolves into "
            "linework on approach."
        ),
        "artist_notes": (
            "Built from a single continuous line hierarchy: the silhouette first, then the "
            "dense feather hatching, then the filigree. The halo is deliberately the only "
            "perfectly circular element — everything else is allowed to breathe away "
            "from geometric precision."
        ),
        "threshold": 112,
        "featured": True,
    },
    {
        "slug": "ornamental-sword",
        "title": "Ornamental Sword, Plate II",
        "styles": ["Gothic", "Ornamental"],
        "placement": "Forearm",
        "size_cm": "8 x 26 cm",
        "duration_minutes": 240,
        "description": (
            "A vertical ceremonial sword with a cruciform hilt, its blade wrapped in "
            "thorny vine ornament. Designed for the forearm so the blade follows the "
            "limb's line."
        ),
        "artist_notes": "Long, narrow compositions should follow the limb, never cross it.",
        "threshold": 120,
        "featured": True,
    },
    {
        "slug": "medieval-cross-panel",
        "title": "Medieval Cross, Panel",
        "styles": ["Gothic", "Geometric"],
        "placement": "Chest",
        "size_cm": "18 x 24 cm",
        "duration_minutes": 300,
        "description": (
            "An ornate medieval cross inside radiating concentric rings, with bramble "
            "ornament at the base. Symmetrical, intended for a centred chest placement."
        ),
        "artist_notes": "The rings are spaced so that they can be extended later without redrawing.",
        "threshold": 118,
        "featured": True,
    },
    {
        "slug": "dark-winged-figure",
        "title": "Dark Winged Figure",
        "styles": ["Blackwork", "Gothic"],
        "placement": "Upper arm",
        "size_cm": "20 x 26 cm",
        "duration_minutes": 360,
        "description": (
            "A silhouetted winged figure with chaotic thorn-like wings, worked as a dark "
            "mass with white linework resolving the interior. The tonal inverse of the "
            "paper-ground pieces."
        ),
        "artist_notes": (
            "This is the one piece in the set that is dark-ground rather than "
            "paper-ground, so it needs a higher halftone threshold — otherwise the dither "
            "collapses it into a solid block."
        ),
        "threshold": 152,
        "featured": True,
        "is_color": False,
    },
    {
        "slug": "gothic-cathedral",
        "title": "Cathedral Frontispiece",
        "styles": ["Gothic", "Ornamental"],
        "placement": "Thigh",
        "size_cm": "24 x 32 cm",
        "duration_minutes": 420,
        "description": (
            "A gothic frontispiece: pointed arch, rose window with tracery, and "
            "ornamental pinnacles. Architectural rather than figurative."
        ),
        "artist_notes": "Tracery detail is the whole point, so this one needs a large canvas.",
        "threshold": 116,
    },
    {
        "slug": "sacred-geometry-filigree",
        "title": "Sacred Geometry with Filigree",
        "styles": ["Geometric", "Ornamental"],
        "placement": "Back",
        "size_cm": "30 x 30 cm",
        "duration_minutes": 480,
        "description": (
            "Concentric circles and overlapping rosette forms inside a filigree frame. A "
            "pure geometry piece — no figure, no narrative."
        ),
        "artist_notes": "Every construction line is kept visible; the drafting is the drawing.",
        "threshold": 122,
        "featured": True,
    },
    {
        "slug": "occult-symbol-panel",
        "title": "Occult Symbol, Diagram",
        "styles": ["Gothic", "Abstract"],
        "placement": "Ribs",
        "size_cm": "16 x 24 cm",
        "duration_minutes": 300,
        "description": (
            "A diagrammatic piece: a seven-pointed star over a rosette, with sigils and "
            "alchemical marks in the margins. Presented as an extracted manuscript page."
        ),
        "artist_notes": "Reads as an artefact rather than an illustration — the frame is part of the design.",
        "threshold": 114,
    },
    {
        "slug": "large-backpiece",
        "title": "Full Back Piece, Composition",
        "styles": ["Blackwork", "Gothic", "Ornamental"],
        "placement": "Back",
        "size_cm": "40 x 50 cm",
        "duration_minutes": 960,
        "description": (
            "A complete back composition: a central cross form with two large swept "
            "wings, a rose-window rosette above, and dense filigree and vine framing the "
            "whole field."
        ),
        "artist_notes": (
            "Multiple sessions. The wings are placed first because everything else keys "
            "off their sweep."
        ),
        "threshold": 120,
    },
    {
        "slug": "thorned-rosace",
        "title": "Thorned Rosace",
        "styles": ["Ornamental", "Geometric"],
        "placement": "Shoulder",
        "size_cm": "22 x 22 cm",
        "duration_minutes": 360,
        "description": (
            "A sixteen-petal rosace ringed by thorny bramble. Circular, so it works on "
            "the shoulder cap where the body curves."
        ),
        "artist_notes": "Circular pieces should be placed on the body's own curves.",
        "threshold": 120,
    },
    {
        "slug": "arch-niche-figure",
        "title": "Figure in Arch Niche",
        "styles": ["Gothic", "Illustrative"],
        "placement": "Calf",
        "size_cm": "14 x 34 cm",
        "duration_minutes": 330,
        "description": (
            "A hooded robed figure standing inside a gothic arch niche with tracery. "
            "Tall and narrow, suited to the calf or forearm."
        ),
        "artist_notes": "The arch can be opened up into a window with background later.",
        "threshold": 116,
    },
    {
        "slug": "seraph-triptych",
        "title": "Seraph Triptych",
        "styles": ["Gothic", "Neo-Gothic"],
        "placement": "Back",
        "size_cm": "26 x 40 cm",
        "duration_minutes": 540,
        "description": (
            "Three panels read left to right: a winged angel, a cruciform spire, and a "
            "crowned winged seraph. Designed as a set but tattooable individually."
        ),
        "artist_notes": "Each panel is independently complete — the triptych is a curation, not a constraint.",
        "threshold": 118,
    },
    {
        "slug": "crown-and-chains",
        "title": "Crown and Chains",
        "styles": ["Ornamental", "Gothic"],
        "placement": "Sternum",
        "size_cm": "14 x 14 cm",
        "duration_minutes": 210,
        "description": (
            "A crown above hanging chains with beaded pendulums. Compact and symmetrical, "
            "sized for a sternum or ankle placement."
        ),
        "artist_notes": "One of the smaller pieces — good for a first session.",
        "threshold": 122,
    },
)


class Command(BaseCommand):
    help = "Seed demonstration tattoo artwork (clearly labelled as placeholder)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing placeholder records before seeding.",
        )
        parser.add_argument(
            "--no-images",
            action="store_true",
            help="Create records without generating image derivatives.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        sample_path = Path(SAMPLE_DIR)
        if not sample_path.exists():
            raise CommandError(
                f"Sample art directory not found: {SAMPLE_DIR}. "
                "Generate the artwork first (see docs/art-direction.md)."
            )

        if options["reset"]:
            removed = Tattoo.objects.filter(is_placeholder=True).delete()
            TattooImage.objects.filter(tattoo__is_placeholder=True).delete()
            MediaAsset.objects.filter(kind=MediaAsset.Kind.ORIGINAL).filter(
                tattoo_images__isnull=True, gallery_images__isnull=True,
            ).filter(alt_text__contains="demonstration artwork").delete()
            self.stdout.write(self.style.WARNING(f"reset: removed {removed}"))

        style_map = {s.name: s for s in TattooStyle.objects.all()}
        if not style_map:
            self.stdout.write(self.style.WARNING(
                "No TattooStyle rows found — run 'manage.py seed_placeholders' first."
            ))

        created = updated = skipped = 0

        for entry in SAMPLE_TATTOOS:
            image_path = sample_path / f"{entry['slug']}.png"
            if not image_path.exists():
                self.stdout.write(self.style.WARNING(f"  missing image: {image_path.name}"))
                skipped += 1
                continue

            tattoo, was_created = Tattoo.objects.update_or_create(
                slug=entry["slug"],
                defaults={
                    "title": entry["title"],
                    "description": entry["description"],
                    "artist_notes": entry.get("artist_notes", ""),
                    "placement": entry["placement"],
                    "size_cm": entry["size_cm"],
                    "duration_minutes": entry["duration_minutes"],
                    "is_featured": entry.get("featured", False),
                    "is_color": entry.get("is_color", False),
                    "is_placeholder": True,
                    "status": Tattoo.Status.PUBLISHED,
                    "published_at": timezone.now(),
                    "session_date": timezone.now().date(),
                },
            )
            tattoo.styles.set(
                [style_map[s] for s in entry["styles"] if s in style_map]
            )

            if not options["no_images"] and not tattoo.images.exists():
                content = image_path.read_bytes()
                # ingest_image now persists the threshold it generated with, so no
                # post-hoc fixup is needed.
                asset = ingest_image(
                    filename=f"sample_art/{image_path.name}",
                    content=content,
                    alt_text=f"{entry['title']} — demonstration artwork, gothic engraving style",
                    dither_threshold=entry["threshold"],
                )

                TattooImage.objects.create(
                    tattoo=tattoo,
                    asset=asset,
                    caption=entry["title"],
                    order=0,
                    is_primary=True,
                    variant=TattooImage.Variant.DETAIL,
                )

            if was_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  + {entry['title']}  (dither T={entry['threshold']})")
                )
            else:
                updated += 1

        # --- A few artworks, presented as gallery objects rather than tattoo records ---
        cat_map = {c.name: c for c in ArtworkCategory.objects.all()}
        artworks = [
            ("sacred-geometry-filigree", "Rosace Study, Geometric", "Digital Art", "Digital", 2026, 124),
            ("thorned-rosace", "Thorned Rosace, Ink Study", "Drawings", "Ink on paper", 2025, 120),
            ("occult-symbol-panel", "Occult Diagram, Page I", "Illustration", "Ink on paper", 2025, 114),
            ("seraph-triptych", "Seraph Triptych, Panel Set", "Prints", "Screenprint", 2026, 118),
        ]
        art_created = 0
        for slug, title, category, medium, year, threshold in artworks:
            image_path = sample_path / f"{slug}.png"
            if not image_path.exists() or category not in cat_map:
                continue
            artwork, was_created = Artwork.objects.update_or_create(
                slug=f"art-{slug}",
                defaults={
                    "title": title,
                    "category": cat_map[category],
                    "medium": medium,
                    "year": year,
                    "dimensions": "36 x 36 cm",
                    "availability": Artwork.Availability.AVAILABLE,
                    "is_featured": True,
                    "is_placeholder": True,
                    "status": Artwork.Status.PUBLISHED,
                    "published_at": timezone.now(),
                    "description": (
                        "Demonstration artwork showing the same engraving language applied "
                        "outside tattoo design."
                    ),
                },
            )

            # Artworks need their image too, otherwise the artwork pages render blank.
            # The threshold is applied here, per image, exactly as for tattoos.
            if not options["no_images"] and not artwork.images.exists():
                from apps.artworks.models import ArtworkImage

                asset = ingest_image(
                    filename=f"sample_art/{image_path.name}",
                    content=image_path.read_bytes(),
                    alt_text=f"{title} — demonstration artwork, gothic engraving style",
                    dither_threshold=threshold,
                )
                ArtworkImage.objects.create(
                    artwork=artwork, asset=asset, caption=title, order=0, is_primary=True
                )

            if was_created:
                art_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  + artwork: {title}  (dither T={threshold})")
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"sample art seeded: {created} tattoos created, {updated} updated, "
            f"{art_created} artworks, {skipped} skipped"
        ))
        self.stdout.write(self.style.WARNING(
            "All records carry is_placeholder=True and are labelled in the UI."
        ))
