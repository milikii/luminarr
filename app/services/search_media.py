from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.clients.tmdb import TmdbMovie
from app.db.candidate_repo import CandidateMappingRepo
from app.db.clarification_repo import ClarificationRepo

SearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
LookupMovieFunc = Callable[[str, str], Awaitable[TmdbMovie | None]]

EMPTY_QUERY_TEXT = "请输入要搜索的内容。"
NO_RESULT_TEXT_TEMPLATE = "未找到候选结果：{query}"
AMBIGUOUS_QUERY_TEXT_TEMPLATE = (
    "片名可能有多个版本：{query}\n"
    "请补充更具体信息后再搜索，例如：\n"
    "- 片名 + 年份（例如：Dune 2021）\n"
    "- 更完整片名（例如：Dune Part Two）\n"
    "只读探索参考：\n"
    "{options}"
)
AMBIGUOUS_OPTION_FALLBACK_TEXT = "- 暂无可区分候选，请直接补充年份。"
AMBIGUOUS_MIN_RESULT_COUNT = 3
AMBIGUOUS_MAX_OPTION_COUNT = 3


@dataclass(frozen=True, slots=True)
class Candidate:
    title: str
    year: str
    quality: str
    size: str
    indexer: str


@dataclass(frozen=True, slots=True)
class ParsedMovieQuery:
    title: str
    year: str


@dataclass(frozen=True, slots=True)
class AmbiguousOption:
    title: str
    year: str


