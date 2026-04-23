from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.clients.web_source import (
    looks_like_http_url,
    looks_like_web_source_page_request,
    resolve_supported_web_source_page_request,
)
from app.db.candidate_repo import CandidateMappingRepo
from app.db.clarification_repo import ClarificationRepo
from app.services.bt_candidate_scorer import BTCandidate, BTScoringContext, filter_candidates, load_bt_scoring_rules
from app.services.search_candidate_state import CandidateLoadResult, CandidateStateStore
from app.services.search_clarification_state import ClarificationQueryLoadResult, ClarificationStateStore
from app.services.bt_sources import resolve_bt_source
from app.services import search_reply_formatter
from app.services import search_request_context
from app.services.search_reply_formatter import (
    format_bt_batch_preview_reply,
    format_bt_batch_preview_selection_label,
    format_bt_read_only_reply,
    format_movie_query_reply,
    normalize_candidate,
    render_search_results_reply,
    safe_indexer,
    safe_text,
    safe_year,
)
from app.services.search_request_context import (
    LookupMovieFunc,
    ParsedMovieQuery,
    SearchFunc,
    build_search_request_context,
    normalize_spaces,
)
from app.services.pure_bt import BTBatchPreviewRequest, select_batch_preview_candidates

EMPTY_QUERY_TEXT = "请输入要搜索的内容。"
NO_RESULT_TEXT_TEMPLATE = search_reply_formatter.NO_RESULT_TEXT_TEMPLATE
BT_READ_ONLY_EMPTY_QUERY_TEXT = "BT 只读探索格式：bt搜 <关键词>"
BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE = search_reply_formatter.BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE
BT_READ_ONLY_NOTICE_TEXT = search_reply_formatter.BT_READ_ONLY_NOTICE_TEXT
BT_BATCH_PREVIEW_EMPTY_QUERY_TEXT = "BT 批量预览格式：bt批量 <关键词或 allowlist 页面 URL> [1-3,5]"
BT_BATCH_PREVIEW_PAGE_URL_UNSUPPORTED_TEXT_TEMPLATE = (
    "BT 批量预览暂不支持这个页面：{query}\n"
    "请提供当前 allowlist 站点已声明的用户页、列表页或搜索结果页 URL。"
)
BT_BATCH_PREVIEW_INVALID_SELECTION_TEMPLATE = (
    "BT 批量预览编号格式无效：{selection}\n"
    "请使用 1-3 或 2,4,6 这类范围表达。"
)
BT_BATCH_PREVIEW_OUT_OF_RANGE_TEMPLATE = (
    "BT 批量预览编号超出范围：{selection}\n"
    "当前可选范围：1-{available_count}"
)
BT_BATCH_PREVIEW_NO_RESULT_TEXT_TEMPLATE = search_reply_formatter.BT_BATCH_PREVIEW_NO_RESULT_TEXT_TEMPLATE
BT_BATCH_PREVIEW_NOTICE_TEMPLATE = search_reply_formatter.BT_BATCH_PREVIEW_NOTICE_TEMPLATE
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
CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT = "搜索待澄清状态写入失败，请稍后重试。"
CANDIDATE_STATE_UNAVAILABLE_TEXT = "搜索候选状态写入失败，请稍后重试。"
CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT = "搜索待澄清状态清理失败，请稍后重试。"
SUPPORTED_DELIVERY_CHANNELS = frozenset({"telegram", "feishu", "personal_wechat", "wecom"})
parse_movie_query = search_request_context.parse_movie_query


