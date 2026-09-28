"""
Shared FastAPI dependencies: pagination, rate limiting, cache headers.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Query, Request, status

MAX_PAGE_SIZE = 100


@dataclass
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def envelope(self, items, total: int, request: Request) -> dict:
        pages = max(1, (total + self.page_size - 1) // self.page_size)

        def link(p: int) -> str:
            return str(request.url.include_query_params(page=p))

        return {
            "items": items,
            "page": self.page,
            "page_size": self.page_size,
            "total": total,
            "pages": pages,
            "next": link(self.page + 1) if self.page < pages else None,
            "previous": link(self.page - 1) if self.page > 1 else None,
        }


def pagination(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(24, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
) -> Pagination:
    return Pagination(page=page, page_size=page_size)


# --------------------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------------------
class RateLimiter:
    """
    In-process sliding-window limiter.

    Deliberately not Redis-backed: the deployment is a single process, and this exists to
    stop form abuse, not to enforce fair-share scheduling. If the API is ever scaled
    horizontally this must move to a shared store — noted so the limitation is not
    mistaken for an oversight.
    """

    def __init__(self, *, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, request: Request) -> None:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            retry = int(self.window - (now - bucket[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Try again in {retry} seconds.",
                headers={"Retry-After": str(retry)},
            )
        bucket.append(now)


def client_key(request: Request) -> str:
    """Identify a client for rate limiting, honouring a proxy header when present."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# One limiter per abuse-sensitive route.
booking_limiter = RateLimiter(limit=5, window_seconds=3600)
contact_limiter = RateLimiter(limit=5, window_seconds=3600)
