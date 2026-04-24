from __future__ import annotations

import math
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.search_title_normalization import BT_RESULT_TITLE_NOISE_TOKENS, compact_match_key, normalize_match_key

_INFO_HASH_PATTERN = re.compile(r"xt=urn:btih:([0-9a-z]{32,40})", re.IGNORECASE)
_NORMALIZED_TEXT_PATTERN = re.compile(r"[^0-9a-z\u4e00-\u9fff]+", re.IGNORECASE)
_LOW_QUALITY_PATTERN = re.compile(r"\b(cam|hdcam|ts|tc|telesync|telecine|screener|枪版|摄像)\b", re.IGNORECASE)
_MULTI_ITEM_PATTERNS = (
    re.compile(r"\bcomplete\b", re.IGNORECASE),
    re.compile(r"\bcollection\b", re.IGNORECASE),
    re.compile(r"\bbatch\b", re.IGNORECASE),
    re.compile(r"\bpack\b", re.IGNORECASE),
    re.compile(r"\b全集\b", re.IGNORECASE),
    re.compile(r"\b合集\b", re.IGNORECASE),
    re.compile(r"\b全季\b", re.IGNORECASE),
    re.compile(r"\b打包\b", re.IGNORECASE),
    re.compile(r"\bs\d{1,2}\s*-\s*s?\d{1,2}\b", re.IGNORECASE),
    re.compile(r"\bs\d{1,2}\b(?!\s*e\d{1,3})", re.IGNORECASE),
    re.compile(r"\be\d{1,3}\s*-\s*e?\d{1,3}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,3}\s*-\s*\d{1,3}\b", re.IGNORECASE),
)
_SERIES_EPISODE_PATTERNS = (
    re.compile(r"\bs\d{1,2}e\d{1,3}\b", re.IGNORECASE),
    re.compile(r"\bs\d{1,2}\b", re.IGNORECASE),
    re.compile(r"\bseason\s*\d{1,2}\b", re.IGNORECASE),
    re.compile(r"\bepisode\s*\d{1,3}\b", re.IGNORECASE),
)
_MOVIE_EXTRA_PATTERNS = (
    re.compile(r"\bextras?\b", re.IGNORECASE),
    re.compile(r"\bfeaturettes?\b", re.IGNORECASE),
    re.compile(r"\bbehind\s+the\s+scenes\b", re.IGNORECASE),
    re.compile(r"\bmaking\s+of\b", re.IGNORECASE),
    re.compile(r"\bdeleted\s+scenes?\b", re.IGNORECASE),
    re.compile(r"\bbonus\b", re.IGNORECASE),
)
_DEFAULT_MOVIE_SIZE_RANGE = (5 * 1024**3, 15 * 1024**3)
_DEFAULT_EPISODE_SIZE_RANGE = (1 * 1024**3, 5 * 1024**3)
_TITLE_RELEVANCE_STOPWORDS = BT_RESULT_TITLE_NOISE_TOKENS


@dataclass(frozen=True, slots=True)
class BTCandidate:
    source_site: str
    title: str
    magnet_or_torrent_url: str
    size_bytes: int | None
    seeders: int | None
    leechers: int | None
    resolution: str | None
    codec: str | None
    source_type: str | None
    audio: tuple[str, ...]
    release_group: str | None
    age_days: int | None
    media_kind: str


@dataclass(frozen=True, slots=True)
class BTScoringContext:
    query: str
    media_kind: str
    single_item_mode: bool = False
    seen_info_hashes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: BTCandidate
    score: float
    score_breakdown: dict[str, float]
    drop_reason: str | None


@dataclass(frozen=True, slots=True)
class BTScoringRules:
    weights: dict[str, float]
    resolution_scores: dict[str | None, float]
    source_type_scores: dict[str | None, float]
    codec_scores: dict[str | None, float]
    source_site_preferred: tuple[str, ...] = ()
    release_group_preferred: tuple[str, ...] = ()


