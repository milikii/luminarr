from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.clients.tmdb import TmdbMovie
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_delivery_item
from app.search_title_normalization import compact_match_key, normalize_match_key, normalize_spaces
from app.services.adult_metadata_sources import (
    canonicalize_adult_metadata_source_name,
    get_adult_metadata_source_profile,
)
from app.services.adult_metadata_localization import resolve_adult_localized_metadata
from app.services.bt_sources import resolve_bt_source
from app.services.search_query_parser import ParsedMovieQuery

NO_RESULT_TEXT_TEMPLATE = "未找到候选结果：{query}"
BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE = "BT 只读探索未找到候选：{query}"
ADULT_BT_SOURCE_EMPTY_TEXT_TEMPLATE = (
    "当前已配置成人源无结果：{query}\n"
    "下一步：请检查 BT_WEB_SOURCES 中的成人 BT 站点或 Prowlarr 成人索引器配置；当前不会扩大到 PT 主线搜索。"
)
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
    *,
    tmdb_candidates: Sequence[TmdbMovie] = (),
) -> str:
    candidates_text = format_candidates(query, candidates)
    if not candidates:
        return candidates_text
    card_text = format_movie_poster_card(parsed_query, tmdb_movie, tmdb_candidates=tmdb_candidates)
    return f"{card_text}\n\n{candidates_text}"


def format_media_candidate_confirmation_reply(
    query: str,
    parsed_query: ParsedMovieQuery,
    tmdb_candidates: Sequence[TmdbMovie],
) -> str:
    if not tmdb_candidates:
        return NO_RESULT_TEXT_TEMPLATE.format(query=query)
    lines = [f"候选作品：{query}"]
    for index, candidate in enumerate(tmdb_candidates[:5], start=1):
        card_title, card_year, card_media_type, card_alias, card_poster, card_overview = resolve_movie_card_fields(
            parsed_query,
            candidate,
            prefer_localized_title=True,
        )
        lines.append(f"{index}. {card_title} ({card_year}) | {card_media_type}")
        if card_poster != "暂未接入图片":
            lines.append(f"   海报: {card_poster}")
        if card_alias != "-":
            lines.append(f"   原名: {card_alias}")
        if card_overview:
            lines.append(f"   简介: {truncate_text(card_overview, limit=80)}")
    lines.append("直接回复对应序号确认作品，例如：1")
    return "\n".join(lines)


def render_search_results_reply(
    *,
    query: str,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
    candidates: Sequence[Candidate],
    channel: str,
    tmdb_candidates: Sequence[TmdbMovie] = (),
) -> str:
    item = build_search_results_delivery_item(
        query=query,
        parsed_query=parsed_query,
        tmdb_movie=tmdb_movie,
        candidates=candidates,
        tmdb_candidates=tmdb_candidates,
    )
    return render_delivery_item(item, channel=channel)