class UnsupportedBatchPreviewPageUrl(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AmbiguousOption:
    title: str
    year: str


class SearchMediaService:
    def __init__(
        self,
        search_func: SearchFunc,
        raw_search_func: SearchFunc | None = None,
        raw_page_search_func: SearchFunc | None = None,
        limit: int = 5,
        candidate_repo: CandidateMappingRepo | None = None,
        clarification_repo: ClarificationRepo | None = None,
        lookup_movie_func: LookupMovieFunc | None = None,
    ) -> None:
        self._search_func = search_func
        self._raw_search_func = raw_search_func or search_func
        self._raw_page_search_func = raw_page_search_func
        self._limit = max(1, limit)
        self._candidate_state = CandidateStateStore(repo=candidate_repo)
        self._clarification_state = ClarificationStateStore(repo=clarification_repo)
        self._lookup_movie_func = lookup_movie_func
        self._recent_candidates_by_chat = self._candidate_state.recent_by_chat
        self._clarification_pending_by_chat = self._clarification_state.pending_by_chat

    async def search_raw_candidates(self, query: str) -> Sequence[Mapping[str, Any]]:
        cleaned_query = query.strip()
        if not cleaned_query:
            return ()
        try:
            return await self._raw_search_func(cleaned_query)
        except Exception as error:
            print(
                f"\033[31m[BT 只读搜索失败]\033[0m query={cleaned_query} 错误={error}\n\033[33m[处理建议]\033[0m 检查 BT 搜索源、代理和网络连通性；当前只读探索没有拿到结果，且这不是正常的“无候选”状态。",
                flush=True,
            )
            raise

    async def search_bt_read_only_and_format(self, query: str) -> str:
        cleaned_query = normalize_spaces(query)
        if not cleaned_query:
            return BT_READ_ONLY_EMPTY_QUERY_TEXT

        raw_results = await self.search_raw_candidates(cleaned_query)
        selected_raw_results = [_to_candidate_dict(item) for item in raw_results[: self._limit]]
        return format_bt_read_only_reply(cleaned_query, selected_raw_results)

    async def search_bt_batch_preview_and_format(self, request: BTBatchPreviewRequest) -> str:
        return await self.search_bt_batch_preview_and_format_for_chat(request, chat_id=None)

    async def search_bt_batch_preview_and_format_for_chat(
        self,
        request: BTBatchPreviewRequest,
        *,
        chat_id: int | None,
    ) -> str:
        cleaned_query = normalize_spaces(request.query)
        if not cleaned_query:
            return BT_BATCH_PREVIEW_EMPTY_QUERY_TEXT
        if request.invalid_selection:
            return BT_BATCH_PREVIEW_INVALID_SELECTION_TEMPLATE.format(selection=request.selection_text or "-")
        try:
            raw_results = await self._search_bt_batch_preview_candidates(cleaned_query)
        except UnsupportedBatchPreviewPageUrl:
            return BT_BATCH_PREVIEW_PAGE_URL_UNSUPPORTED_TEXT_TEMPLATE.format(query=cleaned_query)
        selection = select_batch_preview_candidates(raw_results, request=request, default_limit=self._limit)
        if selection.out_of_range:
            return BT_BATCH_PREVIEW_OUT_OF_RANGE_TEMPLATE.format(
                selection=request.selection_text or "-",
                available_count=selection.available_count,
            )
        selected_raw_results = [_to_candidate_dict(item) for item in selection.candidates]
        if chat_id is not None:
            persist_error_text = self._cache_bt_batch_preview_candidates(chat_id=chat_id, candidates=selected_raw_results)
            if persist_error_text:
                return persist_error_text
        selection_label = format_bt_batch_preview_selection_label(selection.selected_indexes)
        return format_bt_batch_preview_reply(cleaned_query, selected_raw_results, selection_label=selection_label)

    async def _search_bt_batch_preview_candidates(self, query: str) -> Sequence[Mapping[str, Any]]:
        resolved_page_url = resolve_supported_web_source_page_request(query)
        if resolved_page_url is not None:
            if self._raw_page_search_func is None:
                raise UnsupportedBatchPreviewPageUrl(query)
            return await self._search_raw_page_candidates(resolved_page_url)
        if looks_like_http_url(query) or looks_like_web_source_page_request(query):
            raise UnsupportedBatchPreviewPageUrl(query)
        return await self.search_raw_candidates(query)

    async def _search_raw_page_candidates(self, page_url: str) -> Sequence[Mapping[str, Any]]:
        cleaned_page_url = page_url.strip()
        if not cleaned_page_url:
            return ()
        if self._raw_page_search_func is None:
            raise UnsupportedBatchPreviewPageUrl(cleaned_page_url)
        try:
            return await self._raw_page_search_func(cleaned_page_url)
        except UnsupportedBatchPreviewPageUrl:
            raise
        except Exception as error:
            print(
                f"\033[31m[BT 页面预览失败]\033[0m 页面={cleaned_page_url} 错误={error}\n"
                "\033[33m[处理建议]\033[0m 检查页面 URL 是否仍在 allowlist 内、站点是否可达，以及 HTML 结构是否变化后重试。",
                flush=True,
            )
            raise

    async def search_and_format(
        self,
        query: str,
        chat_id: int | None = None,
        *,
        channel: str | None = None,
    ) -> str:
        cleaned_query = query.strip()
        if not cleaned_query:
            return EMPTY_QUERY_TEXT

        request_context = await build_search_request_context(
            user_query=cleaned_query,
            search_func=self._search_func,
            lookup_movie_func=self._lookup_movie_func,
        )
        parsed_query = request_context.parsed_query
        tmdb_movie = request_context.tmdb_movie
        raw_results = request_context.raw_results

        ambiguous_text = _format_ambiguous_clarification(
            query=cleaned_query,
            parsed_query=parsed_query,
            raw_results=raw_results,
        )
        if ambiguous_text is not None:
            if chat_id is not None and not self._set_clarification_pending(chat_id=chat_id, query=cleaned_query):
                return CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT
            return ambiguous_text

        ordered_raw_results = _order_media_bt_results(
            raw_results,
            query=request_context.resolved_query or cleaned_query,
        )
        selected_raw_results = [_to_candidate_dict(item) for item in ordered_raw_results[: self._limit]]
        if chat_id is not None:
            self._recent_candidates_by_chat[chat_id] = selected_raw_results
            if selected_raw_results:
                clarification_pending = self.is_clarification_pending(chat_id)
                if clarification_pending is None:
                    self._recent_candidates_by_chat.pop(chat_id, None)
                    return CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT
                if clarification_pending and not self._clear_clarification_pending(chat_id=chat_id):
                    self._recent_candidates_by_chat.pop(chat_id, None)
                    return CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT
            else:
                if not self._set_clarification_pending(chat_id=chat_id, query=cleaned_query):
                    self._recent_candidates_by_chat.pop(chat_id, None)
                    return CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT
            if not self._candidate_state.persist_search_candidates(chat_id=chat_id, candidates=selected_raw_results):
                return CANDIDATE_STATE_UNAVAILABLE_TEXT

        candidates = [normalize_candidate(item) for item in selected_raw_results]
        if channel in SUPPORTED_DELIVERY_CHANNELS and candidates:
            return render_search_results_reply(
                query=cleaned_query,
                parsed_query=parsed_query,
                tmdb_movie=tmdb_movie,
                candidates=candidates,
                channel=channel,
            )
        return format_movie_query_reply(cleaned_query, parsed_query, tmdb_movie, candidates)

    def get_cached_candidate(self, chat_id: int, index: int) -> Mapping[str, Any] | None:
        return self.get_cached_candidate_load_result(chat_id, index).candidate

    def _cache_bt_batch_preview_candidates(self, *, chat_id: int, candidates: list[dict[str, Any]]) -> str:
        if self._candidate_state.persist_bt_batch_preview_candidates(chat_id=chat_id, candidates=candidates):
            return ""
        return CANDIDATE_STATE_UNAVAILABLE_TEXT

    def get_cached_candidate_load_result(self, chat_id: int, index: int) -> CandidateLoadResult:
        return self._candidate_state.get_cached_candidate_load_result(chat_id, index)

    def has_cached_candidates(self, chat_id: int) -> bool | None:
        return self._candidate_state.has_cached_candidates(chat_id)

    def clear_cached_candidates(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False
        cleared = self._clear_clarification_pending(chat_id=chat_id)
        return self._candidate_state.clear_cached_candidates(chat_id) or cleared

    def is_clarification_pending(self, chat_id: int) -> bool | None:
        return self._clarification_state.is_pending(chat_id)

    def clear_clarification_pending(self, chat_id: int) -> bool:
        return self._clarification_state.clear_pending(chat_id)

    def _set_clarification_pending(self, *, chat_id: int, query: str) -> bool:
        return self._clarification_state.set_pending(chat_id=chat_id, query=query)

    def _clear_clarification_pending(self, *, chat_id: int) -> bool:
        return self._clarification_state.clear_pending(chat_id)

    def _load_persisted_clarification_query(self, *, chat_id: int) -> ClarificationQueryLoadResult:
        return self._clarification_state.load_persisted_query(chat_id=chat_id)

    def _load_persisted_candidate(self, *, chat_id: int, index: int) -> CandidateLoadResult:
        return self._candidate_state.load_persisted_candidate(chat_id=chat_id, index=index)


def _order_media_bt_results(
    raw_results: Sequence[Mapping[str, Any]],
    *,
    query: str,
) -> Sequence[Mapping[str, Any]]:
    candidate_pairs: list[tuple[BTCandidate, Mapping[str, Any]]] = []
    remainder: list[Mapping[str, Any]] = []
    for item in raw_results:
        candidate = _build_media_bt_candidate(item)
        if candidate is None:
            remainder.append(item)
            continue
        candidate_pairs.append((candidate, item))
    if not candidate_pairs:
        return raw_results

    scored_candidates = filter_candidates(
        [candidate for candidate, _ in candidate_pairs],
        BTScoringContext(query=query, media_kind="movie"),
        rules=load_bt_scoring_rules(),
    )
    if all(scored_candidate.drop_reason == "title_mismatch" for scored_candidate in scored_candidates):
        fallback_queries = _derive_media_title_fallback_queries(raw_results, query=query)
        best_fallback_metrics: tuple[int, float, float] | None = None
        best_rescored_candidates: Sequence[Any] | None = None
        for fallback_query in fallback_queries:
            rescored_candidates = filter_candidates(
                [candidate for candidate, _ in candidate_pairs],
                BTScoringContext(query=fallback_query, media_kind="movie"),
                rules=load_bt_scoring_rules(),
            )
            fallback_metrics = _score_fallback_candidates(rescored_candidates)
            if fallback_metrics[0] <= 0:
                continue
            if best_fallback_metrics is None or fallback_metrics > best_fallback_metrics:
                best_fallback_metrics = fallback_metrics
                best_rescored_candidates = rescored_candidates
        if best_rescored_candidates is not None:
            scored_candidates = list(best_rescored_candidates)

    ordered_results: list[Mapping[str, Any]] = []
    for scored_candidate in scored_candidates:
        for candidate, item in candidate_pairs:
            if candidate is scored_candidate.candidate:
                ordered_results.append(item)
                break
    ordered_results.extend(remainder)
    return tuple(ordered_results)


def _derive_media_title_fallback_queries(
    raw_results: Sequence[Mapping[str, Any]],
    *,
    query: str,
) -> tuple[str, ...]:
    parsed_query = parse_movie_query(query)
    titles = [safe_text(item.get("title"), default="") for item in raw_results[:5]]
    normalized_titles = [_normalize_title_tokens_for_fallback(title) for title in titles if title]
    if not normalized_titles:
        return ()
    token_counts = _count_fallback_tokens(normalized_titles)
    minimum_shared_count = 1 if len(normalized_titles) == 1 else 2
    fallback_queries: list[str] = []
    for title_tokens in normalized_titles:
        common_tokens = [token for token in title_tokens if token_counts.get(token, 0) >= minimum_shared_count]
        if not common_tokens:
            continue
        query_text = " ".join(common_tokens).strip()
        if not query_text:
            continue
        fallback_queries.append(f"{query_text} {parsed_query.year}".strip() if parsed_query.year else query_text)
    return tuple(dict.fromkeys(fallback_queries))


def _normalize_title_tokens_for_fallback(title: str) -> list[str]:
    normalized = title.strip().lower()
    normalized = re.sub(r"[._:：\-/]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    tokens = [token for token in normalized.split() if token]
    stopwords = {
        "2160p",
        "1080p",
        "720p",
        "480p",
        "web",
        "dl",
        "webdl",
        "webrip",
        "bluray",
        "blu",
        "ray",
        "bdrip",
        "hdr",
        "dv",
        "hevc",
        "x264",
        "x265",
        "h264",
        "h265",
        "ddp",
        "aac",
        "dts",
        "atmos",
        "truehd",
        "uhd",
        "10bit",
        "8bit",
        "remux",
        "ma",
        "2audios",
        "csweb",
        "frds",
        "hdsweb",
        "diy",
        "hhweb",
        "eur",
        "max",
    }
    return [token for token in tokens if token not in stopwords and not re.fullmatch(r"(?:19|20)\d{2}", token)]


def _count_fallback_tokens(normalized_titles: Sequence[Sequence[str]]) -> dict[str, int]:
    token_counts: dict[str, int] = {}
    for tokens in normalized_titles:
        for token in dict.fromkeys(tokens):
            token_counts[token] = token_counts.get(token, 0) + 1
    return token_counts


def _score_fallback_candidates(scored_candidates: Sequence[Any]) -> tuple[int, float, float]:
    accepted_candidates = [candidate for candidate in scored_candidates if candidate.drop_reason is None]
    if not accepted_candidates:
        return 0, 0.0, 0.0
    return (
        len(accepted_candidates),
        max(candidate.score for candidate in accepted_candidates),
        sum(candidate.score for candidate in accepted_candidates),
    )


def _build_media_bt_candidate(item: Mapping[str, Any]) -> BTCandidate | None:
    source = resolve_bt_source(item)
    title = safe_text(item.get("title"), default="")
    if not source or not title:
        return None
    return BTCandidate(
        source_site=safe_indexer(item.get("indexer"), item.get("indexerName")),
        title=title,
        magnet_or_torrent_url=source,
        size_bytes=_safe_optional_int(item.get("size")),
        seeders=_safe_optional_int(item.get("seeders")),
        leechers=_safe_optional_int(item.get("peers")),
        resolution=_extract_resolution(title),
        codec=_extract_codec(title),
        source_type=_extract_source_type(title),
        audio=(),
        release_group=_extract_release_group(title),
        age_days=None,
        media_kind="movie",
    )


def _extract_resolution(title: str) -> str | None:
    lowered_title = title.strip().lower()
    if re.search(r"\b(2160p|4k)\b", lowered_title):
        return "2160p"
    if re.search(r"\b1080p\b", lowered_title):
        return "1080p"
    if re.search(r"\b720p\b", lowered_title):
        return "720p"
    return None


def _extract_codec(title: str) -> str | None:
    lowered_title = title.strip().lower()
    if re.search(r"\b(x265|hevc)\b", lowered_title):
        return "x265" if "x265" in lowered_title else "HEVC"
    if re.search(r"\b(x264|avc)\b", lowered_title):
        return "x264"
    return None


def _extract_source_type(title: str) -> str | None:
    lowered_title = title.strip().lower()
    if "remux" in lowered_title:
        return "Remux"
    if "bluray" in lowered_title or "blu-ray" in lowered_title:
        return "BluRay"
    if "bdrip" in lowered_title:
        return "BDRip"
    if "web-dl" in lowered_title or "webdl" in lowered_title:
        return "WEB-DL"
    if "webrip" in lowered_title or "web-rip" in lowered_title:
        return "WEBRip"
    return None


def _extract_release_group(title: str) -> str | None:
    matched = re.search(r"-([A-Za-z0-9][A-Za-z0-9-]+)$", title.strip())
    if matched is None:
        return None
    return str(matched.group(1) or "").strip() or None


def _safe_optional_int(value: Any) -> int | None:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return None
    if resolved > 0:
        return resolved
    return None


def _to_candidate_dict(item: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in item.items()}


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
        title = safe_text(item.get("title"), default="")
        if not title:
            continue
        year = safe_year(item.get("year"))
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