class SearchMediaService:
    def __init__(
        self,
        search_func: SearchFunc,
        limit: int = 5,
        candidate_repo: CandidateMappingRepo | None = None,
        clarification_repo: ClarificationRepo | None = None,
        lookup_movie_func: LookupMovieFunc | None = None,
    ) -> None:
        self._search_func = search_func
        self._limit = max(1, limit)
        self._candidate_repo = candidate_repo
        self._clarification_repo = clarification_repo
        self._lookup_movie_func = lookup_movie_func
        self._recent_candidates_by_chat: dict[int, list[dict[str, Any]]] = {}
        self._clarification_pending_by_chat: dict[int, str] = {}

    async def search_and_format(self, query: str, chat_id: int | None = None) -> str:
        cleaned_query = query.strip()
        if not cleaned_query:
            return EMPTY_QUERY_TEXT

        parsed_query = parse_movie_query(cleaned_query)
        fallback_query = _build_query(parsed_query.title, parsed_query.year)
        raw_results: Sequence[Mapping[str, Any]] = ()
        tmdb_movie: TmdbMovie | None = None

        if self._lookup_movie_func is not None:
            try:
                tmdb_movie = await self._lookup_movie_func(parsed_query.title, parsed_query.year)
            except Exception:
                tmdb_movie = None
            if tmdb_movie is not None:
                resolved_year = tmdb_movie.year or parsed_query.year
                ordered_queries = _unique_queries(
                    [
                        _build_query(tmdb_movie.title, resolved_year),
                        _build_query(tmdb_movie.original_title, resolved_year),
                    ]
                )
                raw_results = await _search_first_non_empty(self._search_func, ordered_queries)
            else:
                raw_results = await self._search_func(fallback_query)
        else:
            raw_results = await self._search_func(fallback_query)

        ambiguous_text = _format_ambiguous_clarification(
            query=cleaned_query,
            parsed_query=parsed_query,
            raw_results=raw_results,
        )
        if ambiguous_text is not None:
            if chat_id is not None:
                self._set_clarification_pending(chat_id=chat_id, query=cleaned_query)
            return ambiguous_text

        selected_raw_results = [_to_candidate_dict(item) for item in raw_results[: self._limit]]
        if chat_id is not None:
            self._recent_candidates_by_chat[chat_id] = selected_raw_results
            if selected_raw_results:
                self._clear_clarification_pending(chat_id=chat_id)
            else:
                self._set_clarification_pending(chat_id=chat_id, query=cleaned_query)
            if self._candidate_repo is not None:
                try:
                    self._candidate_repo.save_candidates(chat_id, selected_raw_results)
                except Exception:
                    pass

        candidates = [normalize_candidate(item) for item in selected_raw_results]
        return format_movie_query_reply(cleaned_query, parsed_query, tmdb_movie, candidates)

    def get_cached_candidate(self, chat_id: int, index: int) -> Mapping[str, Any] | None:
        if index < 1:
            return None
        candidates = self._recent_candidates_by_chat.get(chat_id)
        resolved_index = index - 1
        if candidates and resolved_index < len(candidates):
            return candidates[resolved_index]

        if self._candidate_repo is None:
            return None
        try:
            persisted_candidate = self._candidate_repo.get_candidate(chat_id, index)
        except Exception:
            return None
        if persisted_candidate is None:
            return None
        return persisted_candidate

    def has_cached_candidates(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False
        if self.get_cached_candidate(chat_id, 1) is not None:
            return True
        return False

    def clear_cached_candidates(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False

        cleared = False
        if chat_id in self._recent_candidates_by_chat:
            self._recent_candidates_by_chat.pop(chat_id, None)
            cleared = True
        cleared = self._clear_clarification_pending(chat_id=chat_id) or cleared

        if self._candidate_repo is None:
            return cleared
        try:
            return self._candidate_repo.clear_candidates(chat_id) or cleared
        except Exception:
            return cleared

    def is_clarification_pending(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False
        if chat_id in self._clarification_pending_by_chat:
            return True
        pending_query = self._load_persisted_clarification_query(chat_id=chat_id)
        if pending_query is None:
            return False
        self._clarification_pending_by_chat[chat_id] = pending_query
        return True

    def clear_clarification_pending(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False
        return self._clear_clarification_pending(chat_id=chat_id)

    def _set_clarification_pending(self, *, chat_id: int, query: str) -> None:
        if chat_id <= 0:
            return
        self._clarification_pending_by_chat[chat_id] = query
        if self._clarification_repo is None:
            return
        try:
            self._clarification_repo.upsert_pending(chat_id=chat_id, query=query)
        except Exception:
            pass

    def _clear_clarification_pending(self, *, chat_id: int) -> bool:
        cleared = False
        if chat_id in self._clarification_pending_by_chat:
            self._clarification_pending_by_chat.pop(chat_id, None)
            cleared = True
        if self._clarification_repo is None:
            return cleared
        try:
            return self._clarification_repo.clear_pending(chat_id=chat_id) or cleared
        except Exception:
            return cleared

    def _load_persisted_clarification_query(self, *, chat_id: int) -> str | None:
        if self._clarification_repo is None:
            return None
        try:
            return self._clarification_repo.get_pending_query(chat_id=chat_id)
        except Exception:
            return None


def parse_movie_query(query: str) -> ParsedMovieQuery:
    cleaned_query = _normalize_spaces(query)
    if not cleaned_query:
        return ParsedMovieQuery(title="", year="")

    matched_parentheses = re.match(
        r"^(?P<title>.+?)\s*[\(（](?P<year>(?:19|20)\d{2})[\)）]\s*$",
        cleaned_query,
    )
    if matched_parentheses is not None:
        title = _normalize_spaces(matched_parentheses.group("title"))
        year = matched_parentheses.group("year")
        if title:
            return ParsedMovieQuery(title=title, year=year)

    matched_suffix = re.match(r"^(?P<title>.+?)\s+(?P<year>(?:19|20)\d{2})\s*$", cleaned_query)
    if matched_suffix is not None:
        title = _normalize_spaces(matched_suffix.group("title"))
        year = matched_suffix.group("year")
        if title:
            return ParsedMovieQuery(title=title, year=year)

    return ParsedMovieQuery(title=cleaned_query, year="")


def normalize_candidate(item: Mapping[str, Any]) -> Candidate:
    title = _safe_text(item.get("title"), default="(no title)")
    year = _safe_year(item.get("year"))
    quality = _safe_text(item.get("quality"), default="-")
    if quality == "-" and "resolution" in item:
        quality = _safe_text(item.get("resolution"), default="-")
    if quality == "-":
        quality = _guess_quality_from_title(title)
    size = _format_size(item.get("size"))
    indexer = _safe_indexer(item.get("indexer"), item.get("indexerName"))
    return Candidate(title=title, year=year, quality=quality, size=size, indexer=indexer)


def format_candidates(query: str, candidates: Sequence[Candidate]) -> str:
    if not candidates:
        return NO_RESULT_TEXT_TEMPLATE.format(query=query)

    lines = [f"搜索结果：{query}"]
    for i, item in enumerate(candidates, start=1):
        lines.append(f"{i}. {item.title} ({item.year})")
        lines.append(f"   画质: {item.quality} | 大小: {item.size} | 站点: {item.indexer}")
    return "\n".join(lines)


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


def format_movie_poster_card(parsed_query: ParsedMovieQuery, tmdb_movie: TmdbMovie | None) -> str:
    card_title = parsed_query.title or "-"
    card_year = parsed_query.year.strip() or "-"
    card_alias = "-"

    if tmdb_movie is not None:
        original_title = _normalize_spaces(tmdb_movie.original_title)
        english_title = _normalize_spaces(tmdb_movie.title)
        if original_title:
            card_title = original_title
        elif english_title:
            card_title = english_title

        resolved_year = tmdb_movie.year.strip()
        if resolved_year:
            card_year = resolved_year

        if english_title and english_title != card_title:
            card_alias = english_title

    lines = [
        "电影海报卡片",
        f"片名: {card_title}",
        f"年份: {card_year}",
        f"别名: {card_alias}",
        "海报: 暂未接入图片",
    ]
    return "\n".join(lines)


def _safe_text(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text


def _safe_year(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    return text


def _safe_indexer(indexer_value: Any, indexer_name_value: Any) -> str:
    if isinstance(indexer_value, Mapping):
        mapped_name = _safe_text(indexer_value.get("name"), default="-")
        if mapped_name != "-":
            return mapped_name

    name = _safe_text(indexer_name_value, default="-")
    if name != "-":
        return name
    return _safe_text(indexer_value, default="-")


def _format_size(size_value: Any) -> str:
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


def _guess_quality_from_title(title: str) -> str:
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


def _to_candidate_dict(item: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in item.items()}


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _build_query(title: str, year: str) -> str:
    cleaned_title = _normalize_spaces(title)
    cleaned_year = year.strip()
    if not cleaned_year:
        return cleaned_title
    return f"{cleaned_title} {cleaned_year}"


async def _search_first_non_empty(search_func: SearchFunc, ordered_queries: Sequence[str]) -> Sequence[Mapping[str, Any]]:
    for query in ordered_queries:
        raw_results = await search_func(query)
        if raw_results:
            return raw_results
    return ()


def _unique_queries(candidates: Sequence[str]) -> list[str]:
    ordered_queries: list[str] = []
    for query in candidates:
        cleaned_query = query.strip()
        if not cleaned_query:
            continue
        if cleaned_query in ordered_queries:
            continue
        ordered_queries.append(cleaned_query)
    return ordered_queries


def _format_ambiguous_clarification(
    *,
    query: str,
    parsed_query: ParsedMovieQuery,
    raw_results: Sequence[Mapping[str, Any]],
) -> str | None:
    if parsed_query.year.strip():
        return None
    if len(raw_results) < AMBIGUOUS_MIN_RESULT_COUNT:
        return None

    options = _collect_ambiguous_options(raw_results)
    if not _is_highly_ambiguous(options):
        return None

    option_lines = [f"- {option.title} ({option.year})" for option in options[:AMBIGUOUS_MAX_OPTION_COUNT]]
    if not option_lines:
        option_lines.append(AMBIGUOUS_OPTION_FALLBACK_TEXT)

    return AMBIGUOUS_QUERY_TEXT_TEMPLATE.format(
        query=query,
        options="\n".join(option_lines),
    )


def _collect_ambiguous_options(raw_results: Sequence[Mapping[str, Any]]) -> list[AmbiguousOption]:
    options: list[AmbiguousOption] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in raw_results:
        title = _safe_text(item.get("title"), default="")
        if not title:
            continue
        year = _safe_year(item.get("year"))
        key = (_normalize_title_key(title), year)
        if not key[0]:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        options.append(AmbiguousOption(title=title, year=year))
    return options


def _is_highly_ambiguous(options: Sequence[AmbiguousOption]) -> bool:
    if len(options) < 2:
        return False

    distinct_titles = {_normalize_title_key(option.title) for option in options if option.title}
    distinct_years = {option.year for option in options if option.year != "-"}
    if len(distinct_years) >= 2 and len(distinct_titles) >= 2:
        return True
    return len(options) >= 3 and len(distinct_titles) >= 3


def _normalize_title_key(title: str) -> str:
    lowered = title.lower()
    lowered = re.sub(r"\b(?:19|20)\d{2}\b", " ", lowered)
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()