DEFAULT_BT_SCORING_RULES = BTScoringRules(
    weights={
        "title_relevance": 8.0,
        "source_site": 1.25,
        "source_type": 3.0,
        "resolution": 2.5,
        "seeders": 1.0,
        "size_fit": 1.5,
        "codec": 0.75,
        "release_group": 0.5,
    },
    resolution_scores={
        "2160p": 1.0,
        "1080p": 0.8,
        "720p": 0.4,
        None: 0.2,
    },
    source_type_scores={
        "Remux": 1.0,
        "BluRay": 0.9,
        "BDRip": 0.8,
        "WEB-DL": 0.7,
        "WEBRip": 0.5,
        None: 0.3,
    },
    codec_scores={
        "x265": 0.9,
        "HEVC": 0.9,
        "x264": 0.8,
        None: 0.4,
    },
    source_site_preferred=("PTP", "BTN", "PTerClub", "HDBits", "MTV"),
    release_group_preferred=("VCB-Studio", "SweetSub", "CHD", "WiKi", "FRDS"),
)
DEFAULT_BT_SCORING_RULES_PATH = Path(__file__).with_name("bt_scoring_rules.yml")
_SOURCE_SITE_PREFERRED_ENV_KEY = "BT_SOURCE_SITE_PREFERRED"
_SOURCE_SITE_ALIASES = {
    "ptp": "ptp",
    "passthepopcorn": "ptp",
    "btn": "btn",
    "broadcasthe.net": "btn",
    "broadcasthetnet": "btn",
    "broadcasthetnetwork": "btn",
    "bhd": "bhd",
    "beyondhd": "bhd",
    "pter": "pterclub",
    "pterclub": "pterclub",
    "hdb": "hdbits",
    "hdbits": "hdbits",
    "mtv": "mtv",
}


def load_bt_scoring_rules(path: Path | None = None, *, environ: Mapping[str, str] | None = None) -> BTScoringRules:
    resolved_path = path or DEFAULT_BT_SCORING_RULES_PATH
    try:
        raw_text = resolved_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _log_bt_scoring_rules_warning(path=resolved_path, reason="规则文件缺失，继续使用内置规则。")
        return DEFAULT_BT_SCORING_RULES

    try:
        raw_data = _parse_rules_yaml(raw_text)
        rules, warnings = _build_rules_from_data(raw_data)
    except ValueError as error:
        _log_bt_scoring_rules_warning(path=resolved_path, reason=f"规则文件解析失败：{error}；继续使用内置规则。")
        return DEFAULT_BT_SCORING_RULES

    if warnings:
        _log_bt_scoring_rules_warning(path=resolved_path, reason="；".join(warnings))
    return _apply_source_site_env_override(rules, environ=os.environ if environ is None else environ)


def filter_candidates(
    candidates: Sequence[BTCandidate],
    context: BTScoringContext,
    *,
    rules: BTScoringRules = DEFAULT_BT_SCORING_RULES,
) -> list[ScoredCandidate]:
    seen_info_hashes = {info_hash.strip().lower() for info_hash in context.seen_info_hashes if info_hash.strip()}
    scored_items: list[tuple[int, ScoredCandidate]] = []
    for index, candidate in enumerate(candidates):
        drop_reason = _resolve_drop_reason(candidate=candidate, context=context, seen_info_hashes=seen_info_hashes)
        if drop_reason is None:
            info_hash = _extract_info_hash(candidate.magnet_or_torrent_url)
            if info_hash:
                seen_info_hashes.add(info_hash)
            score_breakdown = _build_score_breakdown(candidate=candidate, context=context, rules=rules)
            score = sum(score_breakdown[name] * rules.weights[name] for name in rules.weights)
        else:
            score_breakdown = {}
            score = 0.0
        scored_items.append(
            (
                index,
                ScoredCandidate(
                    candidate=candidate,
                    score=score,
                    score_breakdown=score_breakdown,
                    drop_reason=drop_reason,
                ),
            )
        )
    ranked_items = sorted(
        scored_items,
        key=lambda item: (item[1].drop_reason is None, item[1].score, -item[0]),
        reverse=True,
    )
    return [item[1] for item in ranked_items]


