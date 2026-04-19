from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_SEASON_EPISODE_RE = re.compile(
    r"\bS(?P<season>\d{1,2})E(?P<episode>\d{1,3})(?:-(?P<episode_end>\d{1,3}))?\b",
    flags=re.IGNORECASE,
)
_SEASON_TEXT_RE = re.compile(r"第\s*(?P<season>\d{1,3})\s*季")
_EPISODE_TEXT_RE = re.compile(r"(?P<episode>\d{1,3})\s*(?:话|話|集)")
_EPISODE_PREFIX_RE = re.compile(r"\bEP?\s*(?P<episode>\d{1,3})\b", flags=re.IGNORECASE)
_BRACKET_EPISODE_RE = re.compile(r"\[(?P<episode>\d{1,4})\]")
_LOOSE_EPISODE_RE = re.compile(r"(?:^|[\s._-])(?P<episode>\d{1,4})(?:$|[\s._-])")
_BRACKETED_YEAR_RE = re.compile(r"[\[(](?P<year>(?:19|20)\d{2})[\])]")
_YEAR_RE = re.compile(r"(?<!\d)(?P<year>(?:19|20)\d{2})(?!\d)")
_LEADING_BRACKET_RE = re.compile(r"^\[(?P<tag>[^\[\]]+)\]")
_TRAILING_GROUP_RE = re.compile(r"(?:^|[\s._-])(?P<group>[A-Z0-9]{2,16})(?:$|[\s._-])")
_CONTAINER_SUFFIX_RE = re.compile(r"\.(?P<container>mkv|mp4|ass|srt)\s*$", flags=re.IGNORECASE)
_CONTAINER_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])(?P<container>mkv|mp4|ass|srt)(?![A-Za-z0-9])", flags=re.IGNORECASE)
_CHINESE_PHRASE_RE = re.compile(r"[\u3400-\u9fff][\u3400-\u9fff0-9·・\s'’:：-]{0,80}")
_LATIN_PHRASE_RE = re.compile(r"[A-Za-z][A-Za-z0-9'’:&+\s-]{0,80}")

