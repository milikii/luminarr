from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.clients.tmdb import TmdbMovie

MEDIA_IDENTITY_EVENT_TYPE = "media.identity.confirmed"


def build_media_identity_from_tmdb_movie(
    tmdb_movie: TmdbMovie | None,
    *,
    source: str = "search_confirmed",
) -> dict[str, str] | None:
    if tmdb_movie is None:
        return None
    return normalize_media_identity_payload(
        {
            "media_type": tmdb_movie.media_type,
            "tmdb_id": tmdb_movie.tmdb_id,
            "title": tmdb_movie.title,
            "original_title": tmdb_movie.original_title,
            "year": tmdb_movie.year,
            "source": source,
        }
    )


def normalize_media_identity_payload(payload: Mapping[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(payload, Mapping):
        return None
    normalized_payload = {
        "media_type": str(payload.get("media_type", "")).strip() or "movie",
        "tmdb_id": str(payload.get("tmdb_id", "")).strip(),
        "title": str(payload.get("title", "")).strip(),
        "original_title": str(payload.get("original_title", "")).strip(),
        "year": str(payload.get("year", "")).strip(),
        "source": str(payload.get("source", "")).strip() or "search_confirmed",
    }
    if not any(
        (
            normalized_payload["tmdb_id"],
            normalized_payload["title"],
            normalized_payload["original_title"],
        )
    ):
        return None
    return normalized_payload


def media_identity_to_json(payload: Mapping[str, Any] | None) -> str:
    normalized_payload = normalize_media_identity_payload(payload)
    if normalized_payload is None:
        return ""
    return json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True)


def media_identity_from_json(payload_json: str) -> dict[str, str] | None:
    cleaned_payload = payload_json.strip()
    if not cleaned_payload:
        return None
    try:
        payload = json.loads(cleaned_payload)
    except json.JSONDecodeError:
        return None
    return normalize_media_identity_payload(payload if isinstance(payload, Mapping) else None)
