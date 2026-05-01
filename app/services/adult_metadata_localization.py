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
    overview: AdultLocalizedText
    maker: AdultLocalizedText
    label: AdultLocalizedText
    series: AdultLocalizedText
    director: AdultLocalizedText
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
_TITLE_TRANSLATION_KEYS = ("adult_translation_title_zh",)
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
_OVERVIEW_LOCALIZED_KEYS = (
    "adult_overview_zh",
    "adult_localized_overview",
    "localized_adult_overview",
    "read_only_adult_overview_zh",
    "read_only_adult_localized_overview",
    "chineseOverview",
    "zhOverview",
)
_OVERVIEW_TRANSLATION_KEYS = ("adult_translation_overview_zh",)
_OVERVIEW_SOURCE_KEYS = (
    "adult_overview",
    "read_only_adult_overview",
    "overview",
    "description",
    "summary",
    "plot",
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
_SERIES_TRANSLATION_KEYS = ("adult_translation_series_zh",)
_SERIES_ORIGINAL_KEYS = (
    "adult_original_series",
    "originalSeries",
    "original_series",
    "read_only_adult_original_series",
)
_SERIES_SOURCE_KEYS = ("adult_series", "series", "read_only_adult_series")
_MAKER_LOCALIZED_KEYS = (
    "adult_maker_zh",
    "adult_studio_zh",
    "adult_localized_maker",
    "localized_adult_maker",
    "read_only_adult_maker_zh",
    "read_only_adult_studio_zh",
    "chineseMaker",
    "zhMaker",
)
_MAKER_TRANSLATION_KEYS = ("adult_translation_maker_zh",)
_MAKER_SOURCE_KEYS = (
    "adult_maker",
    "adult_studio",
    "maker",
    "studio",
    "publisher",
    "read_only_adult_maker",
    "read_only_adult_studio",
)
_LABEL_LOCALIZED_KEYS = (
    "adult_label_zh",
    "adult_localized_label",
    "localized_adult_label",
    "read_only_adult_label_zh",
    "read_only_adult_localized_label",
    "chineseLabel",
    "zhLabel",
)
_LABEL_TRANSLATION_KEYS = ("adult_translation_label_zh",)
_LABEL_SOURCE_KEYS = ("adult_label", "label", "read_only_adult_label")
_DIRECTOR_LOCALIZED_KEYS = (
    "adult_director_zh",
    "adult_localized_director",
    "localized_adult_director",
    "read_only_adult_director_zh",
    "read_only_adult_localized_director",
    "chineseDirector",
    "zhDirector",
)
_DIRECTOR_TRANSLATION_KEYS = ("adult_translation_director_zh",)
_DIRECTOR_SOURCE_KEYS = ("adult_director", "director", "read_only_adult_director")
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
        overview=_resolve_localized_overview(item),
        maker=_resolve_localized_maker(item),
        label=_resolve_localized_label(item),
        series=_resolve_localized_series(item),
        director=_resolve_localized_director(item),
        actors=_resolve_localized_actors(item),
    )


def _resolve_localized_title(item: Mapping[str, Any]) -> AdultLocalizedText:
    source_title = _first_text(item, _TITLE_SOURCE_KEYS)
    return _resolve_localized_text(
        item,
        source_text=source_title,
        localized_keys=_TITLE_LOCALIZED_KEYS,
        translation_keys=_TITLE_TRANSLATION_KEYS,
        original_keys=_TITLE_ORIGINAL_KEYS,
        curated_value=_resolve_curated_title_alias(item, source_title),
    )


def _resolve_localized_overview(item: Mapping[str, Any]) -> AdultLocalizedText:
    source_overview = _first_text(item, _OVERVIEW_SOURCE_KEYS)
    return _resolve_localized_text(
        item,
        source_text=source_overview,
        localized_keys=_OVERVIEW_LOCALIZED_KEYS,
        translation_keys=_OVERVIEW_TRANSLATION_KEYS,
    )


