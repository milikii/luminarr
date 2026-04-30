from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.clients.tmdb import TmdbMovie
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_delivery_item
from app.search_title_normalization import compact_match_key, normalize_match_key, normalize_spaces
from app.services.search_query_parser import ParsedMovieQuery

NO_RESULT_TEXT_TEMPLATE = "未找到候选结果：{query}"
BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE = "BT 只读探索未找到候选：{query}"
ADULT_BT_SOURCE_EMPTY_TEXT_TEMPLATE = "当前已配置成人源无结果：{query}"
BT_READ_ONLY_NOTICE_TEXT = (
    "只读说明：当前结果仅供手动 BT 探索和站点规则排查参考，不会创建审批或下载任务。\n"
    "如需走成人下载链，请直接发送磁力并选择 BT 成人链。"
)
ADULT_BT_RESOURCE_FALLBACK_NOTICE_TEXT = (
    "只读说明：以上为当前已配置成人源返回的资源候选，不会创建审批或下载任务。\n"
    "如需走成人下载链，请直接发送磁力并选择 BT 成人链。"
)
BT_BATCH_PREVIEW_NO_RESULT_TEXT_TEMPLATE = "BT 批量预览未找到候选：{query}"
BT_BATCH_PREVIEW_NOTICE_TEMPLATE = (
    "只读说明：当前批量预览只用于确认候选范围，不会创建审批或下载任务。\n"
    "当前预览范围：{selection}"
)


@dataclass(frozen=True, slots=True)
class Candidate:
    title: str
    year: str
    quality: str
    size: str
    indexer: str


def normalize_candidate(item: Mapping[str, Any]) -> Candidate:
    title = safe_text(item.get("title"), default="(no title)")
    year = safe_year(item.get("year"))
    quality = safe_text(item.get("quality"), default="-")
    if quality == "-" and "resolution" in item:
        quality = safe_text(item.get("resolution"), default="-")
    if quality == "-":
        quality = guess_quality_from_title(title)
    size = format_size(item.get("size"))
    indexer = safe_indexer(item.get("indexer"), item.get("indexerName"))
    return Candidate(title=title, year=year, quality=quality, size=size, indexer=indexer)


def format_movie_query_reply(
    query: str,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
    candidates: Sequence[Candidate],
) -> str:
    candidates_text = format_candidates(query, candidates)
    if not candidates:
        return candidates_text
    card_text = format_movie_poster_card(parsed_query, tmdb_movie)
    return f"{card_text}\n\n{candidates_text}"


def render_search_results_reply(
    *,
    query: str,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
    candidates: Sequence[Candidate],
    channel: str,
) -> str:
    item = build_search_results_delivery_item(
        query=query,
        parsed_query=parsed_query,
        tmdb_movie=tmdb_movie,
        candidates=candidates,
    )
    return render_delivery_item(item, channel=channel)


def format_bt_read_only_reply(query: str, candidates: Sequence[Mapping[str, Any]]) -> str:
    if not candidates:
        return BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE.format(query=query)

    lines = [f"BT 只读探索结果：{query}"]
    _append_bt_candidate_lines(lines, candidates)
    lines.append(BT_READ_ONLY_NOTICE_TEXT)
    return "\n".join(lines)


def format_adult_bt_resource_fallback_reply(query: str, candidates: Sequence[Mapping[str, Any]]) -> str:
    if not candidates:
        return ADULT_BT_SOURCE_EMPTY_TEXT_TEMPLATE.format(query=query)

    lines = [f"成人资源候选：{query}"]
    _append_bt_candidate_lines(lines, candidates)
    lines.append(ADULT_BT_RESOURCE_FALLBACK_NOTICE_TEXT)
    return "\n".join(lines)


def _append_bt_candidate_lines(lines: list[str], candidates: Sequence[Mapping[str, Any]]) -> None:
    seen_history_content_ids: set[str] = set()
    for index, item in enumerate(candidates, start=1):
        title = safe_text(item.get("title"), default="(no title)")
        indexer = safe_indexer(item.get("indexer"), item.get("indexerName"))
        provider = safe_text(item.get("sourceProvider"), default=indexer)
        seeders = format_seeder_count(item.get("seeders"))
        size = format_size(item.get("size"))
        lines.append(f"{index}. {title}")
        lines.append(f"   站点: {indexer} | 来源入口: {provider} | 做种: {seeders} | 大小: {size}")
        adult_summary = format_adult_candidate_summary(item)
        if adult_summary:
            lines.append(f"   {adult_summary}")
        helper_summary = format_read_only_adult_helper_summary(item)
        if helper_summary:
            lines.append(f"   {helper_summary}")
        helper_title = format_read_only_adult_helper_title(item)
        if helper_title:
            lines.append(f"   {helper_title}")
        detail_url = format_read_only_adult_detail_url(item)
        if detail_url:
            lines.append(f"   只读详情: {detail_url}")
        history_text = resolve_read_only_history_text(item, seen_content_ids=seen_history_content_ids)
        if history_text:
            lines.append(f"   {history_text}")
        lines.append(f"   链接参考: {format_bt_source_reference(item)}")