def pick_best(
    candidates: Sequence[BTCandidate],
    context: BTScoringContext,
    *,
    rules: BTScoringRules = DEFAULT_BT_SCORING_RULES,
) -> ScoredCandidate | None:
    for scored_candidate in filter_candidates(candidates, context, rules=rules):
        if scored_candidate.drop_reason is None:
            return scored_candidate
    return None


def _parse_rules_yaml(text: str) -> dict[str, object]:
    parsed: dict[str, object] = {}
    current_key: str | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent == 0:
            if not stripped.endswith(":"):
                raise ValueError(f"第 {line_number} 行缺少段落冒号")
            current_key = _parse_yaml_key(stripped[:-1].strip(), line_number=line_number)
            parsed[current_key] = parsed.get(current_key, None)
            continue
        if indent != 2 or current_key is None:
            raise ValueError(f"第 {line_number} 行缩进不合法")
        if stripped.startswith("- "):
            bucket = parsed.get(current_key)
            if bucket is None:
                bucket = []
                parsed[current_key] = bucket
            if not isinstance(bucket, list):
                raise ValueError(f"第 {line_number} 行与上一段类型冲突")
            bucket.append(_parse_yaml_scalar(stripped[2:].strip()))
            continue
        if ":" not in stripped:
            raise ValueError(f"第 {line_number} 行缺少键值分隔符")
        child_key_text, _, child_value_text = stripped.partition(":")
        bucket = parsed.get(current_key)
        if bucket is None:
            bucket = {}
            parsed[current_key] = bucket
        if not isinstance(bucket, dict):
            raise ValueError(f"第 {line_number} 行与上一段类型冲突")
        child_key = _parse_yaml_mapping_key(child_key_text.strip())
        child_value = _parse_yaml_scalar(child_value_text.strip())
        bucket[child_key] = child_value
    return parsed


def _build_rules_from_data(raw_data: dict[str, object]) -> tuple[BTScoringRules, list[str]]:
    warnings: list[str] = []
    weights = dict(DEFAULT_BT_SCORING_RULES.weights)
    resolution_scores = dict(DEFAULT_BT_SCORING_RULES.resolution_scores)
    source_type_scores = dict(DEFAULT_BT_SCORING_RULES.source_type_scores)
    codec_scores = dict(DEFAULT_BT_SCORING_RULES.codec_scores)
    source_site_preferred = list(DEFAULT_BT_SCORING_RULES.source_site_preferred)
    release_group_preferred = list(DEFAULT_BT_SCORING_RULES.release_group_preferred)

    weights, weight_warnings = _merge_score_mapping(
        raw_data=raw_data,
        section_name="weights",
        default_values=weights,
        allow_null_key=False,
    )
    warnings.extend(weight_warnings)
    resolution_scores, resolution_warnings = _merge_score_mapping(
        raw_data=raw_data,
        section_name="resolution_scores",
        default_values=resolution_scores,
        allow_null_key=True,
    )
    warnings.extend(resolution_warnings)
    source_type_scores, source_type_warnings = _merge_score_mapping(
        raw_data=raw_data,
        section_name="source_type_scores",
        default_values=source_type_scores,
        allow_null_key=True,
    )
    warnings.extend(source_type_warnings)
    codec_scores, codec_warnings = _merge_score_mapping(
        raw_data=raw_data,
        section_name="codec_scores",
        default_values=codec_scores,
        allow_null_key=True,
    )
    warnings.extend(codec_warnings)

    source_site_raw = raw_data.get("source_site_preferred")
    if source_site_raw is None:
        warnings.append("source_site_preferred 缺失，继续使用内置默认值")
    elif not isinstance(source_site_raw, list):
        warnings.append("source_site_preferred 不是列表，继续使用内置默认值")
    else:
        source_site_preferred = [str(item).strip() for item in source_site_raw if str(item).strip()]
        if not source_site_preferred:
            warnings.append("source_site_preferred 为空，继续使用内置默认值")
            source_site_preferred = list(DEFAULT_BT_SCORING_RULES.source_site_preferred)

    release_group_raw = raw_data.get("release_group_preferred")
    if release_group_raw is None:
        warnings.append("release_group_preferred 缺失，继续使用内置默认值")
    elif not isinstance(release_group_raw, list):
        warnings.append("release_group_preferred 不是列表，继续使用内置默认值")
    else:
        release_group_preferred = [str(item).strip() for item in release_group_raw if str(item).strip()]
        if not release_group_preferred:
            warnings.append("release_group_preferred 为空，继续使用内置默认值")
            release_group_preferred = list(DEFAULT_BT_SCORING_RULES.release_group_preferred)

    return (
        BTScoringRules(
            weights=weights,
            resolution_scores=resolution_scores,
            source_type_scores=source_type_scores,
            codec_scores=codec_scores,
            source_site_preferred=tuple(source_site_preferred),
            release_group_preferred=tuple(release_group_preferred),
        ),
        warnings,
    )


