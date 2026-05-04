from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

LookupDomesticCastFunc = Callable[["DomesticCastEnrichmentInput"], Awaitable[tuple["DomesticCastMatch", ...]]]


@dataclass(frozen=True, slots=True)
class DomesticCastEnrichmentInput:
    title: str
    original_title: str
    year: str
    tmdb_id: str
    cast_truth: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class DomesticCastMatch:
    """Helper-only localized cast text resolved from a domestic source."""

    order: int
    cast_id: str = ""
    original_name: str = ""
    localized_name: str = ""
    localized_character: str = ""
    domestic_profile_image_url: str = ""


class DomesticCastEnrichmentService:
    """Helper-only cast text supplement seam. Caller handles failure and merge policy."""

    def __init__(
        self,
        lookup_func: LookupDomesticCastFunc | None,
    ) -> None:
        self._lookup_func = lookup_func

    async def lookup(
        self,
        *,
        enrichment_input: DomesticCastEnrichmentInput,
    ) -> tuple[DomesticCastMatch, ...]:
        if self._lookup_func is None:
            return ()
        return await self._lookup_func(enrichment_input)
