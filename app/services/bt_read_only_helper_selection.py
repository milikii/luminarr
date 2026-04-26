from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.search_title_normalization import BT_RESULT_TITLE_NOISE_TOKENS, compact_match_key, normalize_match_key

BT_READ_ONLY_HELPER_TITLE_NOISE_TOKENS = frozenset(
    {
        "collection",
        "compilation",
        "edition",
        "complete",
    }
)


def prepare_bt_read_only_selection_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    helper_match: JavLibraryReadOnlyMatch | None,
) -> list[dict[str, Any]]:
    display_candidates = [_to_candidate_dict(item) for item in candidates]
    if helper_match is None:
        return display_candidates
    prioritized: list[dict[str, Any]] = []
    remainder: list[dict[str, Any]] = []
    for candidate in display_candidates:
        if _is_bt_read_only_helper_related(candidate, helper_match=helper_match):
            prioritized.append(candidate)
            continue
        remainder.append(candidate)
    return prioritized + remainder


def should_apply_bt_read_only_helper(
    candidate: Mapping[str, Any],
    *,
    helper_match: JavLibraryReadOnlyMatch,
) -> bool:
    return _is_bt_read_only_helper_related(candidate, helper_match=helper_match)


def _is_bt_read_only_helper_related(
    candidate: Mapping[str, Any],
    *,
    helper_match: JavLibraryReadOnlyMatch,
) -> bool:
    title = _safe_text(candidate.get("title"), default="")
    candidate_content_id = _safe_text(candidate.get("adult_content_id"), default="") or _safe_text(
        candidate.get("read_only_adult_content_id"),
        default="",
    )
    if candidate_content_id == helper_match.normalized_content_id:
        return True
    candidate_display_id = _safe_text(candidate.get("adult_display_id"), default="") or _safe_text(
        candidate.get("read_only_adult_display_id"),
        default="",
    )
    if candidate_display_id == helper_match.display_id:
        return True
    if not title:
        return False
    display_id_key = compact_match_key(normalize_match_key(helper_match.display_id))
    title_key = compact_match_key(normalize_match_key(title))
    if display_id_key and display_id_key in title_key:
        return True
    helper_tokens = _extract_bt_read_only_helper_tokens(helper_match.title, display_id=helper_match.display_id)
    candidate_tokens = _extract_bt_read_only_helper_tokens(title, display_id=helper_match.display_id)
    return bool(helper_tokens and candidate_tokens and helper_tokens.intersection(candidate_tokens))


def _extract_bt_read_only_helper_tokens(value: str, *, display_id: str) -> set[str]:
    normalized = normalize_match_key(value)
    if not normalized:
        return set()
    display_id_tokens = {token for token in normalize_match_key(display_id).split() if token}
    tokens: set[str] = set()
    for token in normalized.split():
        if (
            token in BT_RESULT_TITLE_NOISE_TOKENS
            or token in BT_READ_ONLY_HELPER_TITLE_NOISE_TOKENS
            or token in display_id_tokens
        ):
            continue
        if len(token) <= 1 or re.fullmatch(r"(?:19|20)\d{2}", token):
            continue
        tokens.add(token)
    return tokens


def _to_candidate_dict(item: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in item.items()}


def _safe_text(value: Any, *, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text
