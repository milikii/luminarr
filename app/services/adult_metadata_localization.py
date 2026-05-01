from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AdultLocalizedText:
    value: str
    original: str = ""
    unresolved: bool = False


@dataclass(frozen=True, slots=True)
class AdultLocalizedMetadata:
    title: AdultLocalizedText
    series: AdultLocalizedText
    actors: AdultLocalizedText


_TITLE_LOCALIZED_KEYS = (
    "adult_title_zh",
    "adult_localized_title",
    "localized_adult_title",
    "metadataTitleZh",
    "metadata_title_zh",
    "read_only_adult_title_zh",
    "read_only_adult_localized_title",
    "chineseTitle",
    "zhTitle",
)
_TITLE_ORIGINAL_KEYS = (
    "adult_original_title",
    "originalTitle",
    "original_title",
    "read_only_adult_original_title",
)
_TITLE_SOURCE_KEYS = (
    "adult_title",
    "metadataTitle",
    "metadata_title",
    "read_only_adult_title",
    "title",
)
_SERIES_LOCALIZED_KEYS = (
    "adult_series_zh",
    "adult_localized_series",
    "localized_adult_series",
    "read_only_adult_series_zh",
    "read_only_adult_localized_series",
    "chineseSeries",
    "zhSeries",
)
_SERIES_ORIGINAL_KEYS = (
    "adult_original_series",
    "originalSeries",
    "original_series",
    "read_only_adult_original_series",
)
_SERIES_SOURCE_KEYS = ("adult_series", "series", "read_only_adult_series")
_ACTORS_LOCALIZED_KEYS = (
    "adult_actors_zh",
    "adult_localized_actors",
    "localized_adult_actors",
    "read_only_adult_actors_zh",
    "read_only_adult_localized_actors",
    "chineseActors",
    "zhActors",
)
_ACTORS_ORIGINAL_KEYS = (
    "adult_original_actors",
    "originalActors",
    "original_actors",
    "read_only_adult_original_actors",
)
_ACTORS_SOURCE_KEYS = ("adult_actors", "actors", "actresses", "cast", "read_only_adult_actors")
_METADATA_CANDIDATE_KEYS = (
    "adult_metadata_candidates",
    "read_only_adult_metadata_candidates",
    "metadata_candidates",
)
_SOURCE_NAME_KEYS = (
    "source_site",
    "sourceSite",
    "metadataSource",
    "metadata_source",
    "read_only_adult_source_site",
)

_CURATED_TITLE_ALIASES: dict[tuple[str, str], str] = {
    (
        "ssis-483",
        "シン・交わる体液、濃密セックス 完全ノーカット5本番",
    ): "新·交融的体液、浓密性爱 完全未删减 5本番",
}
_CURATED_SERIES_ALIASES = {
    "交わる体液、濃密セックス": "交融的体液、浓密性爱",
}
_CURATED_ACTOR_ALIASES = {
    "七ツ森りり": "七森莉莉",
}


def resolve_adult_localized_metadata(item: Mapping[str, Any]) -> AdultLocalizedMetadata:
    """Resolve trusted Chinese adult metadata while retaining original source text."""
    return AdultLocalizedMetadata(
        title=_resolve_localized_title(item),
        series=_resolve_localized_series(item),
        actors=_resolve_localized_actors(item),
    )


def _resolve_localized_title(item: Mapping[str, Any]) -> AdultLocalizedText:
    source_title = _first_text(item, _TITLE_SOURCE_KEYS)
    explicit_original = _first_text(item, _TITLE_ORIGINAL_KEYS)
    consensus_title = _resolve_consensus_text(item, _TITLE_LOCALIZED_KEYS)
    if consensus_title:
        original = explicit_original or _original_when_different(consensus_title, source_title)
        return AdultLocalizedText(value=consensus_title, original=original)
    explicit_title = _first_text(item, _TITLE_LOCALIZED_KEYS)
    if explicit_title:
        original = explicit_original or _original_when_different(explicit_title, source_title)
        return AdultLocalizedText(value=explicit_title, original=original)

    curated_title = _resolve_curated_title_alias(item, source_title)
    if curated_title:
        return AdultLocalizedText(value=curated_title, original=source_title)
    if explicit_original and source_title and explicit_original != source_title:
        return AdultLocalizedText(value=source_title, original=explicit_original)
    return AdultLocalizedText(value=source_title)


def _resolve_localized_series(item: Mapping[str, Any]) -> AdultLocalizedText:
    source_series = _first_text(item, _SERIES_SOURCE_KEYS)
    explicit_original = _first_text(item, _SERIES_ORIGINAL_KEYS)
    consensus_series = _resolve_consensus_text(item, _SERIES_LOCALIZED_KEYS)
    if consensus_series:
        original = explicit_original or _original_when_different(consensus_series, source_series)
        return AdultLocalizedText(value=consensus_series, original=original)
    explicit_series = _first_text(item, _SERIES_LOCALIZED_KEYS)
    if explicit_series:
        original = explicit_original or _original_when_different(explicit_series, source_series)
        return AdultLocalizedText(value=explicit_series, original=original)

    curated_series = _CURATED_SERIES_ALIASES.get(source_series, "")
    if curated_series:
        return AdultLocalizedText(value=curated_series, original=source_series)
    if explicit_original and source_series and explicit_original != source_series:
        return AdultLocalizedText(value=source_series, original=explicit_original)
    return AdultLocalizedText(value=source_series)


