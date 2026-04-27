from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from app.clients.web_source import (
    looks_like_http_url,
    looks_like_web_source_page_request,
    resolve_supported_web_source_page_request,
)
from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.db.candidate_repo import CandidateMappingRepo
from app.db.clarification_repo import ClarificationRepo
from app.services.bt_read_only_display import AdultReadOnlyLookupFunc, BtReadOnlyDisplayService
from app.services.search_candidate_state import CandidateLoadResult, CandidateStateStore
from app.services.search_clarification_state import ClarificationQueryLoadResult, ClarificationStateStore
from app.services import search_reply_formatter
from app.services.search_ambiguity_helper import format_ambiguous_clarification
from app.services.search_media_bt_ordering import order_media_bt_results
from app.services.media_identity import build_media_identity_from_tmdb_movie, normalize_media_identity_payload
from app.operational_logging import emit_operational_log
from app.services.search_reply_formatter import (
    format_bt_batch_preview_reply,
    format_bt_batch_preview_selection_label,
    format_bt_read_only_reply,
    format_movie_query_reply,
    normalize_candidate,
    render_search_results_reply,
)
from app.services.search_request_context import (
    LookupMovieFunc,
    SearchFunc,
    build_search_request_context,
)
from app.services.bt_candidate_scorer import load_bt_scoring_rules as _load_bt_scoring_rules
from app.services.search_query_parser import parse_movie_query as _parse_movie_query
from app.search_title_normalization import normalize_spaces
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
CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT = "搜索待澄清状态写入失败，请稍后重试。"
CANDIDATE_STATE_UNAVAILABLE_TEXT = "搜索候选状态写入失败，请稍后重试。"
CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT = "搜索待澄清状态清理失败，请稍后重试。"
SUPPORTED_DELIVERY_CHANNELS = frozenset({"telegram", "feishu", "personal_wechat", "wecom"})
parse_movie_query = _parse_movie_query
load_bt_scoring_rules = _load_bt_scoring_rules

BatchPreviewSearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
PrepareRawCandidatesFunc = Callable[[Sequence[Mapping[str, Any]], str], Sequence[Mapping[str, Any]]]


class UnsupportedBatchPreviewPageUrl(ValueError):
    pass


async def search_bt_batch_preview_candidates(
    query: str,
    *,
    raw_search_func: BatchPreviewSearchFunc,
    raw_page_search_func: BatchPreviewSearchFunc | None,
    prepare_raw_candidates: PrepareRawCandidatesFunc,
) -> Sequence[Mapping[str, Any]]:
    resolved_page_url = resolve_supported_web_source_page_request(query)
    if resolved_page_url is not None:
        if raw_page_search_func is None:
            raise UnsupportedBatchPreviewPageUrl(query)
        return await search_raw_page_candidates(
            resolved_page_url,
            raw_page_search_func=raw_page_search_func,
            prepare_raw_candidates=prepare_raw_candidates,
        )
    if looks_like_http_url(query) or looks_like_web_source_page_request(query):
        raise UnsupportedBatchPreviewPageUrl(query)
    raw_results = await raw_search_func(query)
    return tuple(prepare_raw_candidates(raw_results, query=query))


