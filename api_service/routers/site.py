"""Site metadata and home payload."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api_service.db.models import ArtistProfile, SiteSettings
from api_service.db.session import get_db
from api_service.schemas.content import SiteOut

router = APIRouter()


@router.get("/site", response_model=SiteOut, summary="Site settings and artist identity")
def get_site(db: Session = Depends(get_db)):
    site = db.execute(select(SiteSettings).limit(1)).scalar_one_or_none()
    artist = db.execute(select(ArtistProfile).limit(1)).scalar_one_or_none()
    return SiteOut(
        site_name=site.site_name if site else "",
        tagline=site.tagline if site else "",
        hero_kicker=site.hero_kicker if site else "",
        hero_title=site.hero_title if site else "",
        contact_email=site.contact_email if site else "",
        contact_phone=site.contact_phone if site else "",
        studio_address=site.studio_address if site else "",
        booking_open=site.booking_open if site else True,
        artist_name=artist.display_name if artist else "",
        artist_statement=artist.statement if artist else "",
        artist_biography=artist.biography if artist else "",
        artist_location=(
            ", ".join(p for p in (artist.location_city, artist.location_country) if p)
            if artist
            else ""
        ),
        social_links=[],  # populated when SocialLink is mirrored
    )