def render_media_candidate_confirmation_reply(
    *,
    query: str,
    parsed_query: ParsedMovieQuery,
    tmdb_candidates: Sequence[TmdbMovie],
    channel: str,
) -> str:
    item = build_media_candidate_confirmation_delivery_item(
        query=query,
        parsed_query=parsed_query,
        tmdb_candidates=tmdb_candidates,
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
    _append_bt_candidate_lines(lines, candidates, include_adult_metadata=True, include_source_link=True)
    lines.append(ADULT_BT_RESOURCE_FALLBACK_NOTICE_TEXT)
    return "\n".join(lines)


def _append_bt_candidate_lines(
    lines: list[str],
    candidates: Sequence[Mapping[str, Any]],
    *,
    include_adult_metadata: bool = False,
    include_source_link: bool = False,
) -> None:
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
        if include_adult_metadata:
            for metadata_line in format_adult_metadata_lines(item):
                lines.append(f"   {metadata_line}")
        if include_source_link:
            source_link = format_bt_direct_source_link(item)
            if source_link:
                lines.append(f"   {source_link}")
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


def format_adult_metadata_lines(item: Mapping[str, Any]) -> tuple[str, ...]:
    lines: list[str] = []
    poster_url = _first_text(
        item,
        (
            "adult_poster_url",
            "posterUrl",
            "poster_url",
            "coverUrl",
            "cover_url",
            "thumbnail",
            "image",
            "read_only_adult_poster_url",
        ),
    )
    if poster_url:
        lines.append(f"海报: {poster_url}")

    standard_summary = format_adult_standard_metadata_summary(item)
    if standard_summary:
        lines.append(f"标准信息: {standard_summary}")

    overview_summary = format_adult_overview_metadata_summary(item)
    if overview_summary:
        lines.append(f"简介: {overview_summary}")

    production_summary = format_adult_production_metadata_summary(item)
    if production_summary:
        lines.append(f"制作信息: {production_summary}")

    metadata_source_summary = format_adult_metadata_source_summary(item)
    if metadata_source_summary:
        lines.append(metadata_source_summary)
    return tuple(lines)


def format_adult_standard_metadata_summary(item: Mapping[str, Any]) -> str:
    localized_metadata = resolve_adult_localized_metadata(item)
    title = localized_metadata.title.value or _first_text(item, ("adult_title", "metadataTitle", "metadata_title", "read_only_adult_title", "title"))
    release_date = _first_text(
        item,
        ("adult_release_date", "releaseDate", "release_date", "date", "read_only_adult_release_date"),
    )
    runtime = _first_text(
        item,
        ("adult_runtime", "runtime", "duration", "length", "read_only_adult_runtime"),
    )
    fields = []
    if title:
        fields.append(f"标题: {title}")
    if localized_metadata.title.original:
        fields.append(f"原名: {localized_metadata.title.original}")
    if release_date:
        fields.append(f"发行日: {release_date}")
    if runtime:
        fields.append(f"时长: {runtime}")
    return " | ".join(fields)


def format_adult_overview_metadata_summary(item: Mapping[str, Any]) -> str:
    localized_metadata = resolve_adult_localized_metadata(item)
    overview = localized_metadata.overview.value
    if not overview:
        return ""
    return truncate_text(overview, limit=160)


def format_adult_production_metadata_summary(item: Mapping[str, Any]) -> str:
    localized_metadata = resolve_adult_localized_metadata(item)
    maker = localized_metadata.maker.value or _first_text(
        item,
        ("adult_maker", "adult_studio", "maker", "studio", "publisher", "read_only_adult_maker", "read_only_adult_studio"),
    )
    label = localized_metadata.label.value or _first_text(item, ("adult_label", "label", "read_only_adult_label"))
    series = localized_metadata.series.value or _first_text(item, ("adult_series", "series", "read_only_adult_series"))
    director = localized_metadata.director.value or _first_text(item, ("adult_director", "director", "read_only_adult_director"))
    actors = localized_metadata.actors.value or _first_sequence_text(
        item,
        ("adult_actors", "actors", "actresses", "cast", "read_only_adult_actors"),
    )
    fields = []
    if maker:
        fields.append(f"制作商: {maker}")
    if label:
        fields.append(f"厂牌: {label}")
    if series:
        fields.append(f"系列: {series}")
    if localized_metadata.series.original:
        fields.append(f"原系列: {localized_metadata.series.original}")
    if director:
        fields.append(f"导演: {director}")
    if actors:
        fields.append(f"演员: {actors}")
    if localized_metadata.actors.original:
        fields.append(f"原演员: {localized_metadata.actors.original}")
    return " | ".join(fields)


def format_adult_metadata_source_summary(item: Mapping[str, Any]) -> str:
    direct_source = _first_text(
        item,
        (
            "adult_metadata_source",
            "metadataSource",
            "metadata_source",
            "sourceSite",
            "source_site",
        ),
    )
    read_only_source = _first_text(item, ("read_only_adult_source_site",))
    raw_source = direct_source or read_only_source
    if not raw_source:
        return ""
    source_name = canonicalize_adult_metadata_source_name(raw_source)
    source_profile = get_adult_metadata_source_profile(source_name)
    role = _first_text(item, ("adult_metadata_source_role",))
    if not role and not direct_source:
        role = _first_text(item, ("read_only_adult_metadata_source_role",))
    if not role and source_profile is not None:
        role = source_profile.role
    if role:
        return f"Metadata源: {source_name} | 角色: {role}"
    return f"Metadata源: {source_name}"


def format_bt_direct_source_link(item: Mapping[str, Any]) -> str:
    source = resolve_bt_source(item)
    if not source:
        return ""
    if source.lower().startswith("magnet:?"):
        return f"磁力链接: {source}"
    return f"资源链接: {source}"


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


def _first_text(item: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        text = safe_text(item.get(key), default="")
        if text:
            return text
    return ""


def _first_sequence_text(item: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str):
            text = safe_text(value, default="")
            if text:
                return text
            continue
        if isinstance(value, Sequence):
            parts = [safe_text(part, default="") for part in value]
            text = " / ".join(part for part in parts if part)
            if text:
                return text
            continue
        text = safe_text(value, default="")
        if text:
            return text
    return ""


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


def format_movie_poster_card(
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
    *,
    tmdb_candidates: Sequence[TmdbMovie] = (),
) -> str:
    card_title, card_year, card_media_type, card_alias, card_poster, card_overview = resolve_movie_card_fields(
        parsed_query,
        tmdb_movie,
    )
    lines = [
        "电影海报卡片",
        f"片名: {card_title}",
        f"年份: {card_year}",
        f"类型: {card_media_type}",
        f"别名: {card_alias}",
        f"海报: {card_poster}",
    ]
    if card_overview:
        lines.append(f"简介: {truncate_text(card_overview, limit=120)}")
    candidate_lines = format_tmdb_candidate_lines(tmdb_candidates)
    if candidate_lines:
        lines.append("相关作品:")
        lines.extend(candidate_lines)
    return "\n".join(lines)


def resolve_movie_card_fields(
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
    *,
    prefer_localized_title: bool = False,
) -> tuple[str, str, str, str, str, str]:
    card_title = parsed_query.title or "-"
    card_year = parsed_query.year.strip() or "-"
    card_media_type = "-"
    card_alias = "-"
    card_poster = "暂未接入图片"
    card_overview = ""

    if tmdb_movie is not None:
        original_title = normalize_spaces(tmdb_movie.original_title)
        localized_title = normalize_spaces(tmdb_movie.title)
        if prefer_localized_title:
            card_title, card_alias = _resolve_tmdb_display_titles(
                localized_title=localized_title,
                original_title=original_title,
                fallback_title=parsed_query.title,
            )
        else:
            if _contains_cjk(localized_title):
                card_title = localized_title
            elif original_title:
                card_title = original_title
            elif localized_title:
                card_title = localized_title

            if card_title == original_title and localized_title and localized_title != card_title:
                card_alias = localized_title
            elif original_title and original_title != card_title:
                card_alias = original_title

        resolved_year = tmdb_movie.year.strip()
        if resolved_year:
            card_year = resolved_year

        if tmdb_movie.media_type.strip():
            card_media_type = tmdb_movie.media_type.strip()
        card_poster = resolve_tmdb_poster_url(tmdb_movie) or card_poster
        card_overview = normalize_spaces(tmdb_movie.overview)
    return card_title, card_year, card_media_type, card_alias, card_poster, card_overview


def _resolve_tmdb_display_titles(
    *,
    localized_title: str,
    original_title: str,
    fallback_title: str,
) -> tuple[str, str]:
    resolved_localized_title = normalize_spaces(localized_title)
    resolved_original_title = normalize_spaces(original_title)
    resolved_fallback_title = normalize_spaces(fallback_title)

    if _contains_han_characters(resolved_localized_title):
        primary_title = resolved_localized_title
    elif resolved_localized_title:
        primary_title = resolved_localized_title
    elif resolved_original_title:
        primary_title = resolved_original_title
    elif resolved_fallback_title:
        primary_title = resolved_fallback_title
    else:
        primary_title = "-"

    if resolved_original_title and resolved_original_title != primary_title:
        return primary_title, resolved_original_title
    return primary_title, "-"


def _contains_han_characters(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", value))


def resolve_tmdb_poster_url(tmdb_movie: TmdbMovie) -> str:
    poster_path = tmdb_movie.poster_path.strip()
    if not poster_path:
        return ""
    if poster_path.startswith(("http://", "https://")):
        return poster_path
    if poster_path.startswith("/"):
        return f"https://image.tmdb.org/t/p/w500{poster_path}"
    return f"https://image.tmdb.org/t/p/w500/{poster_path}"


def format_tmdb_candidate_lines(tmdb_candidates: Sequence[TmdbMovie]) -> tuple[str, ...]:
    lines: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in tmdb_candidates[:5]:
        title = normalize_spaces(candidate.original_title) or normalize_spaces(candidate.title) or "-"
        alias = normalize_spaces(candidate.title)
        year = candidate.year.strip() or "-"
        media_type = candidate.media_type.strip() or "-"
        key = (media_type, candidate.tmdb_id, title)
        if key in seen:
            continue
        seen.add(key)
        if alias and alias != title:
            lines.append(f"- {media_type} | {title} / {alias} | {year}")
        else:
            lines.append(f"- {media_type} | {title} | {year}")
    return tuple(lines)


def format_ranked_tmdb_candidate_lines(tmdb_candidates: Sequence[TmdbMovie]) -> tuple[str, ...]:
    lines: list[str] = []
    for index, candidate in enumerate(tmdb_candidates[:5], start=1):
        card_title, card_year, card_media_type, card_alias, _, card_overview = resolve_movie_card_fields(
            ParsedMovieQuery(title=candidate.title, year=candidate.year),
            candidate,
            prefer_localized_title=True,
        )
        title_line = f"{index}. {card_title} ({card_year}) | {card_media_type}"
        lines.append(title_line)
        poster_url = resolve_tmdb_poster_url(candidate)
        if poster_url:
            lines.append(f"   海报: {poster_url}")
        if card_alias != "-":
            lines.append(f"   原名: {card_alias}")
        if card_overview:
            lines.append(f"   简介: {truncate_text(card_overview, limit=80)}")
    return tuple(lines)


def build_search_results_delivery_item(
    *,
    query: str,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
    candidates: Sequence[Candidate],
    tmdb_candidates: Sequence[TmdbMovie] = (),
) -> DeliveryItem:
    if not candidates:
        raise ValueError("search results delivery requires at least one candidate")
    card_title, card_year, card_media_type, card_alias, card_poster, card_overview = resolve_movie_card_fields(
        parsed_query,
        tmdb_movie,
    )
    candidate_lines: list[str] = []
    for index, item in enumerate(candidates, start=1):
        candidate_lines.append(f"{index}. {item.title} ({item.year})")
        candidate_lines.append(f"画质：{item.quality} ｜ 大小：{item.size} ｜ 站点：{item.indexer}")
    media_info_lines = [
        f"片名：{card_title}",
        f"年份：{card_year}",
        f"类型：{card_media_type}",
        f"别名：{card_alias}",
        f"海报：{card_poster}",
    ]
    if card_overview:
        media_info_lines.append(f"简介：{truncate_text(card_overview, limit=120)}")
    candidate_info_lines = format_tmdb_candidate_lines(tmdb_candidates)
    if candidate_info_lines:
        media_info_lines.append("相关作品：")
        media_info_lines.extend(candidate_info_lines)
    return DeliveryItem(
        header=DeliveryHeader(kind="search_results", title=f"搜索：{query}", subtitle=f"候选结果（{len(candidates)} 条）"),
        sections=(
            DeliverySection(label="电影信息", lines=tuple(media_info_lines)),
            DeliverySection(label="候选结果", lines=tuple(candidate_lines)),
        ),
        actions=(
            DeliveryAction(label="开始下载", hint="发送 select 1", kind="primary"),
            DeliveryAction(label="换关键词", hint=f"发送 search {query}", kind="secondary"),
        ),
        status="success",
    )


def build_media_candidate_confirmation_delivery_item(
    *,
    query: str,
    parsed_query: ParsedMovieQuery,
    tmdb_candidates: Sequence[TmdbMovie],
) -> DeliveryItem:
    if not tmdb_candidates:
        raise ValueError("media candidate confirmation requires at least one candidate")
    sections: list[DeliverySection] = []
    for index, candidate in enumerate(tmdb_candidates[:5], start=1):
        card_title, card_year, card_media_type, card_alias, card_poster, card_overview = resolve_movie_card_fields(
            ParsedMovieQuery(title=candidate.title, year=candidate.year),
            candidate,
            prefer_localized_title=True,
        )
        candidate_lines = [
            f"海报：{card_poster}",
            f"年份：{card_year}",
            f"类型：{card_media_type}",
        ]
        if card_alias != "-":
            candidate_lines.append(f"原名：{card_alias}")
        if card_overview:
            candidate_lines.append(f"简介：{truncate_text(card_overview, limit=120)}")
        sections.append(
            DeliverySection(
                label=f"{index}. {card_title} ({card_year}) | {card_media_type}",
                lines=tuple(candidate_lines),
            )
        )
    return DeliveryItem(
        header=DeliveryHeader(kind="media_candidate_confirmation", title=f"候选作品：{query}", subtitle=f"候选作品（{len(tmdb_candidates[:5])} 条）"),
        sections=tuple(sections),
        actions=(
            DeliveryAction(label="确认作品", hint="发送 1", kind="primary"),
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
