"""
Content routers: tattoos, styles, artwork, gallery, products.

Read-only, cacheable. These are the hot paths the frontend hits on every navigation, so
they use only the columns the response needs and set public cache headers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api_service.db.models import (
    Artwork,
    ArtworkCategory,
    GalleryImage,
    MediaAsset,
    Product,
    Tattoo,
    TattooStyle,
)
from api_service.db.session import get_db
from api_service.deps import Pagination, pagination
from api_service.schemas.common import ImageRef, Page
from api_service.schemas.content import (
    ArtworkCard,
    ArtworkDetail,
    CategoryCard,
    GalleryItem,
    ProductCard,
    ProductDetail,
    StyleCard,
    StyleDetail,
    TattooCard,
    TattooDetail,
)

router = APIRouter()

# Cache policy: content changes are artist-driven and rare, so a short public cache makes
# the API effectively free under load without risking visible staleness.
CACHE = "public, max-age=300, stale-while-revalidate=600"


def _asset_ref(asset: MediaAsset | None, dither_url: str | None = None) -> ImageRef | None:
    if asset is None:
        return None
    return ImageRef(
        url=f"/media/{asset.file}",
        dither_url=dither_url,
        width=asset.width,
        height=asset.height,
        alt=asset.alt_text or "",
    )


def _dither_for(db: Session, asset: MediaAsset) -> str | None:
    """Resolve the pre-generated dither sibling for an asset."""
    if not asset.sha256:
        return None
    sibling = db.execute(
        select(MediaAsset).where(
            MediaAsset.sha256 == asset.sha256, MediaAsset.kind == "dither"
        )
    ).scalar_one_or_none()
    return f"/media/{sibling.file}" if sibling else None


def _primary_image(db: Session, images, asset_getter) -> ImageRef | None:
    if not images:
        return None
    primary = next((i for i in images if i.is_primary), images[0])
    asset = asset_getter(primary)
    if asset is None:
        return None
    return _asset_ref(asset, _dither_for(db, asset))


# --------------------------------------------------------------------------------------
# Tattoo styles
# --------------------------------------------------------------------------------------
@router.get("/styles", response_model=list[StyleCard], summary="List tattoo styles")
def list_styles(db: Session = Depends(get_db)):
    # Count published pieces per style through the association table. Written against the
    # Table object directly rather than a relationship attribute path, which is an
    # internal API and breaks between SQLAlchemy releases.
    from api_service.db.models import tattoo_styles

    counts = dict(
        db.execute(
            select(tattoo_styles.c.tattoostyle_id, func.count())
            .select_from(
                tattoo_styles.join(Tattoo, Tattoo.id == tattoo_styles.c.tattoo_id)
            )
            .where(Tattoo.status == "published")
            .group_by(tattoo_styles.c.tattoostyle_id)
        ).all()
    )
    rows = db.execute(select(TattooStyle).order_by(TattooStyle.order, TattooStyle.name)).scalars()
    return [
        StyleCard(
            name=s.name,
            slug=s.slug,
            description=s.description or "",
            piece_count=counts.get(s.id, 0),
            url=f"/styles/{s.slug}/",
        )
        for s in rows
    ]


@router.get("/styles/{slug}", response_model=StyleDetail, summary="Style detail")
def get_style(slug: str, db: Session = Depends(get_db)):
    style = db.execute(select(TattooStyle).where(TattooStyle.slug == slug)).scalar_one_or_none()
    if style is None:
        raise HTTPException(status_code=404, detail="Style not found")
    count = db.execute(
        select(func.count()).select_from(Tattoo).where(Tattoo.status == "published")
    ).scalar_one()
    return StyleDetail(
        name=style.name,
        slug=style.slug,
        description=style.description or "",
        piece_count=count,
        featured=style.is_featured,
        url=f"/styles/{style.slug}/",
    )


# --------------------------------------------------------------------------------------
# Tattoos
# --------------------------------------------------------------------------------------
@router.get("/tattoos", response_model=Page[TattooCard], summary="List tattoos")
def list_tattoos(
    request: Request,
    db: Session = Depends(get_db),
    page: Pagination = Depends(pagination),
    style: str | None = Query(None, description="Filter by style slug"),
    placement: str | None = Query(None),
    is_color: bool | None = Query(None),
    featured: bool | None = Query(None),
    q: str | None = Query(None, description="Free-text search"),
):
    stmt = select(Tattoo).where(Tattoo.status == "published")
    if style:
        stmt = stmt.join(Tattoo.styles).where(TattooStyle.slug == style)
    if placement:
        stmt = stmt.where(func.lower(Tattoo.placement) == placement.lower())
    if is_color is not None:
        stmt = stmt.where(Tattoo.is_color == is_color)
    if featured is not None:
        stmt = stmt.where(Tattoo.is_featured == featured)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Tattoo.title.ilike(like) | Tattoo.description.ilike(like))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Tattoo.published_at.desc().nullslast())
        .offset(page.offset)
        .limit(page.page_size)
    ).scalars().unique().all()

    items = [
        TattooCard(
            title=t.title,
            slug=t.slug,
            url=f"/tattoos/{t.slug}/",
            styles=[s.name for s in t.styles],
            placement=t.placement or "",
            is_color=t.is_color,
            is_placeholder=t.is_placeholder,
            primary_image=_primary_image(db, t.images, lambda i: i.asset),
        )
        for t in rows
    ]
    return page.envelope(items, total, request)


@router.get("/tattoos/{slug}", response_model=TattooDetail, summary="Tattoo detail")
def get_tattoo(slug: str, db: Session = Depends(get_db)):
    tattoo = db.execute(select(Tattoo).where(Tattoo.slug == slug)).scalar_one_or_none()
    if tattoo is None or tattoo.status != "published":
        raise HTTPException(status_code=404, detail="Tattoo not found")

    images = [
        ImageRef(
            url=f"/media/{i.asset.file}",
            dither_url=_dither_for(db, i.asset),
            width=i.asset.width,
            height=i.asset.height,
            alt=i.caption or i.asset.alt_text or "",
        )
        for i in tattoo.images
        if i.asset
    ]
    return TattooDetail(
        title=tattoo.title,
        slug=tattoo.slug,
        url=f"/tattoos/{tattoo.slug}/",
        styles=[s.name for s in tattoo.styles],
        placement=tattoo.placement or "",
        is_color=tattoo.is_color,
        is_placeholder=tattoo.is_placeholder,
        primary_image=images[0] if images else None,
        description=tattoo.description or "",
        artist_notes=tattoo.artist_notes or "",
        size_cm=tattoo.size_cm or "",
        duration_minutes=tattoo.duration_minutes,
        price_from=str(tattoo.price_from) if tattoo.price_from is not None else None,
        price_to=str(tattoo.price_to) if tattoo.price_to is not None else None,
        currency=tattoo.currency,
        session_date=tattoo.session_date,
        images=images,
    )


# --------------------------------------------------------------------------------------
# Artwork
# --------------------------------------------------------------------------------------
@router.get("/categories", response_model=list[CategoryCard], summary="List artwork categories")
def list_categories(db: Session = Depends(get_db)):
    rows = db.execute(
        select(ArtworkCategory).order_by(ArtworkCategory.order, ArtworkCategory.name)
    ).scalars()
    return [
        CategoryCard(
            name=c.name,
            slug=c.slug,
            description=c.description or "",
            url=f"/artworks/category/{c.slug}/",
        )
        for c in rows
    ]


@router.get("/artworks", response_model=Page[ArtworkCard], summary="List artwork")
def list_artworks(
    request: Request,
    db: Session = Depends(get_db),
    page: Pagination = Depends(pagination),
    category: str | None = None,
    year: int | None = None,
    availability: str | None = None,
    featured: bool | None = None,
    q: str | None = None,
):
    stmt = select(Artwork).where(Artwork.status == "published")
    if category:
        stmt = stmt.join(Artwork.category).where(ArtworkCategory.slug == category)
    if year:
        stmt = stmt.where(Artwork.year == year)
    if availability:
        stmt = stmt.where(Artwork.availability == availability)
    if featured is not None:
        stmt = stmt.where(Artwork.is_featured == featured)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Artwork.title.ilike(like) | Artwork.description.ilike(like))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Artwork.year.desc().nullslast()).offset(page.offset).limit(page.page_size)
    ).scalars().unique().all()

    items = [
        ArtworkCard(
            title=a.title,
            slug=a.slug,
            url=f"/artworks/{a.slug}/",
            category=a.category.name if a.category else "",
            medium=a.medium or "",
            year=a.year,
            availability=a.availability,
            is_placeholder=a.is_placeholder,
            primary_image=_primary_image(db, a.images, lambda i: i.asset),
        )
        for a in rows
    ]
    return page.envelope(items, total, request)


@router.get("/artworks/{slug}", response_model=ArtworkDetail, summary="Artwork detail")
def get_artwork(slug: str, db: Session = Depends(get_db)):
    art = db.execute(select(Artwork).where(Artwork.slug == slug)).scalar_one_or_none()
    if art is None or art.status != "published":
        raise HTTPException(status_code=404, detail="Artwork not found")

    images = [
        ImageRef(
            url=f"/media/{i.asset.file}",
            dither_url=_dither_for(db, i.asset),
            width=i.asset.width,
            height=i.asset.height,
            alt=i.caption or i.asset.alt_text or "",
        )
        for i in art.images
        if i.asset
    ]
    return ArtworkDetail(
        title=art.title,
        slug=art.slug,
        url=f"/artworks/{art.slug}/",
        category=art.category.name if art.category else "",
        medium=art.medium or "",
        year=art.year,
        availability=art.availability,
        is_placeholder=art.is_placeholder,
        primary_image=images[0] if images else None,
        description=art.description or "",
        dimensions=art.dimensions or "",
        edition_info=art.edition_info or "",
        price=str(art.price) if art.price is not None else None,
        currency=art.currency,
        images=images,
    )


# --------------------------------------------------------------------------------------
# Gallery
# --------------------------------------------------------------------------------------
@router.get("/gallery", response_model=list[GalleryItem], summary="Gallery images")
def list_gallery(db: Session = Depends(get_db), featured: bool | None = None, limit: int = Query(60, le=200)):
    stmt = select(GalleryImage).order_by(GalleryImage.order, GalleryImage.id).limit(limit)
    if featured is not None:
        stmt = stmt.where(GalleryImage.is_featured == featured)
    rows = db.execute(stmt).scalars().all()
    return [
        GalleryItem(
            caption=g.caption or "",
            aspect=g.aspect,
            span=g.span,
            is_featured=g.is_featured,
            image=_asset_ref(g.asset, _dither_for(db, g.asset)) if g.asset else None,
        )
        for g in rows
    ]


# --------------------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------------------
@router.get("/products", response_model=Page[ProductCard], summary="List products")
def list_products(
    request: Request,
    db: Session = Depends(get_db),
    page: Pagination = Depends(pagination),
    category: str | None = None,
    product_type: str | None = None,
    availability: str | None = None,
    featured: bool | None = None,
):
    stmt = select(Product).where(Product.status == "published")
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)
    if availability:
        stmt = stmt.where(Product.availability == availability)
    if featured is not None:
        stmt = stmt.where(Product.is_featured == featured)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Product.created_at.desc()).offset(page.offset).limit(page.page_size)
    ).scalars().unique().all()

    items = []
    for p in rows:
        orderable = p.availability not in ("sold_out", "coming_soon") and (
            p.stock is None or p.stock > 0
        )
        items.append(
            ProductCard(
                name=p.name,
                slug=p.slug,
                url=f"/shop/{p.slug}/",
                product_type=p.product_type,
                availability=p.availability,
                price=str(p.price),
                currency=p.currency,
                in_stock=orderable,
                primary_image=_primary_image(db, p.images, lambda i: i.asset),
            )
        )
    return page.envelope(items, total, request)


@router.get("/products/{slug}", response_model=ProductDetail, summary="Product detail")
def get_product(slug: str, db: Session = Depends(get_db)):
    product = db.execute(select(Product).where(Product.slug == slug)).scalar_one_or_none()
    if product is None or product.status != "published":
        raise HTTPException(status_code=404, detail="Product not found")

    orderable = product.availability not in ("sold_out", "coming_soon") and (
        product.stock is None or product.stock > 0
    )
    images = [
        ImageRef(
            url=f"/media/{i.asset.file}",
            dither_url=_dither_for(db, i.asset),
            width=i.asset.width,
            height=i.asset.height,
            alt=i.caption or i.asset.alt_text or "",
        )
        for i in product.images
        if i.asset
    ]
    return ProductDetail(
        name=product.name,
        slug=product.slug,
        url=f"/shop/{product.slug}/",
        product_type=product.product_type,
        availability=product.availability,
        price=str(product.price),
        currency=product.currency,
        in_stock=orderable,
        description=product.description or "",
        stock=product.stock,
        is_limited=product.is_limited,
        edition_size=product.edition_size,
        images=images,
    )
