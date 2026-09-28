"""
SQLAlchemy read-mirrors of the Django-owned schema.

IMPORTANT ARCHITECTURAL RULE (docs/fastapi.md section 2):
Django owns all DDL. These models are READ MIRRORS — they must never issue migrations and
never create or alter a table. `tests/test_schema_contract.py` asserts every column here
exists in the live Postgres schema, so a Django field addition that is not mirrored fails
CI with the exact column name rather than surfacing as a runtime error.

Only the columns the API actually serves are declared. Mirroring all ~40 columns across
every table would create maintenance burden for no benefit.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TattooStyle(Base):
    __tablename__ = "tattoos_tattoostyle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(90))
    description: Mapped[str] = mapped_column(Text, default="")
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)


# The many-to-many association table Django created for Tattoo.styles.
# Declared as a read-mirror Table because SQLAlchemy resolves `secondary=` by table NAME:
# without this, mapper initialisation fails with
# "expression 'tattoos_tattoo_styles' failed to locate a name".
tattoo_styles = Table(
    "tattoos_tattoo_styles",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("tattoo_id", ForeignKey("tattoos_tattoo.id")),
    Column("tattoostyle_id", ForeignKey("tattoos_tattoostyle.id")),
)


class Tattoo(Base):
    __tablename__ = "tattoos_tattoo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    artist_notes: Mapped[str] = mapped_column(Text, default="")
    placement: Mapped[str] = mapped_column(String(80), default="")
    size_cm: Mapped[str] = mapped_column(String(40), default="")
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_from: Mapped[float | None] = mapped_column(Numeric(9, 2), nullable=True)
    price_to: Mapped[float | None] = mapped_column(Numeric(9, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    is_color: Mapped[bool] = mapped_column(Boolean, default=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_placeholder: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    styles: Mapped[list[TattooStyle]] = relationship(
        secondary=tattoo_styles, lazy="selectin"
    )
    images: Mapped[list[TattooImage]] = relationship(
        back_populates="tattoo", lazy="selectin", order_by="TattooImage.order"
    )


class TattooImage(Base):
    __tablename__ = "tattoos_tattooimage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tattoo_id: Mapped[int] = mapped_column(ForeignKey("tattoos_tattoo.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("core_mediaasset.id"))
    caption: Mapped[str] = mapped_column(String(200), default="")
    variant: Mapped[str] = mapped_column(String(20), default="detail")
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    tattoo: Mapped[Tattoo] = relationship(back_populates="images")
    asset: Mapped[MediaAsset] = relationship(lazy="selectin")


class MediaAsset(Base):
    __tablename__ = "core_mediaasset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20), default="original")
    variant_key: Mapped[str] = mapped_column(String(40), default="")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    alt_text: Mapped[str] = mapped_column(String(200), default="")
    dither_threshold: Mapped[int] = mapped_column(Integer, default=118)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ArtworkCategory(Base):
    __tablename__ = "artworks_artworkcategory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(90))
    description: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)


class Artwork(Base):
    __tablename__ = "artworks_artwork"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[int] = mapped_column(ForeignKey("artworks_artworkcategory.id"))
    medium: Mapped[str] = mapped_column(String(120), default="")
    dimensions: Mapped[str] = mapped_column(String(80), default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    availability: Mapped[str] = mapped_column(String(20), default="available")
    price: Mapped[float | None] = mapped_column(Numeric(9, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    edition_info: Mapped[str] = mapped_column(String(120), default="")
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_placeholder: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    category: Mapped[ArtworkCategory] = relationship(lazy="selectin")
    images: Mapped[list[ArtworkImage]] = relationship(
        back_populates="artwork", lazy="selectin", order_by="ArtworkImage.order"
    )


class ArtworkImage(Base):
    __tablename__ = "artworks_artworkimage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artwork_id: Mapped[int] = mapped_column(ForeignKey("artworks_artwork.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("core_mediaasset.id"))
    caption: Mapped[str] = mapped_column(String(200), default="")
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    artwork: Mapped[Artwork] = relationship(back_populates="images")
    asset: Mapped[MediaAsset] = relationship(lazy="selectin")


class GalleryImage(Base):
    __tablename__ = "gallery_galleryimage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("core_mediaasset.id"))
    caption: Mapped[str] = mapped_column(String(200), default="")
    aspect: Mapped[str] = mapped_column(String(10), default="portrait")
    span: Mapped[int] = mapped_column(Integer, default=1)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    asset: Mapped[MediaAsset] = relationship(lazy="selectin")


class Product(Base):
    __tablename__ = "shop_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[int] = mapped_column(Integer)
    product_type: Mapped[str] = mapped_column(String(20), default="print")
    price: Mapped[float] = mapped_column(Numeric(9, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_limited: Mapped[bool] = mapped_column(Boolean, default=False)
    edition_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    availability: Mapped[str] = mapped_column(String(20), default="in_stock")
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    images: Mapped[list[ProductImage]] = relationship(lazy="selectin", order_by="ProductImage.order")


class ProductImage(Base):
    __tablename__ = "shop_productimage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("shop_product.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("core_mediaasset.id"))
    caption: Mapped[str] = mapped_column(String(200), default="")
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    asset: Mapped[MediaAsset] = relationship(lazy="selectin")


class SiteSettings(Base):
    __tablename__ = "core_sitesettings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_name: Mapped[str] = mapped_column(String(120), default="TattoWeb")
    tagline: Mapped[str] = mapped_column(String(200), default="")
    hero_kicker: Mapped[str] = mapped_column(String(120), default="")
    hero_title: Mapped[str] = mapped_column(String(200), default="")
    contact_email: Mapped[str] = mapped_column(String(254), default="")
    contact_phone: Mapped[str] = mapped_column(String(40), default="")
    studio_address: Mapped[str] = mapped_column(Text, default="")
    booking_open: Mapped[bool] = mapped_column(Boolean, default=True)


class ArtistProfile(Base):
    __tablename__ = "artists_artistprofile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    monogram: Mapped[str] = mapped_column(String(6), default="")
    role_line: Mapped[str] = mapped_column(String(160), default="")
    statement: Mapped[str] = mapped_column(Text, default="")
    biography: Mapped[str] = mapped_column(Text, default="")
    location_city: Mapped[str] = mapped_column(String(80), default="")
    location_country: Mapped[str] = mapped_column(String(80), default="")
    years_experience: Mapped[int] = mapped_column(Integer, default=0)
    email: Mapped[str] = mapped_column(String(254), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    is_booking_open: Mapped[bool] = mapped_column(Boolean, default=True)
