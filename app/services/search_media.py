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
from app.clients.tmdb import TmdbMovie
from app.db.candidate_repo import CandidateMappingRepo, CandidatePayloadCorruptionError, CandidatePersistenceError
from app.db.clarification_repo import ClarificationPersistenceError, ClarificationRepo
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_delivery_item
from app.services.bt_candidate_scorer import BTCandidate, BTScoringContext, filter_candidates, load_bt_scoring_rules
from app.services.bt_sources import resolve_bt_source
from app.services.search_request_context import (
    LookupMovieFunc,
    ParsedMovieQuery,
    SearchFunc,
    build_search_request_context,
    normalize_spaces,
    parse_movie_query,
)
from app.services.pure_bt import BTBatchPreviewRequest, select_batch_preview_candidates

EMPTY_QUERY_TEXT = "请输入要搜索的内容。"
NO_RESULT_TEXT_TEMPLATE = "未找到候选结果：{query}"
BT_READ_ONLY_EMPTY_QUERY_TEXT = "BT 只读探索格式：bt搜 <关键词>"
BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE = "BT 只读探索未找到候选：{query}"
BT_READ_ONLY_NOTICE_TEXT = "只读说明：当前结果仅供手动 BT 探索和站点规则排查参考，不会创建审批或下载任务。"
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
BT_BATCH_PREVIEW_NO_RESULT_TEXT_TEMPLATE = "BT 批量预览未找到候选：{query}"
BT_BATCH_PREVIEW_NOTICE_TEMPLATE = (
    "只读说明：当前批量预览只用于确认候选范围，不会创建审批或下载任务。\n"
    "当前预览范围：{selection}"
)
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
CLARIFICATION_MISSING_AFTER_UPSERT_REASON = "clarification_state missing after upsert"
CLARIFICATION_CLEAR_RESULT_MISSING_REASON = "clarification clear result missing"
CLARIFICATION_QUERY_EMPTY_AFTER_READ_REASON = "clarification_state query empty after read"
CANDIDATE_COUNT_RESULT_MISSING_AFTER_SAVE_REASON = "candidate_mapping count missing after query"
CANDIDATE_COUNT_MISMATCH_AFTER_SAVE_REASON = "candidate_mapping count mismatch after save"
CANDIDATE_CLEAR_RESULT_MISSING_REASON = "candidate clear result missing"
CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON = "candidate clear result missing during persist rollback"
SUPPORTED_DELIVERY_CHANNELS = frozenset({"telegram", "feishu", "personal_wechat", "wecom"})