def format_bt_batch_preview_reply(
    query: str,
    candidates: Sequence[Mapping[str, Any]],
    *,
    selection_label: str,
) -> str:
    if not candidates:
        return BT_BATCH_PREVIEW_NO_RESULT_TEXT_TEMPLATE.format(query=query)

    lines = [f"BT 批量预览结果：{query}"]
    _append_bt_candidate_lines(lines, candidates)
    lines.append(BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection=selection_label))
    return "\n".join(lines)


def format_bt_batch_preview_selection_label(selected_indexes: Sequence[int]) -> str:
    if not selected_indexes:
        return "-"
    return ",".join(str(index) for index in selected_indexes)


def format_adult_candidate_summary(item: Mapping[str, Any]) -> str:
    content_id = safe_text(item.get("adult_display_id"), default="")
    category = safe_text(item.get("adult_archive_category"), default="")
    if not content_id and not category:
        return ""
    if content_id and category:
        return f"番号: {content_id} | 分类: {category}"
    if content_id:
        return f"番号: {content_id}"
    return f"分类: {category}"


def format_read_only_adult_helper_summary(item: Mapping[str, Any]) -> str:
    if safe_text(item.get("adult_display_id"), default=""):
        return ""
    provider = safe_text(item.get("read_only_adult_source_site"), default="")
    content_id = safe_text(item.get("read_only_adult_display_id"), default="")
    category = safe_text(item.get("read_only_adult_archive_category"), default="")
    if not provider and not content_id and not category:
        return ""

    provider_label = provider or "helper"
    if content_id and category:
        return f"只读补全: {provider_label} | 番号: {content_id} | 分类: {category}"
    if content_id:
        return f"只读补全: {provider_label} | 番号: {content_id}"
    if category:
        return f"只读补全: {provider_label} | 分类: {category}"
    return f"只读补全: {provider_label}"


def format_read_only_adult_helper_title(item: Mapping[str, Any]) -> str:
    if safe_text(item.get("adult_display_id"), default=""):
        return ""
    helper_title = safe_text(item.get("read_only_adult_title"), default="")
    candidate_title = safe_text(item.get("title"), default="")
    if not helper_title:
        return ""
    if helper_title == candidate_title:
        return ""
    helper_title_key = compact_match_key(normalize_match_key(helper_title))
    candidate_title_key = compact_match_key(normalize_match_key(candidate_title))
    if helper_title_key and helper_title_key == candidate_title_key:
        return ""
    return f"只读标题: {helper_title}"


def format_read_only_adult_detail_url(item: Mapping[str, Any]) -> str:
    return safe_text(item.get("read_only_adult_detail_url"), default="")


def resolve_read_only_history_text(item: Mapping[str, Any], *, seen_content_ids: set[str]) -> str:
    history_text = safe_text(item.get("adult_history_text"), default="")
    if not history_text:
        return ""
    content_id = safe_text(item.get("adult_content_id"), default="") or safe_text(
        item.get("read_only_adult_content_id"),
        default="",
    )
    if not content_id:
        return history_text
    if content_id in seen_content_ids:
        return ""
    seen_content_ids.add(content_id)
    return history_text