async def search_raw_page_candidates(
    page_url: str,
    *,
    raw_page_search_func: BatchPreviewSearchFunc | None,
    prepare_raw_candidates: PrepareRawCandidatesFunc,
) -> Sequence[Mapping[str, Any]]:
    cleaned_page_url = page_url.strip()
    if not cleaned_page_url:
        return ()
    if raw_page_search_func is None:
        raise UnsupportedBatchPreviewPageUrl(cleaned_page_url)
    try:
        raw_results = await raw_page_search_func(cleaned_page_url)
    except UnsupportedBatchPreviewPageUrl:
        raise
    except Exception as error:
        emit_operational_log(
            title="BT 页面预览失败",
            detail=f"页面={cleaned_page_url} 错误={error}",
            fix_hint="检查页面 URL 是否仍在 allowlist 内、站点是否可达，以及 HTML 结构是否变化后重试。",
        )
        raise
    return tuple(prepare_raw_candidates(raw_results, query=cleaned_page_url))


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
        adult_content_registry_repo: AdultContentRegistryRepo | None = None,
        adult_read_only_lookup_func: AdultReadOnlyLookupFunc | None = None,
    ) -> None:
        self._search_func = search_func
        self._raw_search_func = raw_search_func or search_func
        self._raw_page_search_func = raw_page_search_func
        self._limit = max(1, limit)
        self._candidate_state = CandidateStateStore(repo=candidate_repo)
        self._clarification_state = ClarificationStateStore(repo=clarification_repo)
        self._lookup_movie_func = lookup_movie_func
        self._bt_read_only_display = BtReadOnlyDisplayService(
            adult_content_registry_repo=adult_content_registry_repo,
            adult_read_only_lookup_func=adult_read_only_lookup_func,
        )
        self._recent_candidates_by_chat = self._candidate_state.recent_by_chat
        self._clarification_pending_by_chat = self._clarification_state.pending_by_chat

    async def search_raw_candidates(self, query: str) -> Sequence[Mapping[str, Any]]:
        cleaned_query = query.strip()
        if not cleaned_query:
            return ()
        try:
            raw_results = await self._raw_search_func(cleaned_query)
        except Exception as error:
            emit_operational_log(
                title="BT 只读搜索失败",
                detail=f"query={cleaned_query} 错误={error}",
                fix_hint="检查 BT 搜索源、代理和网络连通性；当前只读探索没有拿到结果，且这不是正常的“无候选”状态。",
            )
            raise
        return tuple(self._bt_read_only_display.prepare_raw_candidates(raw_results, query=cleaned_query))

    async def search_bt_read_only_and_format(self, query: str) -> str:
        cleaned_query = normalize_spaces(query)
        if not cleaned_query:
            return BT_READ_ONLY_EMPTY_QUERY_TEXT

        raw_results = await self.search_raw_candidates(cleaned_query)
        display_results = await self._bt_read_only_display.build_display_candidates(
            raw_results,
            lookup_query=cleaned_query,
            limit=self._limit,
        )
        return format_bt_read_only_reply(cleaned_query, display_results)

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
            raw_results = await search_bt_batch_preview_candidates(
                cleaned_query,
                raw_search_func=self._raw_search_func,
                raw_page_search_func=self._raw_page_search_func,
                prepare_raw_candidates=self._bt_read_only_display.prepare_raw_candidates,
            )
        except UnsupportedBatchPreviewPageUrl:
            return BT_BATCH_PREVIEW_PAGE_URL_UNSUPPORTED_TEXT_TEMPLATE.format(query=cleaned_query)
        helper_match = await self._bt_read_only_display.lookup_helper_match(cleaned_query)
        selection_source_results = self._bt_read_only_display.prepare_selection_candidates(
            raw_results,
            helper_match=helper_match,
        )
        selection = select_batch_preview_candidates(selection_source_results, request=request, default_limit=self._limit)
        if selection.out_of_range:
            return BT_BATCH_PREVIEW_OUT_OF_RANGE_TEMPLATE.format(
                selection=request.selection_text or "-",
                available_count=selection.available_count,
            )
        selected_raw_results = [{str(key): value for key, value in item.items()} for item in selection.candidates]
        display_results = await self._bt_read_only_display.decorate_display_candidates(
            selected_raw_results,
            lookup_query=cleaned_query,
            helper_match=helper_match,
        )
        if chat_id is not None:
            if not self._candidate_state.persist_bt_batch_preview_candidates(
                chat_id=chat_id,
                candidates=selected_raw_results,
            ):
                return CANDIDATE_STATE_UNAVAILABLE_TEXT
        selection_label = format_bt_batch_preview_selection_label(selection.selected_indexes)
        return format_bt_batch_preview_reply(cleaned_query, display_results, selection_label=selection_label)

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
        media_identity = build_media_identity_from_tmdb_movie(tmdb_movie)

        ambiguous_text = format_ambiguous_clarification(
            query=cleaned_query,
            parsed_query=parsed_query,
            raw_results=raw_results,
        )
        if ambiguous_text is not None:
            if chat_id is not None and not self._set_clarification_pending(chat_id=chat_id, query=cleaned_query):
                return CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT
            return ambiguous_text

        ordered_raw_results = order_media_bt_results(
            raw_results,
            query=request_context.resolved_query or cleaned_query,
            load_bt_scoring_rules_func=load_bt_scoring_rules,
        )
        selected_raw_results = [{str(key): value for key, value in item.items()} for item in ordered_raw_results[: self._limit]]
        if media_identity is not None:
            normalized_media_identity = normalize_media_identity_payload(media_identity)
            if normalized_media_identity is not None:
                selected_raw_results = [
                    {
                        **item,
                        "media_identity": normalized_media_identity,
                    }
                    for item in selected_raw_results
                ]
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