def _merge_score_mapping(
    *,
    raw_data: dict[str, object],
    section_name: str,
    default_values: dict[str | None, float],
    allow_null_key: bool,
) -> tuple[dict[str | None, float], list[str]]:
    warnings: list[str] = []
    merged_values = dict(default_values)
    section = raw_data.get(section_name)
    if section is None:
        warnings.append(f"{section_name} 缺失，继续使用内置默认值")
        return merged_values, warnings
    if not isinstance(section, dict):
        warnings.append(f"{section_name} 不是映射，继续使用内置默认值")
        return merged_values, warnings

    for key, value in section.items():
        if key is None and not allow_null_key:
            warnings.append(f"{section_name} 包含 null key，已忽略")
            continue
        if key is not None and not isinstance(key, str):
            warnings.append(f"{section_name} 包含非法 key，已忽略")
            continue
        if not isinstance(value, (int, float)):
            warnings.append(f"{section_name}.{key} 不是数字，已忽略")
            continue
        merged_values[key] = float(value)
    return merged_values, warnings


def _parse_yaml_key(text: str, *, line_number: int) -> str:
    key = _parse_yaml_scalar(text)
    if not isinstance(key, str) or not key:
        raise ValueError(f"第 {line_number} 行段落名非法")
    return key


def _parse_yaml_mapping_key(text: str) -> str | None:
    key = _parse_yaml_scalar(text)
    if key is None:
        return None
    return str(key)


def _parse_yaml_scalar(text: str) -> str | float | None:
    if not text:
        return ""
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    lowered_text = text.lower()
    if lowered_text == "null":
        return None
    try:
        return float(text)
    except ValueError:
        return text


def _log_bt_scoring_rules_warning(*, path: Path, reason: str) -> None:
    print(
        f"\033[33m[BT 评分规则文件回退]\033[0m 文件={path} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 YAML 键名、缩进和数值格式；修正后重新运行相关 BT 评分测试。"
    )


def _resolve_drop_reason(
    *,
    candidate: BTCandidate,
    context: BTScoringContext,
    seen_info_hashes: set[str],
) -> str | None:
    if not _looks_like_valid_download_source(candidate.magnet_or_torrent_url):
        return "invalid_source"
    if not _title_matches_query(candidate.title, context.query):
        return "title_mismatch"
    if context.media_kind == "movie" and _looks_like_series_episode_release(candidate.title):
        return "title_mismatch"
    if context.media_kind == "movie" and _looks_like_movie_extra_release(candidate.title):
        return "title_mismatch"
    info_hash = _extract_info_hash(candidate.magnet_or_torrent_url)
    if info_hash and info_hash in seen_info_hashes:
        return "duplicate_info_hash"
    if _is_low_quality_title(candidate.title):
        return "low_quality_title"
    if context.single_item_mode and _looks_like_multi_item_release(candidate.title):
        return "multi_item_release"
    return None


