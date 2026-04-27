from __future__ import annotations

import ast
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.operational_logging import emit_operational_log

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
_DEFAULT_RULES_PATH = Path(__file__).with_name("naming_rules.yml")
_DEFAULT_STRIP_TAGS = (
    "国配",
    "繁中",
    "简中",
    "简繁",
    "无字幕",
    "中日双语",
    "双语",
    "CHS",
    "CHT",
)
_DEFAULT_QUALITY_WHITELIST = (
    "2160p",
    "1080p",
    "720p",
    "WEB-DL",
    "WEBRip",
    "BluRay",
    "BDRip",
    "HDR",
    "DV",
    "10bit",
    "HEVC",
    "x264",
    "x265",
)


@dataclass(frozen=True, slots=True)
class AltTitleRule:
    primary: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NamingRules:
    strip_tags: tuple[str, ...]
    quality_whitelist: tuple[str, ...]
    alt_titles: tuple[AltTitleRule, ...]


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


_DEFAULT_NAMING_RULES = NamingRules(
    strip_tags=_DEFAULT_STRIP_TAGS,
    quality_whitelist=_DEFAULT_QUALITY_WHITELIST,
    alt_titles=(),
)


def load_naming_rules(config_path: Path | None = None) -> NamingRules:
    resolved_path = (config_path or _DEFAULT_RULES_PATH).expanduser()
    if not resolved_path.exists():
        return _DEFAULT_NAMING_RULES
    return _load_naming_rules_cached(str(resolved_path.resolve()))


@lru_cache(maxsize=8)
def _load_naming_rules_cached(config_path: str) -> NamingRules:
    path = Path(config_path)
    try:
        return _parse_naming_rules_yaml(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, SyntaxError) as error:
        emit_operational_log(
            title="命名规则文件读取失败",
            detail=f"path={path} 错误={error}",
            fix_hint="检查 app/services/naming_rules.yml 缩进、引号和 aliases 列表格式；当前会回退到内置最小规则，避免把解析链直接卡死。",
        )
        return _DEFAULT_NAMING_RULES


def parse_media_name(raw: str, *, naming_rules: NamingRules | None = None) -> ParsedMediaName:
    resolved_rules = naming_rules or load_naming_rules()
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
    quality_tags, working_text = _extract_quality_tags(working_text, resolved_rules.quality_whitelist)
    stripped_tags, working_text = _strip_noise_tags(working_text, resolved_rules.strip_tags)
    if container is None:
        container, working_text = _extract_container_token(working_text)
    if source_group is None:
        source_group, working_text = _extract_trailing_group(working_text)

    title, alt_titles = _extract_titles(working_text)
    alt_titles = _apply_alt_title_rules(title=title, alt_titles=alt_titles, alt_title_rules=resolved_rules.alt_titles)
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
    if any(pattern.fullmatch(value) for pattern in _build_quality_patterns(_DEFAULT_QUALITY_WHITELIST).values()):
        return False
    if any(pattern.fullmatch(value) for pattern in _build_strip_tag_patterns(_DEFAULT_STRIP_TAGS).values()):
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


def _extract_quality_tags(text: str, quality_whitelist: tuple[str, ...]) -> tuple[tuple[str, ...], str]:
    quality_tags: list[str] = []
    working_text = text
    for label, pattern in _build_quality_patterns(quality_whitelist).items():
        if pattern.search(working_text) is None:
            continue
        working_text = pattern.sub(" ", working_text)
        quality_tags.append(label)
    return tuple(quality_tags), _normalize_text(working_text)


def _strip_noise_tags(text: str, strip_tags: tuple[str, ...]) -> tuple[tuple[str, ...], str]:
    removed_tags: list[str] = []
    working_text = text
    for label, pattern in _build_strip_tag_patterns(strip_tags).items():
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


def _apply_alt_title_rules(
    *,
    title: str,
    alt_titles: tuple[str, ...],
    alt_title_rules: tuple[AltTitleRule, ...],
) -> tuple[str, ...]:
    if not title:
        return alt_titles
    normalized_seen = {_normalize_compare_key(title), *(_normalize_compare_key(item) for item in alt_titles)}
    merged_alt_titles = list(alt_titles)
    for rule in alt_title_rules:
        candidates = (rule.primary, *rule.aliases)
        if not any(_normalize_compare_key(candidate) in normalized_seen for candidate in candidates):
            continue
        for candidate in candidates:
            normalized_candidate = _normalize_compare_key(candidate)
            if not normalized_candidate or normalized_candidate == _normalize_compare_key(title):
                continue
            if normalized_candidate in normalized_seen:
                continue
            merged_alt_titles.append(candidate)
            normalized_seen.add(normalized_candidate)
    return tuple(merged_alt_titles)


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