def _resolve_localized_series(item: Mapping[str, Any]) -> AdultLocalizedText:
    source_series = _first_text(item, _SERIES_SOURCE_KEYS)
    return _resolve_localized_text(
        item,
        source_text=source_series,
        localized_keys=_SERIES_LOCALIZED_KEYS,
        translation_keys=_SERIES_TRANSLATION_KEYS,
        original_keys=_SERIES_ORIGINAL_KEYS,
        curated_value=_CURATED_SERIES_ALIASES.get(source_series, ""),
    )


def _resolve_localized_maker(item: Mapping[str, Any]) -> AdultLocalizedText:
    source_maker = _first_text(item, _MAKER_SOURCE_KEYS)
    return _resolve_localized_text(
        item,
        source_text=source_maker,
        localized_keys=_MAKER_LOCALIZED_KEYS,
        translation_keys=_MAKER_TRANSLATION_KEYS,
    )


def _resolve_localized_label(item: Mapping[str, Any]) -> AdultLocalizedText:
    source_label = _first_text(item, _LABEL_SOURCE_KEYS)
    return _resolve_localized_text(
        item,
        source_text=source_label,
        localized_keys=_LABEL_LOCALIZED_KEYS,
        translation_keys=_LABEL_TRANSLATION_KEYS,
    )


def _resolve_localized_director(item: Mapping[str, Any]) -> AdultLocalizedText:
    source_director = _first_text(item, _DIRECTOR_SOURCE_KEYS)
    return _resolve_localized_text(
        item,
        source_text=source_director,
        localized_keys=_DIRECTOR_LOCALIZED_KEYS,
        translation_keys=_DIRECTOR_TRANSLATION_KEYS,
    )


def _resolve_localized_actors(item: Mapping[str, Any]) -> AdultLocalizedText:
    source_actors = _first_sequence_text(item, _ACTORS_SOURCE_KEYS)
    explicit_original = _first_sequence_text(item, _ACTORS_ORIGINAL_KEYS)
    explicit_actors = _first_sequence_text(item, _ACTORS_LOCALIZED_KEYS)
    if explicit_actors:
        original = explicit_original or _original_when_different(explicit_actors, source_actors)
        return AdultLocalizedText(value=explicit_actors, original=original)
    consensus_actors = _resolve_consensus_sequence_text(item, _ACTORS_LOCALIZED_KEYS)
    if consensus_actors:
        original = explicit_original or _original_when_different(consensus_actors, source_actors)
        return AdultLocalizedText(value=consensus_actors, original=original)

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


def _resolve_localized_text(
    item: Mapping[str, Any],
    *,
    source_text: str,
    localized_keys: Sequence[str],
    translation_keys: Sequence[str] = (),
    original_keys: Sequence[str] = (),
    curated_value: str = "",
) -> AdultLocalizedText:
    explicit_original = _first_text(item, original_keys)
    explicit_localized = _first_text(item, localized_keys)
    if explicit_localized:
        original = explicit_original or _original_when_different(explicit_localized, source_text)
        return AdultLocalizedText(value=explicit_localized, original=original)
    consensus_value = _resolve_consensus_text(item, localized_keys)
    if consensus_value:
        original = explicit_original or _original_when_different(consensus_value, source_text)
        return AdultLocalizedText(value=consensus_value, original=original)
    translated_value = _first_text(item, translation_keys)
    if translated_value:
        original = explicit_original or _original_when_different(translated_value, source_text)
        return AdultLocalizedText(value=translated_value, original=original)
    if curated_value:
        original = source_text or explicit_original
        return AdultLocalizedText(value=curated_value, original=original)
    if explicit_original and source_text and explicit_original != source_text:
        return AdultLocalizedText(value=source_text, original=explicit_original)
    return AdultLocalizedText(value=source_text)


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
