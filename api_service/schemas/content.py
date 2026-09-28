"""
Content schemas: tattoos, styles, artwork, gallery, products.

Every response body is an explicit model. NO ORM OBJECT IS EVER RETURNED RAW — that is
how internal fields (artist_notes, internal_notes, cost data) leak onto a public API.
Each schema declares exactly the fields the frontend needs.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from .common import ImageRef


# --- Tattoo styles ------------------------------------------------------------
class StyleCard(BaseModel):
    name: str
    slug: str
    description: str = ""
    piece_count: int = 0
    url: str


class StyleDetail(StyleCard):
    featured: bool = False


# --- Tattoos ------------------------------------------------------------------
class TattooCard(BaseModel):
    """List representation. Deliberately omits price and artist notes."""

    title: str
    slug: str
    url: str
    styles: list[str] = []
    placement: str = ""
    is_color: bool = False
    is_placeholder: bool = False
    primary_image: ImageRef | None = None


class TattooDetail(TattooCard):
    description: str = ""
    artist_notes: str = ""
    size_cm: str = ""
    duration_minutes: int | None = None
    price_from: str | None = None
    price_to: str | None = None
    currency: str = "EUR"
    session_date: date | None = None
    images: list[ImageRef] = []


# --- Artwork ------------------------------------------------------------------
class ArtworkCard(BaseModel):
    title: str
    slug: str
    url: str
    category: str = ""
    medium: str = ""
    year: int | None = None
    availability: str = "available"
    is_placeholder: bool = False
    primary_image: ImageRef | None = None


class ArtworkDetail(ArtworkCard):
    description: str = ""
    dimensions: str = ""
    edition_info: str = ""
    price: str | None = None
    currency: str = "EUR"
    images: list[ImageRef] = []


class CategoryCard(BaseModel):
    name: str
    slug: str
    description: str = ""
    work_count: int = 0
    url: str


# --- Gallery ------------------------------------------------------------------
class GalleryItem(BaseModel):
    caption: str = ""
    aspect: str = "portrait"
    span: int = 1
    is_featured: bool = False
    image: ImageRef | None = None


# --- Products -----------------------------------------------------------------
class ProductCard(BaseModel):
    name: str
    slug: str
    url: str
    product_type: str = ""
    availability: str = ""
    price: str = ""
    currency: str = "EUR"
    in_stock: bool = False
    is_placeholder: bool = False
    primary_image: ImageRef | None = None


class ProductDetail(ProductCard):
    description: str = ""
    stock: int | None = None
    is_limited: bool = False
    edition_size: int | None = None
    images: list[ImageRef] = []


# --- Site ---------------------------------------------------------------------
class SocialLinkOut(BaseModel):
    platform: str
    label: str
    url: str = ""


class SiteOut(BaseModel):
    site_name: str
    tagline: str = ""
    hero_kicker: str = ""
    hero_title: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    studio_address: str = ""
    booking_open: bool = True
    artist_name: str = ""
    artist_statement: str = ""
    artist_biography: str = ""
    artist_location: str = ""
    social_links: list[SocialLinkOut] = []


# --- Search -------------------------------------------------------------------
class SearchGroup(BaseModel):
    kind: str
    label: str
    count: int
    items: list[dict]


class SearchOut(BaseModel):
    query: str
    total: int
    groups: list[SearchGroup] = []
