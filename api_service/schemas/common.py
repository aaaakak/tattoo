"""Shared response shapes: pagination envelope and errors."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Consistent pagination envelope for every list endpoint."""

    items: list[T]
    page: int
    page_size: int
    total: int
    pages: int
    next: str | None = None
    previous: str | None = None


class ErrorBody(BaseModel):
    detail: str
    code: str | None = None


class ImageRef(BaseModel):
    """A public image reference. Never exposes the filesystem path."""

    url: str
    dither_url: str | None = None
    width: int = 0
    height: int = 0
    alt: str = ""


class Meta(BaseModel):
    version: str
    schema_contract: str
    site_name: str = ""
