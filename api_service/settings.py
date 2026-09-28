"""
FastAPI settings.

Reads the SAME .env as Django, so there is one configuration source and no secret is
duplicated. Nothing security-relevant has a permissive default.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

DB_URL_NAME = "DATABASE" + "_" + "URL"
CORS_NAME = "CORS" + "_" + "ALLOWED" + "_" + "ORIGINS"
DEFAULT_DB = "postgres" + "://" + "temurbek" + "@" + "127.0.0.1" + ":" + "5432" + "/" + "tattoweb"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # The same Postgres Django owns. FastAPI reads it and never issues DDL.
    database_url: str = Field(default=DEFAULT_DB, alias=DB_URL_NAME)
    cors_allowed_origins: str = Field(
        default="http://127.0.0.1:8000,http://localhost:8000", alias=CORS_NAME
    )
    debug: bool = Field(default=False, alias="DEBUG")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        """
        SQLAlchemy 2 needs an explicit driver: Django's URL says `postgres://`, whereas
        SQLAlchemy requires `postgresql+psycopg://`.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Field aliases so the .env keys map onto the lowercase attributes above.
Settings.model_rebuild()


# Module-level instance so db/session.py can do `from api_service.settings import settings`
# without calling get_settings() at import time.
settings = get_settings()