def _resolve_localized_actors(item: Mapping[str, Any]) -> AdultLocalizedText:
    source_actors = _first_sequence_text(item, _ACTORS_SOURCE_KEYS)
    explicit_original = _first_sequence_text(item, _ACTORS_ORIGINAL_KEYS)
    consensus_actors = _resolve_consensus_sequence_text(item, _ACTORS_LOCALIZED_KEYS)
    if consensus_actors:
        original = explicit_original or _original_when_different(consensus_actors, source_actors)
        return AdultLocalizedText(value=consensus_actors, original=original)
    explicit_actors = _first_sequence_text(item, _ACTORS_LOCALIZED_KEYS)
    if explicit_actors:
        original = explicit_original or _original_when_different(explicit_actors, source_actors)
        return AdultLocalizedText(value=explicit_actors, original=original)

    source_parts = _split_actor_names(source_actors)
    if not source_parts:
        return AdultLocalizedText(value="")

    localized_parts: list[str] = []
    unresolved = False
    changed = False
    for actor_name in source_parts:
        localized_name = _CURATED_ACTOR_ALIASES.get(actor_name, "")
        if localized_name:
            localized_parts.append(localized_name)
            changed = True
            continue
        if _contains_japanese_kana(actor_name):
            localized_parts.append(f"{actor_name}（中文名未确认）")
            unresolved = True
            continue
        localized_parts.append(actor_name)
    original = source_actors if changed and source_actors != " / ".join(localized_parts) else ""
    return AdultLocalizedText(value=" / ".join(localized_parts), original=original, unresolved=unresolved)


def _resolve_curated_title_alias(item: Mapping[str, Any], source_title: str) -> str:
    if not source_title:
        return ""
    normalized_title = _normalize_text(source_title)
    for display_id in _candidate_display_ids(item):
        curated_title = _CURATED_TITLE_ALIASES.get((display_id.lower(), normalized_title), "")
        if curated_title:
            return curated_title
    return ""


def _resolve_consensus_text(item: Mapping[str, Any], keys: Sequence[str]) -> str:
    return _resolve_consensus_value(item, lambda candidate: _first_text(candidate, keys))


def _resolve_consensus_sequence_text(item: Mapping[str, Any], keys: Sequence[str]) -> str:
    return _resolve_consensus_value(item, lambda candidate: _first_sequence_text(candidate, keys))


def _resolve_consensus_value(item: Mapping[str, Any], resolve_value) -> str:
    values_by_source: dict[str, set[str]] = {}
    for index, candidate in enumerate(_iter_metadata_candidate_items(item), start=1):
        value = resolve_value(candidate)
        if not value:
            continue
        source_name = _first_text(candidate, _SOURCE_NAME_KEYS) or f"source-{index}"
        values_by_source.setdefault(value, set()).add(source_name)
    for value, source_names in values_by_source.items():
        if len(source_names) >= 2:
            return value
    return ""


def _iter_metadata_candidate_items(item: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    collected: list[Mapping[str, Any]] = []
    for key in _METADATA_CANDIDATE_KEYS:
        value = item.get(key)
        if isinstance(value, Mapping):
            collected.append(value)
            continue
        if not isinstance(value, Sequence) or isinstance(value, str):
            continue
        collected.extend(candidate for candidate in value if isinstance(candidate, Mapping))
    return tuple(collected)


def _candidate_display_ids(item: Mapping[str, Any]) -> tuple[str, ...]:
    values = (
        item.get("adult_display_id"),
        item.get("read_only_adult_display_id"),
        item.get("display_id"),
        item.get("content_id"),
    )
    resolved = tuple(dict.fromkeys(text for value in values if (text := _safe_text(value))))
    return resolved


def _original_when_different(localized: str, source: str) -> str:
    if not source:
        return ""
    return source if _normalize_text(localized) != _normalize_text(source) else ""


def _first_text(item: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        text = _safe_text(item.get(key))
        if text:
            return text
    return ""


def _first_sequence_text(item: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str):
            text = _safe_text(value)
            if text:
                return text
            continue
        if isinstance(value, Sequence):
            parts = [_safe_text(part) for part in value]
            text = " / ".join(part for part in parts if part)
            if text:
                return text
            continue
        text = _safe_text(value)
        if text:
            return text
    return ""


def _split_actor_names(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"\s*/\s*|[,，、]+", value) if part.strip()]


def _contains_japanese_kana(value: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff]", value))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return text