def _build_score_breakdown(
    *,
    candidate: BTCandidate,
    context: BTScoringContext,
    rules: BTScoringRules,
) -> dict[str, float]:
    return {
        "title_relevance": _score_title_relevance(candidate.title, context.query),
        "source_site": _score_source_site(candidate.source_site, rules.source_site_preferred),
        "resolution": _score_lookup(candidate.resolution, rules.resolution_scores),
        "source_type": _score_lookup(candidate.source_type, rules.source_type_scores),
        "seeders": _score_seeders(candidate.seeders),
        "size_fit": _score_size_fit(candidate=candidate, context=context),
        "codec": _score_lookup(candidate.codec, rules.codec_scores),
        "release_group": _score_release_group(candidate.release_group, rules.release_group_preferred),
    }


def _score_lookup(value: str | None, score_map: dict[str | None, float]) -> float:
    return score_map.get(value, score_map.get(None, 0.0))


def _score_seeders(seeders: int | None) -> float:
    if seeders is None or seeders <= 0:
        return 0.0
    if seeders >= 50:
        return 1.0
    if seeders >= 20:
        return 0.8
    if seeders >= 5:
        return 0.5
    return 0.2


def _score_size_fit(*, candidate: BTCandidate, context: BTScoringContext) -> float:
    size_bytes = candidate.size_bytes
    if size_bytes is None or size_bytes <= 0:
        return 0.0
    expected_range = _expected_size_range(context)
    if expected_range is None:
        return 0.5
    expected_min, expected_max = expected_range
    if expected_min <= size_bytes <= expected_max:
        return 1.0
    if size_bytes < expected_min:
        return max(0.0, min(1.0, size_bytes / expected_min))
    return max(0.0, min(1.0, expected_max / size_bytes))


def _expected_size_range(context: BTScoringContext) -> tuple[int, int] | None:
    if context.media_kind == "movie":
        return _DEFAULT_MOVIE_SIZE_RANGE
    if context.media_kind in {"series", "anime"}:
        return _DEFAULT_EPISODE_SIZE_RANGE
    if context.media_kind == "raw_bt" and context.single_item_mode:
        return _DEFAULT_EPISODE_SIZE_RANGE
    return None


def _score_release_group(release_group: str | None, preferred_groups: tuple[str, ...]) -> float:
    if not release_group:
        return 0.0
    if release_group in preferred_groups:
        return 1.0
    return 0.2


def _score_source_site(source_site: str | None, preferred_sites: tuple[str, ...]) -> float:
    if not source_site:
        return 0.0
    normalized_source_site = _normalize_source_site_key(source_site)
    if not normalized_source_site:
        return 0.0
    normalized_preferred_sites = [_normalize_source_site_key(site) for site in preferred_sites if site.strip()]
    if normalized_source_site in normalized_preferred_sites:
        return 1.0
    return 0.2


def _apply_source_site_env_override(
    rules: BTScoringRules,
    *,
    environ: Mapping[str, str],
) -> BTScoringRules:
    raw_value = str(environ.get(_SOURCE_SITE_PREFERRED_ENV_KEY, "")).strip()
    if not raw_value:
        return rules
    preferred_sites = tuple(site.strip() for site in raw_value.replace(";", ",").split(",") if site.strip())
    if not preferred_sites:
        return rules
    return BTScoringRules(
        weights=dict(rules.weights),
        resolution_scores=dict(rules.resolution_scores),
        source_type_scores=dict(rules.source_type_scores),
        codec_scores=dict(rules.codec_scores),
        source_site_preferred=preferred_sites,
        release_group_preferred=tuple(rules.release_group_preferred),
    )


def _normalize_source_site_key(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9.]+", "", value.strip().lower())
    if not collapsed:
        return ""
    return _SOURCE_SITE_ALIASES.get(collapsed, collapsed)


def _looks_like_valid_download_source(source: str) -> bool:
    cleaned_source = source.strip()
    if not cleaned_source:
        return False
    lowered_source = cleaned_source.lower()
    return lowered_source.startswith("magnet:?") or lowered_source.startswith("http://") or lowered_source.startswith(
        "https://"
    )