_STRIP_TAG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("国配", re.compile(r"(?<![\w\u3400-\u9fff])国配(?![\w\u3400-\u9fff])", flags=re.IGNORECASE)),
    ("繁中", re.compile(r"(?<![\w\u3400-\u9fff])繁中(?![\w\u3400-\u9fff])", flags=re.IGNORECASE)),
    ("简中", re.compile(r"(?<![\w\u3400-\u9fff])简中(?![\w\u3400-\u9fff])", flags=re.IGNORECASE)),
    ("简繁", re.compile(r"(?<![\w\u3400-\u9fff])简繁(?![\w\u3400-\u9fff])", flags=re.IGNORECASE)),
    ("无字幕", re.compile(r"(?<![\w\u3400-\u9fff])无字幕(?![\w\u3400-\u9fff])", flags=re.IGNORECASE)),
    ("中日双语", re.compile(r"(?<![\w\u3400-\u9fff])中日双语(?![\w\u3400-\u9fff])", flags=re.IGNORECASE)),
    ("双语", re.compile(r"(?<![\w\u3400-\u9fff])双语(?![\w\u3400-\u9fff])", flags=re.IGNORECASE)),
    ("CHS", re.compile(r"(?<![A-Za-z0-9])CHS(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("CHT", re.compile(r"(?<![A-Za-z0-9])CHT(?![A-Za-z0-9])", flags=re.IGNORECASE)),
)
_QUALITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("2160p", re.compile(r"(?<![A-Za-z0-9])2160p(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("1080p", re.compile(r"(?<![A-Za-z0-9])1080p(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("720p", re.compile(r"(?<![A-Za-z0-9])720p(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("WEB-DL", re.compile(r"(?<![A-Za-z0-9])WEB[-_. ]?DL(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("WEBRip", re.compile(r"(?<![A-Za-z0-9])WEB[-_. ]?Rip(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("BluRay", re.compile(r"(?<![A-Za-z0-9])BluRay(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("BDRip", re.compile(r"(?<![A-Za-z0-9])BDRip(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("HDR", re.compile(r"(?<![A-Za-z0-9])HDR(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("DV", re.compile(r"(?<![A-Za-z0-9])DV(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("10bit", re.compile(r"(?<![A-Za-z0-9])10bit(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("HEVC", re.compile(r"(?<![A-Za-z0-9])HEVC(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("x264", re.compile(r"(?<![A-Za-z0-9])x264(?![A-Za-z0-9])", flags=re.IGNORECASE)),
    ("x265", re.compile(r"(?<![A-Za-z0-9])x265(?![A-Za-z0-9])", flags=re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ParsedMediaName:
    title: str
    alt_titles: tuple[str, ...]
    year: int | None
    season: int | None
    episode: int | None
    episode_end: int | None
    quality_tags: tuple[str, ...]
    source_group: str | None
    container: str | None
    media_kind: str
    raw: str
    parser_confidence: float


@dataclass(frozen=True, slots=True)
class _EpisodeParseResult:
    season: int | None
    episode: int | None
    episode_end: int | None
    text: str
    strong_match: bool
    loose_match: bool


def parse_media_name(raw: str) -> ParsedMediaName:
    normalized_raw = _normalize_text(raw)
    if not normalized_raw:
        return ParsedMediaName(
            title="",
            alt_titles=(),
            year=None,
            season=None,
            episode=None,
            episode_end=None,
            quality_tags=(),
            source_group=None,
            container=None,
            media_kind="unknown",
            raw=raw,
            parser_confidence=0.0,
        )

    working_text = normalized_raw
    source_group, working_text = _extract_source_group(working_text)
    container, working_text = _extract_container(working_text)
    year, working_text = _extract_year(working_text)
    episode_result = _extract_episode_context(working_text)
    working_text = episode_result.text
    quality_tags, working_text = _extract_quality_tags(working_text)
    stripped_tags, working_text = _strip_noise_tags(working_text)
    if container is None:
        container, working_text = _extract_container_token(working_text)
    if source_group is None:
        source_group, working_text = _extract_trailing_group(working_text)

    title, alt_titles = _extract_titles(working_text)
    media_kind = _infer_media_kind(
        title=title,
        year=year,
        season=episode_result.season,
        episode=episode_result.episode,
        source_group=source_group,
        loose_episode=episode_result.loose_match,
    )
    parser_confidence = _compute_confidence(
        raw=normalized_raw,
        title=title,
        year=year,
        strong_episode=episode_result.strong_match,
        loose_episode=episode_result.loose_match,
        recognized_metadata=bool(stripped_tags or quality_tags or source_group or container),
    )
    return ParsedMediaName(
        title=title,
        alt_titles=alt_titles,
        year=year,
        season=episode_result.season,
        episode=episode_result.episode,
        episode_end=episode_result.episode_end,
        quality_tags=quality_tags,
        source_group=source_group,
        container=container,
        media_kind=media_kind,
        raw=raw,
        parser_confidence=parser_confidence,
    )


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = (
        normalized.replace("【", "[")
        .replace("】", "]")
        .replace("「", " ")
        .replace("」", " ")
        .replace("『", " ")
        .replace("』", " ")
        .replace("．", ".")
    )
    normalized = re.sub(r"\s+", " ", normalized.strip())
    return normalized


def _extract_source_group(text: str) -> tuple[str | None, str]:
    match = _LEADING_BRACKET_RE.match(text)
    if match is None:
        return None, text
    tag = _clean_phrase(match.group("tag"))
    if not _looks_like_source_group(tag):
        return None, text
    remaining = _normalize_text(text[match.end() :])
    return tag, remaining


def _looks_like_source_group(value: str) -> bool:
    if not value:
        return False
    if _BRACKETED_YEAR_RE.fullmatch(f"[{value}]") or _YEAR_RE.fullmatch(value):
        return False
    if _SEASON_EPISODE_RE.fullmatch(value) or _SEASON_TEXT_RE.fullmatch(value) or _EPISODE_TEXT_RE.fullmatch(value):
        return False
    if any(pattern.fullmatch(value) for _, pattern in _QUALITY_PATTERNS):
        return False
    if any(pattern.fullmatch(value) for _, pattern in _STRIP_TAG_PATTERNS):
        return False
    if value.lower() in {"mkv", "mp4", "ass", "srt"}:
        return False
    if re.search(r"sub|字幕|studio|压制|搬运|组", value, flags=re.IGNORECASE):
        return True
    if re.search(r"[._+-]", value):
        return True
    return bool(re.search(r"[a-z][A-Z]|[A-Z]{2,}", value))


def _extract_container(text: str) -> tuple[str | None, str]:
    match = _CONTAINER_SUFFIX_RE.search(text)
    if match is None:
        return None, text
    container = match.group("container").lower()
    remaining = _normalize_text(text[: match.start()])
    return container, remaining


def _extract_container_token(text: str) -> tuple[str | None, str]:
    match = _CONTAINER_TOKEN_RE.search(text)
    if match is None:
        return None, text
    container = match.group("container").lower()
    remaining = _normalize_text(f"{text[: match.start()]} {text[match.end() :]}")
    return container, remaining


def _extract_year(text: str) -> tuple[int | None, str]:
    bracket_match = _BRACKETED_YEAR_RE.search(text)
    if bracket_match is not None:
        year = int(bracket_match.group("year"))
        remaining = _normalize_text(f"{text[: bracket_match.start()]} {text[bracket_match.end() :]}")
        return year, remaining

    match = _YEAR_RE.search(text)
    if match is None:
        return None, text
    year = int(match.group("year"))
    remaining = _normalize_text(f"{text[: match.start()]} {text[match.end() :]}")
    return year, remaining


def _extract_episode_context(text: str) -> _EpisodeParseResult:
    season: int | None = None
    episode: int | None = None
    episode_end: int | None = None
    working_text = text
    strong_match = False
    loose_match = False

    season_episode_match = _SEASON_EPISODE_RE.search(working_text)
    if season_episode_match is not None:
        season = int(season_episode_match.group("season"))
        episode = int(season_episode_match.group("episode"))
        episode_end = (
            int(season_episode_match.group("episode_end"))
            if season_episode_match.group("episode_end") is not None
            else None
        )
        working_text = _normalize_text(
            f"{working_text[: season_episode_match.start()]} {working_text[season_episode_match.end() :]}"
        )
        strong_match = True

    if season is None:
        season_text_match = _SEASON_TEXT_RE.search(working_text)
        if season_text_match is not None:
            season = int(season_text_match.group("season"))
            working_text = _normalize_text(
                f"{working_text[: season_text_match.start()]} {working_text[season_text_match.end() :]}"
            )
            strong_match = True

    if episode is None:
        for pattern in (_EPISODE_TEXT_RE, _EPISODE_PREFIX_RE):
            episode_match = pattern.search(working_text)
            if episode_match is None:
                continue
            episode = int(episode_match.group("episode"))
            working_text = _normalize_text(f"{working_text[: episode_match.start()]} {working_text[episode_match.end() :]}")
            strong_match = True
            break

    if episode is None:
        bracket_episode_match = _BRACKET_EPISODE_RE.search(working_text)
        if bracket_episode_match is not None:
            episode = int(bracket_episode_match.group("episode"))
            if episode < 1900:
                working_text = _normalize_text(
                    f"{working_text[: bracket_episode_match.start()]} {working_text[bracket_episode_match.end() :]}"
                )
                strong_match = True
            else:
                episode = None

    if episode is None:
        loose_match_result = _find_loose_episode(working_text)
        if loose_match_result is not None:
            episode = loose_match_result[0]
            working_text = loose_match_result[1]
            loose_match = True

    return _EpisodeParseResult(
        season=season,
        episode=episode,
        episode_end=episode_end,
        text=working_text,
        strong_match=strong_match,
        loose_match=loose_match,
    )


def _find_loose_episode(text: str) -> tuple[int, str] | None:
    matches = list(_LOOSE_EPISODE_RE.finditer(text))
    if not matches:
        return None
    match = matches[-1]
    candidate = int(match.group("episode"))
    if candidate >= 1900:
        return None
    remaining = _normalize_text(f"{text[: match.start('episode')]} {text[match.end('episode') :]}")
    return candidate, remaining


def _extract_quality_tags(text: str) -> tuple[tuple[str, ...], str]:
    quality_tags: list[str] = []
    working_text = text
    for label, pattern in _QUALITY_PATTERNS:
        if pattern.search(working_text) is None:
            continue
        working_text = pattern.sub(" ", working_text)
        quality_tags.append(label)
    return tuple(quality_tags), _normalize_text(working_text)


def _strip_noise_tags(text: str) -> tuple[tuple[str, ...], str]:
    removed_tags: list[str] = []
    working_text = text
    for label, pattern in _STRIP_TAG_PATTERNS:
        if pattern.search(working_text) is None:
            continue
        working_text = pattern.sub(" ", working_text)
        removed_tags.append(label)
    return tuple(removed_tags), _normalize_text(working_text)


def _extract_trailing_group(text: str) -> tuple[str | None, str]:
    match = _TRAILING_GROUP_RE.search(text)
    if match is None:
        return None, text
    group = match.group("group")
    if not group.isupper():
        return None, text
    remaining = _normalize_text(f"{text[: match.start('group')]} {text[match.end('group') :]}")
    return group, remaining


def _extract_titles(text: str) -> tuple[str, tuple[str, ...]]:
    candidate_text = text.replace("[", " ").replace("]", " ")
    candidate_text = re.sub(r"[./_]+", " ", candidate_text)
    candidate_text = re.sub(r"\s*-\s*", " ", candidate_text)
    candidate_text = re.sub(r"(?<![A-Za-z0-9])\d{1,4}(?![A-Za-z0-9])", " ", candidate_text)
    candidate_text = re.sub(r"(?<![A-Za-z0-9])(AVC|AAC)(?![A-Za-z0-9])", " ", candidate_text, flags=re.IGNORECASE)
    candidate_text = _normalize_text(candidate_text)
    if not candidate_text:
        return "", ()

    chinese_phrases = _unique_phrases(_CHINESE_PHRASE_RE.findall(candidate_text))
    latin_phrases = _unique_phrases(_LATIN_PHRASE_RE.findall(candidate_text))

    if chinese_phrases:
        title = max(chinese_phrases, key=_phrase_sort_key)
        alt_titles = tuple(phrase for phrase in latin_phrases if phrase.lower() != title.lower())
        return title, alt_titles

    if latin_phrases:
        title = max(latin_phrases, key=_phrase_sort_key)
        alt_titles = tuple(phrase for phrase in latin_phrases if phrase.lower() != title.lower())
        return title, alt_titles

    fallback = _clean_phrase(candidate_text)
    return fallback, ()


def _unique_phrases(values: list[str]) -> list[str]:
    phrases: list[str] = []
    for value in values:
        cleaned = _clean_phrase(value)
        if len(cleaned) < 2:
            continue
        if cleaned.upper() in {"AVC", "AAC"}:
            continue
        if cleaned.lower() in {"mkv", "mp4", "ass", "srt"}:
            continue
        if cleaned not in phrases:
            phrases.append(cleaned)
    return phrases


def _clean_phrase(value: str) -> str:
    cleaned = value.strip(" -._:：[](){}")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _phrase_sort_key(value: str) -> tuple[int, int]:
    meaningful_length = len(re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", value))
    has_cjk = 1 if _CJK_RE.search(value) else 0
    return has_cjk, meaningful_length


def _infer_media_kind(
    *,
    title: str,
    year: int | None,
    season: int | None,
    episode: int | None,
    source_group: str | None,
    loose_episode: bool,
) -> str:
    if season is not None or episode is not None:
        if source_group is not None or loose_episode:
            return "anime"
        return "series"
    if year is not None and title:
        return "movie"
    return "unknown"


def _compute_confidence(
    *,
    raw: str,
    title: str,
    year: int | None,
    strong_episode: bool,
    loose_episode: bool,
    recognized_metadata: bool,
) -> float:
    if not title:
        return 0.0

    if strong_episode:
        confidence = 0.8
    elif loose_episode:
        confidence = 0.48
    elif year is not None:
        confidence = 0.75
    else:
        confidence = 0.5

    if recognized_metadata:
        confidence += 0.1

    title_chars = len(re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", title))
    raw_chars = len(re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", raw))
    if raw_chars > 0 and title_chars / raw_chars < 0.35:
        confidence -= 0.2

    return max(0.0, min(1.0, round(confidence, 2)))