def safe_text(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text


def safe_year(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    return text


def safe_indexer(indexer_value: Any, indexer_name_value: Any) -> str:
    if isinstance(indexer_value, Mapping):
        mapped_name = safe_text(indexer_value.get("name"), default="-")
        if mapped_name != "-":
            return mapped_name

    name = safe_text(indexer_name_value, default="-")
    if name != "-":
        return name
    return safe_text(indexer_value, default="-")


def format_size(size_value: Any) -> str:
    if size_value is None:
        return "-"

    try:
        bytes_value = int(size_value)
    except (TypeError, ValueError):
        return "-"

    if bytes_value <= 0:
        return "-"

    units = ("B", "KB", "MB", "GB", "TB")
    size = float(bytes_value)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def format_seeder_count(value: Any) -> str:
    if value is None:
        return "-"
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return "-"
    if resolved < 0:
        return "-"
    return str(resolved)


def format_bt_source_reference(item: Mapping[str, Any]) -> str:
    source = safe_text(item.get("source"), default="-")
    if source == "-":
        return source

    info_hash = safe_text(item.get("infoHash"), default="")
    if source.lower().startswith("magnet:?"):
        if info_hash:
            return f"magnet | infoHash={info_hash}"
        return truncate_text(source, limit=96)

    return truncate_text(source, limit=96)


def format_candidates(query: str, candidates: Sequence[Candidate]) -> str:
    if not candidates:
        return NO_RESULT_TEXT_TEMPLATE.format(query=query)

    lines = [f"搜索结果：{query}"]
    for index, item in enumerate(candidates, start=1):
        lines.append(f"{index}. {item.title} ({item.year})")
        lines.append(f"   画质: {item.quality} | 大小: {item.size} | 站点: {item.indexer}")
    return "\n".join(lines)


def format_movie_poster_card(parsed_query: ParsedMovieQuery, tmdb_movie: TmdbMovie | None) -> str:
    card_title, card_year, card_alias = resolve_movie_card_fields(parsed_query, tmdb_movie)
    lines = [
        "电影海报卡片",
        f"片名: {card_title}",
        f"年份: {card_year}",
        f"别名: {card_alias}",
        "海报: 暂未接入图片",
    ]
    return "\n".join(lines)


def resolve_movie_card_fields(parsed_query: ParsedMovieQuery, tmdb_movie: TmdbMovie | None) -> tuple[str, str, str]:
    card_title = parsed_query.title or "-"
    card_year = parsed_query.year.strip() or "-"
    card_alias = "-"

    if tmdb_movie is not None:
        original_title = normalize_spaces(tmdb_movie.original_title)
        english_title = normalize_spaces(tmdb_movie.title)
        if original_title:
            card_title = original_title
        elif english_title:
            card_title = english_title

        resolved_year = tmdb_movie.year.strip()
        if resolved_year:
            card_year = resolved_year

        if english_title and english_title != card_title:
            card_alias = english_title
    return card_title, card_year, card_alias


def build_search_results_delivery_item(
    *,
    query: str,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
    candidates: Sequence[Candidate],
) -> DeliveryItem:
    if not candidates:
        raise ValueError("search results delivery requires at least one candidate")
    card_title, card_year, card_alias = resolve_movie_card_fields(parsed_query, tmdb_movie)
    candidate_lines: list[str] = []
    for index, item in enumerate(candidates, start=1):
        candidate_lines.append(f"{index}. {item.title} ({item.year})")
        candidate_lines.append(f"画质：{item.quality} ｜ 大小：{item.size} ｜ 站点：{item.indexer}")
    return DeliveryItem(
        header=DeliveryHeader(kind="search_results", title=f"搜索：{query}", subtitle=f"候选结果（{len(candidates)} 条）"),
        sections=(
            DeliverySection(
                label="电影信息",
                lines=(
                    f"片名：{card_title}",
                    f"年份：{card_year}",
                    f"别名：{card_alias}",
                    "海报：暂未接入图片",
                ),
            ),
            DeliverySection(label="候选结果", lines=tuple(candidate_lines)),
        ),
        actions=(
            DeliveryAction(label="开始下载", hint="发送 select 1", kind="primary"),
            DeliveryAction(label="换关键词", hint=f"发送 search {query}", kind="secondary"),
        ),
        status="success",
    )


def guess_quality_from_title(title: str) -> str:
    resolution_match = re.search(r"\b(2160p|1080p|720p|480p|4k)\b", title, flags=re.IGNORECASE)
    source_match = re.search(
        r"\b(web[- ]dl|webrip|bluray|remux|hdtv|dvdrip|bdrip)\b",
        title,
        flags=re.IGNORECASE,
    )
    if not resolution_match and not source_match:
        return "-"

    resolution = "-"
    if resolution_match:
        raw_resolution = resolution_match.group(1)
        resolution = "4K" if raw_resolution.lower() == "4k" else raw_resolution.lower()

    if not source_match:
        return resolution

    source_raw = source_match.group(1).lower().replace(" ", "-")
    source_map = {
        "web-dl": "WEB-DL",
        "webrip": "WEBRip",
        "bluray": "BluRay",
        "remux": "Remux",
        "hdtv": "HDTV",
        "dvdrip": "DVDRip",
        "bdrip": "BDRip",
    }
    source = source_map.get(source_raw, source_raw.upper())
    if resolution == "-":
        return source
    return f"{resolution} {source}"


def truncate_text(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return f"{value[: limit - 3]}..."