class UnsupportedBatchPreviewPageUrl(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Candidate:
    title: str
    year: str
    quality: str
    size: str
    indexer: str

@dataclass(frozen=True, slots=True)
class AmbiguousOption:
    title: str
    year: str


@dataclass(frozen=True, slots=True)
class ClarificationQueryLoadResult:
    query: str | None = None
    load_failed: bool = False


@dataclass(frozen=True, slots=True)
class CandidateLoadResult:
    candidate: Mapping[str, Any] | None = None
    load_failed: bool = False


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
        self._candidate_repo = candidate_repo
        self._clarification_repo = clarification_repo
        self._lookup_movie_func = lookup_movie_func
        self._recent_candidates_by_chat: dict[int, list[dict[str, Any]]] = {}
        self._clarification_pending_by_chat: dict[int, str] = {}

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
        selection_label = _format_bt_batch_preview_selection_label(selection.selected_indexes)
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
            if self._candidate_repo is not None:
                try:
                    self._candidate_repo.save_candidates(chat_id, selected_raw_results)
                except CandidatePersistenceError as error:
                    if str(error) == CANDIDATE_COUNT_RESULT_MISSING_AFTER_SAVE_REASON:
                        print(
                            f"\033[31m[搜索候选写入结果缺失]\033[0m chat_id={chat_id} 错误={error}\n"
                            "\033[33m[处理建议]\033[0m 检查 candidate_mapping 写入后的计数查询是否仍带有完整结果；"
                            "当前会直接返回候选状态写入失败，避免把缺失真相误判成仍可继续按序号选择的候选缓存。",
                            flush=True,
                        )
                    elif str(error) == CANDIDATE_COUNT_MISMATCH_AFTER_SAVE_REASON:
                        print(
                            f"\033[31m[搜索候选写入后记录不一致]\033[0m chat_id={chat_id} 错误={error}\n"
                            "\033[33m[处理建议]\033[0m 检查 candidate_mapping 表是否被并发删除或部分回滚；"
                            "如需继续按序号选择，请先确认 SQLite 写入后条目数和预期一致。",
                            flush=True,
                        )
                    else:
                        print(
                            f"\033[31m[搜索候选持久化失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表写入是否正常；当前会直接返回候选状态写入失败，避免把持久化真相缺口混成仍可继续按序号选择的候选缓存。",
                            flush=True,
                        )
                    self._recent_candidates_by_chat.pop(chat_id, None)
                    try:
                        cleared_result = self._candidate_repo.clear_candidates(chat_id)
                        if cleared_result is None:
                            raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON)
                    except Exception as rollback_error:
                        if str(rollback_error) == CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON:
                            print(
                                f"\033[31m[搜索候选回滚清理结果缺失]\033[0m chat_id={chat_id} 错误={rollback_error}\n"
                                "\033[33m[处理建议]\033[0m 检查 candidate_mapping 回滚删除返回是否仍带有明确结果；"
                                "当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                                flush=True,
                            )
                        else:
                            print(
                                f"\033[31m[搜索候选清理失败]\033[0m chat_id={chat_id} 错误={rollback_error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表删除是否正常；当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                                flush=True,
                            )
                    return CANDIDATE_STATE_UNAVAILABLE_TEXT
                except Exception as error:
                    print(
                        f"\033[31m[搜索候选持久化失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表写入是否正常；当前会直接返回候选状态写入失败，避免把持久化真相缺口混成仍可继续按序号选择的候选缓存。",
                        flush=True,
                    )
                    self._recent_candidates_by_chat.pop(chat_id, None)
                    try:
                        cleared_result = self._candidate_repo.clear_candidates(chat_id)
                        if cleared_result is None:
                            raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON)
                    except Exception as rollback_error:
                        if str(rollback_error) == CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON:
                            print(
                                f"\033[31m[搜索候选回滚清理结果缺失]\033[0m chat_id={chat_id} 错误={rollback_error}\n"
                                "\033[33m[处理建议]\033[0m 检查 candidate_mapping 回滚删除返回是否仍带有明确结果；"
                                "当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                                flush=True,
                            )
                        else:
                            print(
                                f"\033[31m[搜索候选清理失败]\033[0m chat_id={chat_id} 错误={rollback_error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表删除是否正常；当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                                flush=True,
                            )
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
        self._recent_candidates_by_chat[chat_id] = candidates
        if self._candidate_repo is None:
            return ""
        try:
            self._candidate_repo.save_candidates(chat_id, candidates)
        except Exception as error:
            print(
                f"\033[31m[BT 批量预览候选持久化失败]\033[0m chat_id={chat_id} 错误={error}\n"
                "\033[33m[处理建议]\033[0m 检查 SQLite/candidate_mapping 写入是否正常；"
                "当前会直接返回候选状态写入失败，避免把坏候选继续暴露给批量确认入口。",
                flush=True,
            )
            self._recent_candidates_by_chat.pop(chat_id, None)
            try:
                cleared_result = self._candidate_repo.clear_candidates(chat_id)
                if cleared_result is None:
                    raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON)
            except Exception as rollback_error:
                print(
                    f"\033[31m[BT 批量预览候选清理失败]\033[0m chat_id={chat_id} 错误={rollback_error}\n"
                    "\033[33m[处理建议]\033[0m 检查 SQLite/candidate_mapping 删除是否正常；"
                    "当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                    flush=True,
                )
            return CANDIDATE_STATE_UNAVAILABLE_TEXT
        return ""

    def get_cached_candidate_load_result(self, chat_id: int, index: int) -> CandidateLoadResult:
        if index < 1:
            return CandidateLoadResult()
        candidates = self._recent_candidates_by_chat.get(chat_id)
        resolved_index = index - 1
        if candidates and resolved_index < len(candidates):
            return CandidateLoadResult(candidate=candidates[resolved_index])

        return self._load_persisted_candidate(chat_id=chat_id, index=index)

    def has_cached_candidates(self, chat_id: int) -> bool | None:
        if chat_id <= 0:
            return False
        candidates = self._recent_candidates_by_chat.get(chat_id)
        if candidates:
            return True
        load_result = self._load_persisted_candidate(chat_id=chat_id, index=1)
        if load_result.load_failed:
            return None
        return load_result.candidate is not None

    def clear_cached_candidates(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False

        cleared = False
        previous_candidates: Sequence[Mapping[str, Any]] | None = None
        if chat_id in self._recent_candidates_by_chat:
            previous_candidates = tuple(self._recent_candidates_by_chat[chat_id])
            self._recent_candidates_by_chat.pop(chat_id, None)
            cleared = True
        cleared = self._clear_clarification_pending(chat_id=chat_id) or cleared

        if self._candidate_repo is None:
            return cleared
        try:
            cleared_result = self._candidate_repo.clear_candidates(chat_id)
            if cleared_result is None:
                raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_REASON)
            return cleared_result or cleared
        except Exception as error:
            if str(error) == CANDIDATE_CLEAR_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[搜索候选清理结果缺失]\033[0m chat_id={chat_id} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 candidate_mapping 删除返回是否仍带有明确结果；"
                    "当前进程内候选已清掉，但重启后旧候选可能仍残留。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[搜索候选清理失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表删除是否正常；当前进程内候选已清掉，但重启后旧候选可能仍残留。",
                    flush=True,
                )
            if previous_candidates is not None:
                self._recent_candidates_by_chat[chat_id] = list(previous_candidates)
            return False

    def is_clarification_pending(self, chat_id: int) -> bool | None:
        if chat_id <= 0:
            return False
        if chat_id in self._clarification_pending_by_chat:
            return True
        load_result = self._load_persisted_clarification_query(chat_id=chat_id)
        if load_result.load_failed:
            return None
        if load_result.query is None:
            return False
        self._clarification_pending_by_chat[chat_id] = load_result.query
        return True

    def clear_clarification_pending(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False
        return self._clear_clarification_pending(chat_id=chat_id)

    def _set_clarification_pending(self, *, chat_id: int, query: str) -> bool:
        if chat_id <= 0:
            return False
        previous_query = self._clarification_pending_by_chat.get(chat_id, "")
        self._clarification_pending_by_chat[chat_id] = query
        if self._clarification_repo is None:
            return True
        try:
            self._clarification_repo.upsert_pending(chat_id=chat_id, query=query)
        except ClarificationPersistenceError as error:
            if str(error) == CLARIFICATION_MISSING_AFTER_UPSERT_REASON:
                print(
                    f"\033[31m[搜索澄清态写入后记录缺失]\033[0m chat_id={chat_id} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 clarification_state 表是否被并发删除或触发器回滚；"
                    "如需继续待澄清流程，请先确认 SQLite 写入后能立即回读该记录。",
                    flush=True,
                )
            elif str(error) == CLARIFICATION_QUERY_EMPTY_AFTER_READ_REASON:
                print(
                    f"\033[31m[搜索澄清态写入命中坏记录]\033[0m chat_id={chat_id} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 clarification_state.query 是否在写后被写成空值或脏数据；"
                    "当前会按待澄清状态写入失败处理，避免把坏记录误判成已成功进入待澄清状态。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[搜索澄清态持久化失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/clarification 表写入是否正常；当前进程内仍保留待澄清状态，但重启后可能丢失这次待确认查询。",
                    flush=True,
                )
            if previous_query:
                self._clarification_pending_by_chat[chat_id] = previous_query
            else:
                self._clarification_pending_by_chat.pop(chat_id, None)
            return False
        except Exception as error:
            print(
                f"\033[31m[搜索澄清态持久化失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/clarification 表写入是否正常；当前进程内仍保留待澄清状态，但重启后可能丢失这次待确认查询。",
                flush=True,
            )
            if previous_query:
                self._clarification_pending_by_chat[chat_id] = previous_query
            else:
                self._clarification_pending_by_chat.pop(chat_id, None)
            return False
        return True

    def _clear_clarification_pending(self, *, chat_id: int) -> bool:
        cleared = False
        previous_query = ""
        if chat_id in self._clarification_pending_by_chat:
            previous_query = self._clarification_pending_by_chat[chat_id]
            self._clarification_pending_by_chat.pop(chat_id, None)
            cleared = True
        if self._clarification_repo is None:
            return cleared
        try:
            cleared_result = self._clarification_repo.clear_pending(chat_id=chat_id)
            if cleared_result is None:
                raise ClarificationPersistenceError(CLARIFICATION_CLEAR_RESULT_MISSING_REASON)
            return cleared_result or cleared
        except Exception as error:
            if str(error) == CLARIFICATION_CLEAR_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[搜索澄清态清理结果缺失]\033[0m chat_id={chat_id} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 clarification 表删除返回是否仍带有明确结果；"
                    "当前进程内待澄清状态已清掉，但重启后旧查询可能仍残留。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[搜索澄清态清理失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/clarification 表删除是否正常；当前进程内待澄清状态已清掉，但重启后旧查询可能仍残留。",
                    flush=True,
                )
            if previous_query:
                self._clarification_pending_by_chat[chat_id] = previous_query
            return False

    def _load_persisted_clarification_query(self, *, chat_id: int) -> ClarificationQueryLoadResult:
        if self._clarification_repo is None:
            return ClarificationQueryLoadResult()
        try:
            return ClarificationQueryLoadResult(
                query=self._clarification_repo.get_pending_query(chat_id=chat_id),
            )
        except Exception as error:
            if str(error) == CLARIFICATION_QUERY_EMPTY_AFTER_READ_REASON:
                print(
                    f"\033[31m[搜索澄清态记录损坏]\033[0m chat_id={chat_id} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 clarification_state.query 是否被写成空值或脏数据；"
                    "当前相关入口会按状态不可用处理，避免把坏记录误判成“无待澄清记录”。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[搜索澄清态读取失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/clarification 表读取是否正常；当前相关入口会按状态不可用处理，避免把持久化异常误判成“无待澄清记录”。",
                    flush=True,
                )
            return ClarificationQueryLoadResult(load_failed=True)

    def _load_persisted_candidate(self, *, chat_id: int, index: int) -> CandidateLoadResult:
        if self._candidate_repo is None:
            return CandidateLoadResult()
        try:
            return CandidateLoadResult(candidate=self._candidate_repo.get_candidate(chat_id, index))
        except CandidatePayloadCorruptionError as error:
            print(
                f"\033[31m[搜索候选载荷损坏]\033[0m chat_id={chat_id} index={index} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/candidate_mapping 表里的 candidate_json 是否仍是合法 JSON；当前相关入口会按候选读取失败或状态不可用处理，避免把持久化坏数据误判成“无候选”。",
                flush=True,
            )
            return CandidateLoadResult(load_failed=True)
        except Exception as error:
            print(
                f"\033[31m[搜索候选读取失败]\033[0m chat_id={chat_id} index={index} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表读取是否正常；当前相关入口会按候选读取失败或状态不可用处理，避免把持久化异常误判成“无候选”。",
                flush=True,
            )
            return CandidateLoadResult(load_failed=True)

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


def build_search_results_delivery_item(
    *,
    query: str,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
    candidates: Sequence[Candidate],
) -> DeliveryItem:
    if not candidates:
        raise ValueError("search results delivery requires at least one candidate")
    card_title, card_year, card_alias = _resolve_movie_card_fields(parsed_query, tmdb_movie)
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


def format_bt_read_only_reply(query: str, candidates: Sequence[Mapping[str, Any]]) -> str:
    if not candidates:
        return BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE.format(query=query)

    lines = [f"BT 只读探索结果：{query}"]
    for index, item in enumerate(candidates, start=1):
        title = _safe_text(item.get("title"), default="(no title)")
        indexer = _safe_indexer(item.get("indexer"), item.get("indexerName"))
        provider = _safe_text(item.get("sourceProvider"), default=indexer)
        seeders = _format_seeder_count(item.get("seeders"))
        size = _format_size(item.get("size"))
        lines.append(f"{index}. {title}")
        lines.append(f"   站点: {indexer} | 来源入口: {provider} | 做种: {seeders} | 大小: {size}")
        lines.append(f"   链接参考: {_format_bt_source_reference(item)}")
    lines.append(BT_READ_ONLY_NOTICE_TEXT)
    return "\n".join(lines)


def format_bt_batch_preview_reply(
    query: str,
    candidates: Sequence[Mapping[str, Any]],
    *,
    selection_label: str,
) -> str:
    if not candidates:
        return BT_BATCH_PREVIEW_NO_RESULT_TEXT_TEMPLATE.format(query=query)

    lines = [f"BT 批量预览结果：{query}"]
    for index, item in enumerate(candidates, start=1):
        title = _safe_text(item.get("title"), default="(no title)")
        indexer = _safe_indexer(item.get("indexer"), item.get("indexerName"))
        provider = _safe_text(item.get("sourceProvider"), default=indexer)
        seeders = _format_seeder_count(item.get("seeders"))
        size = _format_size(item.get("size"))
        lines.append(f"{index}. {title}")
        lines.append(f"   站点: {indexer} | 来源入口: {provider} | 做种: {seeders} | 大小: {size}")
        lines.append(f"   链接参考: {_format_bt_source_reference(item)}")
    lines.append(BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection=selection_label))
    return "\n".join(lines)


