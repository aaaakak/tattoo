"""Cross-entity search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from api_service.db.models import Artwork, Product, Tattoo, TattooStyle
from api_service.db.session import get_db
from api_service.schemas.content import SearchGroup, SearchOut

router = APIRouter()

MIN_QUERY_LENGTH = 2


@router.get("/search", response_model=SearchOut, summary="Search tattoos, artwork, styles and products")
def search(
    db: Session = Depends(get_db),
    q: str = Query(..., min_length=MIN_QUERY_LENGTH, description="Search terms"),
    limit_per_group: int = Query(5, ge=1, le=20),
):
    """
    Search across the content types.

    Uses ILIKE rather than full-text search: the dataset is small (hundreds of rows), and
    a GIN index on a generated search_vector is documented as the scaling path in
    docs/erd.md rather than being premature here.
    """
    like = f"%{q}%"
    groups: list[SearchGroup] = []
    total = 0

    tattoos = db.execute(
        select(Tattoo)
        .where(
            Tattoo.status == "published",
            or_(Tattoo.title.ilike(like), Tattoo.description.ilike(like), Tattoo.placement.ilike(like)),
        )
        .limit(limit_per_group)
    ).scalars().all()
    if tattoos:
        count = db.execute(
            select(func.count()).select_from(Tattoo).where(
                Tattoo.status == "published",
                or_(Tattoo.title.ilike(like), Tattoo.description.ilike(like), Tattoo.placement.ilike(like)),
            )
        ).scalar_one()
        total += count
        groups.append(SearchGroup(
            kind="tattoo", label="Tattoos", count=count,
            items=[{"title": t.title, "slug": t.slug, "url": f"/tattoos/{t.slug}/",
                    "meta": t.placement or ""} for t in tattoos],
        ))

    styles = db.execute(
        select(TattooStyle).where(
            or_(TattooStyle.name.ilike(like), TattooStyle.description.ilike(like))
        ).limit(limit_per_group)
    ).scalars().all()
    if styles:
        count = db.execute(
            select(func.count()).select_from(TattooStyle).where(
                or_(TattooStyle.name.ilike(like), TattooStyle.description.ilike(like))
            )
        ).scalar_one()
        total += count
        groups.append(SearchGroup(
            kind="style", label="Styles", count=count,
            items=[{"title": s.name, "slug": s.slug, "url": f"/styles/{s.slug}/", "meta": ""} for s in styles],
        ))

    artworks = db.execute(
        select(Artwork).where(
            Artwork.status == "published",
            or_(Artwork.title.ilike(like), Artwork.description.ilike(like), Artwork.medium.ilike(like)),
        ).limit(limit_per_group)
    ).scalars().all()
    if artworks:
        count = db.execute(
            select(func.count()).select_from(Artwork).where(
                Artwork.status == "published",
                or_(Artwork.title.ilike(like), Artwork.description.ilike(like), Artwork.medium.ilike(like)),
            )
        ).scalar_one()
        total += count
        groups.append(SearchGroup(
            kind="artwork", label="Artwork", count=count,
            items=[{"title": a.title, "slug": a.slug, "url": f"/artworks/{a.slug}/",
                    "meta": a.medium or ""} for a in artworks],
        ))

    products = db.execute(
        select(Product).where(
            Product.status == "published",
            or_(Product.name.ilike(like), Product.description.ilike(like)),
        ).limit(limit_per_group)
    ).scalars().all()
    if products:
        count = db.execute(
            select(func.count()).select_from(Product).where(
                Product.status == "published",
                or_(Product.name.ilike(like), Product.description.ilike(like)),
            )
        ).scalar_one()
        total += count
        groups.append(SearchGroup(
            kind="product", label="Shop", count=count,
            items=[{"title": p.name, "slug": p.slug, "url": f"/shop/{p.slug}/",
                    "meta": f"{p.price} {p.currency}"} for p in products],
        ))

    return SearchOut(query=q, total=total, groups=groups)