def _title_matches_query(title: str, query: str) -> bool:
    normalized_query = _normalize_title_for_relevance(query)
    if not normalized_query:
        return True
    normalized_title = _normalize_title_for_relevance(title)
    if not normalized_title:
        return False
    if normalized_query in normalized_title:
        return True
    if compact_match_key(normalized_title) == compact_match_key(normalized_query):
        return True

    query_tokens = [token for token in normalized_query.split() if token]
    if not query_tokens:
        return True
    title_tokens = set(normalized_title.split())
    matched_count = sum(1 for token in query_tokens if token in title_tokens)
    required_count = max(1, math.ceil(len(query_tokens) * 0.8))
    return matched_count >= required_count


def _score_title_relevance(title: str, query: str) -> float:
    normalized_query_title = _normalize_title_for_relevance(query)
    normalized_candidate_title = _normalize_title_for_relevance(title)
    if not normalized_query_title or not normalized_candidate_title:
        return 0.0
    if normalized_candidate_title == normalized_query_title:
        surface_query_title = _normalize_surface_title_for_relevance(query)
        surface_candidate_title = _normalize_surface_title_for_relevance(title)
        if compact_match_key(surface_candidate_title) == compact_match_key(surface_query_title):
            return 1.0
        return 0.9
    surface_query_title = _normalize_surface_title_for_relevance(query)
    surface_candidate_title = _normalize_surface_title_for_relevance(title)
    if surface_candidate_title == surface_query_title:
        return 1.0
    if normalized_candidate_title.startswith(normalized_query_title):
        return 0.2
    if normalized_query_title in normalized_candidate_title:
        return 0.1

    query_tokens = [token for token in normalized_query_title.split() if token]
    if not query_tokens:
        return 0.0
    matched_count = sum(1 for token in query_tokens if token in normalized_candidate_title)
    if matched_count <= 0:
        return 0.0
    return matched_count / len(query_tokens) * 0.5


def _normalize_title_for_relevance(value: str) -> str:
    return _normalize_title_tokens_for_relevance(value, normalizer=normalize_match_key)


def _normalize_surface_title_for_relevance(value: str) -> str:
    return _normalize_title_tokens_for_relevance(value, normalizer=_normalize_text)


def _normalize_title_tokens_for_relevance(value: str, *, normalizer: Callable[[str], str]) -> str:
    cleaned_value = re.sub(r"-[A-Za-z0-9][A-Za-z0-9-]*$", "", value.strip())
    cleaned_value = re.sub(r"\b\d\.\d\b", " ", cleaned_value, flags=re.IGNORECASE)
    normalized = normalizer(cleaned_value)
    if not normalized:
        return ""
    filtered_tokens: list[str] = []
    for token in normalized.split():
        if re.fullmatch(r"(?:19|20)\d{2}", token):
            continue
        if token in _TITLE_RELEVANCE_STOPWORDS:
            continue
        filtered_tokens.append(token)
    return " ".join(filtered_tokens).strip()


def _normalize_text(text: str) -> str:
    normalized = _NORMALIZED_TEXT_PATTERN.sub(" ", text.strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _extract_info_hash(source: str) -> str:
    matched = _INFO_HASH_PATTERN.search(source)
    if matched is None:
        return ""
    return str(matched.group(1) or "").strip().lower()


def _is_low_quality_title(title: str) -> bool:
    return _LOW_QUALITY_PATTERN.search(title.strip()) is not None


def _looks_like_multi_item_release(title: str) -> bool:
    cleaned_title = title.strip()
    if not cleaned_title:
        return False
    return any(pattern.search(cleaned_title) is not None for pattern in _MULTI_ITEM_PATTERNS)


def _looks_like_series_episode_release(title: str) -> bool:
    cleaned_title = title.strip()
    if not cleaned_title:
        return False
    return any(pattern.search(cleaned_title) is not None for pattern in _SERIES_EPISODE_PATTERNS)


def _looks_like_movie_extra_release(title: str) -> bool:
    cleaned_title = title.strip()
    if not cleaned_title:
        return False
    return any(pattern.search(cleaned_title) is not None for pattern in _MOVIE_EXTRA_PATTERNS)