def format_movie_poster_card(parsed_query: ParsedMovieQuery, tmdb_movie: TmdbMovie | None) -> str:
    card_title, card_year, card_alias = _resolve_movie_card_fields(parsed_query, tmdb_movie)
    lines = [
        "电影海报卡片",
        f"片名: {card_title}",
        f"年份: {card_year}",
        f"别名: {card_alias}",
        "海报: 暂未接入图片",
    ]
    return "\n".join(lines)


def _resolve_movie_card_fields(parsed_query: ParsedMovieQuery, tmdb_movie: TmdbMovie | None) -> tuple[str, str, str]:
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


def _safe_text(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text


def _format_bt_batch_preview_selection_label(selected_indexes: Sequence[int]) -> str:
    if not selected_indexes:
        return "-"
    return ",".join(str(index) for index in selected_indexes)


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

    ordered_results: list[Mapping[str, Any]] = []
    for scored_candidate in filter_candidates(
        [candidate for candidate, _ in candidate_pairs],
        BTScoringContext(query=query, media_kind="movie"),
        rules=load_bt_scoring_rules(),
    ):
        for candidate, item in candidate_pairs:
            if candidate is scored_candidate.candidate:
                ordered_results.append(item)
                break
    ordered_results.extend(remainder)
    return tuple(ordered_results)


def _build_media_bt_candidate(item: Mapping[str, Any]) -> BTCandidate | None:
    source = resolve_bt_source(item)
    title = _safe_text(item.get("title"), default="")
    if not source or not title:
        return None
    return BTCandidate(
        source_site=_safe_indexer(item.get("indexer"), item.get("indexerName")),
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


def _format_seeder_count(value: Any) -> str:
    if value is None:
        return "-"
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return "-"
    if resolved < 0:
        return "-"
    return str(resolved)


def _format_bt_source_reference(item: Mapping[str, Any]) -> str:
    source = _safe_text(item.get("source"), default="-")
    if source == "-":
        return source

    info_hash = _safe_text(item.get("infoHash"), default="")
    if source.lower().startswith("magnet:?"):
        if info_hash:
            return f"magnet | infoHash={info_hash}"
        return _truncate_text(source, limit=96)

    return _truncate_text(source, limit=96)


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


def _truncate_text(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return f"{value[: limit - 3]}..."


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