def _normalize_compare_key(value: str) -> str:
    normalized = _normalize_text(value)
    normalized = re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", " ", normalized)
    return normalized.casefold().strip()


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


def _build_strip_tag_patterns(strip_tags: tuple[str, ...]) -> dict[str, re.Pattern[str]]:
    patterns: dict[str, re.Pattern[str]] = {}
    for tag in strip_tags:
        cleaned_tag = _clean_phrase(tag)
        if not cleaned_tag or cleaned_tag in patterns:
            continue
        patterns[cleaned_tag] = _build_keyword_pattern(cleaned_tag)
    return patterns


def _build_quality_patterns(quality_whitelist: tuple[str, ...]) -> dict[str, re.Pattern[str]]:
    patterns: dict[str, re.Pattern[str]] = {}
    for label in quality_whitelist:
        cleaned_label = _clean_phrase(label)
        if not cleaned_label or cleaned_label in patterns:
            continue
        patterns[cleaned_label] = _build_keyword_pattern(cleaned_label)
    return patterns


def _build_keyword_pattern(value: str) -> re.Pattern[str]:
    pieces = [re.escape(piece) for piece in re.split(r"[-_. ]+", value) if piece]
    body = r"[-_. ]?".join(pieces) if pieces else re.escape(value)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", flags=re.IGNORECASE)


def _parse_naming_rules_yaml(text: str) -> NamingRules:
    strip_tags: list[str] = []
    quality_whitelist: list[str] = []
    alt_titles: list[AltTitleRule] = []
    current_section = ""
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        if not line.startswith(" "):
            if not stripped.endswith(":"):
                raise ValueError(f"top-level section malformed: {stripped}")
            current_section = stripped[:-1]
            if current_section not in {"strip_tags", "quality_whitelist", "alt_titles"}:
                raise ValueError(f"unsupported section: {current_section}")
            index += 1
            continue

        if current_section in {"strip_tags", "quality_whitelist"}:
            if not line.startswith("  - "):
                raise ValueError(f"list item malformed under {current_section}: {stripped}")
            value = _parse_yaml_scalar(stripped[2:].strip())
            target = strip_tags if current_section == "strip_tags" else quality_whitelist
            target.append(value)
            index += 1
            continue

        if current_section == "alt_titles":
            if not line.startswith("  - "):
                raise ValueError(f"alt_titles item malformed: {stripped}")
            item = stripped[2:].strip()
            if not item.startswith("primary:"):
                raise ValueError(f"alt_titles primary missing: {stripped}")
            primary = _parse_yaml_scalar(item.partition(":")[2].strip())
            aliases: list[str] = []
            index += 1
            while index < len(lines):
                nested_line = lines[index]
                nested_stripped = nested_line.strip()
                if not nested_stripped or nested_stripped.startswith("#"):
                    index += 1
                    continue
                if not nested_line.startswith("    "):
                    break
                if nested_stripped.startswith("aliases:"):
                    alias_body = nested_stripped.partition(":")[2].strip()
                    if alias_body:
                        aliases.extend(_parse_inline_yaml_list(alias_body))
                        index += 1
                        continue
                    index += 1
                    while index < len(lines):
                        alias_line = lines[index]
                        alias_stripped = alias_line.strip()
                        if not alias_stripped or alias_stripped.startswith("#"):
                            index += 1
                            continue
                        if not alias_line.startswith("      - "):
                            break
                        aliases.append(_parse_yaml_scalar(alias_stripped[2:].strip()))
                        index += 1
                    continue
                raise ValueError(f"unsupported alt_titles field: {nested_stripped}")
            alt_titles.append(AltTitleRule(primary=primary, aliases=tuple(aliases)))
            continue

        raise ValueError(f"content outside supported section: {stripped}")

    return NamingRules(
        strip_tags=tuple(strip_tags or _DEFAULT_STRIP_TAGS),
        quality_whitelist=tuple(quality_whitelist or _DEFAULT_QUALITY_WHITELIST),
        alt_titles=tuple(alt_titles),
    )


def _parse_yaml_scalar(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("empty scalar is not allowed")
    if cleaned[0] in {"'", '"'} and cleaned[-1] == cleaned[0]:
        return str(ast.literal_eval(cleaned))
    return cleaned


def _parse_inline_yaml_list(value: str) -> list[str]:
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError) as error:
        raise ValueError(f"inline list malformed: {value}") from error
    if not isinstance(parsed, list):
        raise ValueError(f"inline list malformed: {value}")
    result: list[str] = []
    for item in parsed:
        if not isinstance(item, str):
            raise ValueError(f"inline list contains non-string: {value}")
        result.append(item)
    return result
