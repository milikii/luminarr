from __future__ import annotations

import re
import sqlite3
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.clients.web_source import (
    looks_like_http_url,
    looks_like_web_source_page_request,
    resolve_supported_web_source_page_request,
)
from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.db.candidate_repo import CandidateMappingRepo, CandidatePayloadCorruptionError, CandidatePersistenceError
from app.db.clarification_repo import ClarificationPersistenceError, ClarificationRepo
from app.search_title_normalization import BT_RESULT_TITLE_NOISE_TOKENS, compact_match_key, normalize_match_key, normalize_spaces
from app.services.bt_read_only_display import AdultReadOnlyLookupFunc, BtReadOnlyDisplayService
from app.services import search_reply_formatter
from app.services.bt_candidate_scorer import BTCandidate, BTScoringContext, filter_candidates
from app.services.bt_sources import resolve_bt_source
from app.services.media_identity import build_media_identity_from_tmdb_movie, normalize_media_identity_payload
from app.operational_logging import emit_operational_log
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
from app.services.search_query_parser import parse_movie_query
from app.services.search_request_context import (
    LookupMovieFunc,
    SearchFunc,
    build_search_request_context,
)
from app.services.bt_candidate_scorer import load_bt_scoring_rules as _load_bt_scoring_rules
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

BatchPreviewSearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
PrepareRawCandidatesFunc = Callable[[Sequence[Mapping[str, Any]], str], Sequence[Mapping[str, Any]]]
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
load_bt_scoring_rules = _load_bt_scoring_rules


class UnsupportedBatchPreviewPageUrl(ValueError):
    pass


CANDIDATE_COUNT_RESULT_MISSING_AFTER_SAVE_REASON = "candidate_mapping count missing after query"
CANDIDATE_COUNT_MISMATCH_AFTER_SAVE_REASON = "candidate_mapping count mismatch after save"
CANDIDATE_CLEAR_RESULT_MISSING_REASON = "candidate clear result missing"
CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON = "candidate clear result missing during persist rollback"
CLARIFICATION_MISSING_AFTER_UPSERT_REASON = "clarification_state missing after upsert"
CLARIFICATION_CLEAR_RESULT_MISSING_REASON = "clarification clear result missing"
CLARIFICATION_QUERY_EMPTY_AFTER_READ_REASON = "clarification_state query empty after read"


def _log_candidate_state_error(*, title: str, detail: str, fix_hint: str) -> None:
    emit_operational_log(title=title, detail=detail, fix_hint=fix_hint)


def _log_clarification_state_error(*, title: str, detail: str, fix_hint: str) -> None:
    emit_operational_log(title=title, detail=detail, fix_hint=fix_hint)


@dataclass(frozen=True, slots=True)
class CandidateLoadResult:
    candidate: Mapping[str, Any] | None = None
    load_failed: bool = False


@dataclass(frozen=True, slots=True)
class ClarificationQueryLoadResult:
    query: str | None = None
    load_failed: bool = False


@dataclass(frozen=True, slots=True)
class AmbiguousOption:
    title: str
    year: str


@dataclass(slots=True)
class CandidateStateStore:
    repo: CandidateMappingRepo | None = None
    recent_by_chat: dict[int, list[dict[str, Any]]] = field(default_factory=dict)

    def persist_bt_batch_preview_candidates(self, *, chat_id: int, candidates: list[dict[str, Any]]) -> bool:
        self.recent_by_chat[chat_id] = candidates
        if self.repo is None:
            return True
        try:
            self.repo.save_candidates(chat_id, candidates)
        except (CandidatePersistenceError, sqlite3.Error) as error:
            _log_candidate_state_error(
                title="BT 批量预览候选持久化失败",
                detail=f"chat_id={chat_id} 错误={error}",
                fix_hint=(
                    "检查 SQLite/candidate_mapping 写入是否正常；"
                    "当前会直接返回候选状态写入失败，避免把坏候选继续暴露给批量确认入口。"
                ),
            )
            self.recent_by_chat.pop(chat_id, None)
            try:
                cleared_result = self.repo.clear_candidates(chat_id)
                if cleared_result is None:
                    raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON)
            except (CandidatePersistenceError, sqlite3.Error) as rollback_error:
                _log_candidate_state_error(
                    title="BT 批量预览候选清理失败",
                    detail=f"chat_id={chat_id} 错误={rollback_error}",
                    fix_hint=(
                        "检查 SQLite/candidate_mapping 删除是否正常；"
                        "当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。"
                    ),
                )
            return False
        return True

    def persist_search_candidates(self, *, chat_id: int, candidates: list[dict[str, Any]]) -> bool:
        self.recent_by_chat[chat_id] = candidates
        if self.repo is None:
            return True
        try:
            self.repo.save_candidates(chat_id, candidates)
        except CandidatePersistenceError as error:
            if str(error) == CANDIDATE_COUNT_RESULT_MISSING_AFTER_SAVE_REASON:
                _log_candidate_state_error(
                    title="搜索候选写入结果缺失",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint=(
                        "检查 candidate_mapping 写入后的计数查询是否仍带有完整结果；"
                        "当前会直接返回候选状态写入失败，避免把缺失真相误判成仍可继续按序号选择的候选缓存。"
                    ),
                )
            elif str(error) == CANDIDATE_COUNT_MISMATCH_AFTER_SAVE_REASON:
                _log_candidate_state_error(
                    title="搜索候选写入后记录不一致",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint=(
                        "检查 candidate_mapping 表是否被并发删除或部分回滚；"
                        "如需继续按序号选择，请先确认 SQLite 写入后条目数和预期一致。"
                    ),
                )
            else:
                _log_candidate_state_error(
                    title="搜索候选持久化失败",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint="检查 SQLite/候选表写入是否正常；当前会直接返回候选状态写入失败，避免把持久化真相缺口混成仍可继续按序号选择的候选缓存。",
                )
            self.recent_by_chat.pop(chat_id, None)
            self._rollback_failed_persist(chat_id=chat_id)
            return False
        except (CandidatePersistenceError, sqlite3.Error) as error:
            _log_candidate_state_error(
                title="搜索候选持久化失败",
                detail=f"chat_id={chat_id} 错误={error}",
                fix_hint="检查 SQLite/候选表写入是否正常；当前会直接返回候选状态写入失败，避免把持久化真相缺口混成仍可继续按序号选择的候选缓存。",
            )
            self.recent_by_chat.pop(chat_id, None)
            self._rollback_failed_persist(chat_id=chat_id)
            return False
        return True

    def get_cached_candidate_load_result(self, chat_id: int, index: int) -> CandidateLoadResult:
        if index < 1:
            return CandidateLoadResult()
        candidates = self.recent_by_chat.get(chat_id)
        resolved_index = index - 1
        if candidates and resolved_index < len(candidates):
            return CandidateLoadResult(candidate=candidates[resolved_index])
        return self.load_persisted_candidate(chat_id=chat_id, index=index)

    def has_cached_candidates(self, chat_id: int) -> bool | None:
        if chat_id <= 0:
            return False
        candidates = self.recent_by_chat.get(chat_id)
        if candidates:
            return True
        load_result = self.load_persisted_candidate(chat_id=chat_id, index=1)
        if load_result.load_failed:
            return None
        return load_result.candidate is not None

    def clear_cached_candidates(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False

        cleared = False
        previous_candidates: Sequence[Mapping[str, Any]] | None = None
        if chat_id in self.recent_by_chat:
            previous_candidates = tuple(self.recent_by_chat[chat_id])
            self.recent_by_chat.pop(chat_id, None)
            cleared = True

        if self.repo is None:
            return cleared
        try:
            cleared_result = self.repo.clear_candidates(chat_id)
            if cleared_result is None:
                raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_REASON)
            return cleared_result or cleared
        except (CandidatePersistenceError, sqlite3.Error) as error:
            if str(error) == CANDIDATE_CLEAR_RESULT_MISSING_REASON:
                _log_candidate_state_error(
                    title="搜索候选清理结果缺失",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint=(
                        "检查 candidate_mapping 删除返回是否仍带有明确结果；"
                        "当前进程内候选已清掉，但重启后旧候选可能仍残留。"
                    ),
                )
            else:
                _log_candidate_state_error(
                    title="搜索候选清理失败",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint="检查 SQLite/候选表删除是否正常；当前进程内候选已清掉，但重启后旧候选可能仍残留。",
                )
            if previous_candidates is not None:
                self.recent_by_chat[chat_id] = list(previous_candidates)
            return False

    def load_persisted_candidate(self, *, chat_id: int, index: int) -> CandidateLoadResult:
        if self.repo is None:
            return CandidateLoadResult()
        try:
            return CandidateLoadResult(candidate=self.repo.get_candidate(chat_id, index))
        except CandidatePayloadCorruptionError as error:
            _log_candidate_state_error(
                title="搜索候选载荷损坏",
                detail=f"chat_id={chat_id} index={index} 错误={error}",
                fix_hint="检查 SQLite/candidate_mapping 表里的 candidate_json 是否仍是合法 JSON；当前相关入口会按候选读取失败或状态不可用处理，避免把持久化坏数据误判成“无候选”。",
            )
            return CandidateLoadResult(load_failed=True)
        except (CandidatePersistenceError, sqlite3.Error) as error:
            _log_candidate_state_error(
                title="搜索候选读取失败",
                detail=f"chat_id={chat_id} index={index} 错误={error}",
                fix_hint="检查 SQLite/候选表读取是否正常；当前相关入口会按候选读取失败或状态不可用处理，避免把持久化异常误判成“无候选”。",
            )
            return CandidateLoadResult(load_failed=True)

    def _rollback_failed_persist(self, *, chat_id: int) -> None:
        if self.repo is None:
            return
        try:
            cleared_result = self.repo.clear_candidates(chat_id)
            if cleared_result is None:
                raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON)
        except (CandidatePersistenceError, sqlite3.Error) as rollback_error:
            if str(rollback_error) == CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON:
                _log_candidate_state_error(
                    title="搜索候选回滚清理结果缺失",
                    detail=f"chat_id={chat_id} 错误={rollback_error}",
                    fix_hint=(
                        "检查 candidate_mapping 回滚删除返回是否仍带有明确结果；"
                        "当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。"
                    ),
                )
            else:
                _log_candidate_state_error(
                    title="搜索候选清理失败",
                    detail=f"chat_id={chat_id} 错误={rollback_error}",
                    fix_hint="检查 SQLite/候选表删除是否正常；当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                )


@dataclass(slots=True)
class ClarificationStateStore:
    repo: ClarificationRepo | None = None
    pending_by_chat: dict[int, str] = field(default_factory=dict)

    def is_pending(self, chat_id: int) -> bool | None:
        if chat_id <= 0:
            return False
        if chat_id in self.pending_by_chat:
            return True
        load_result = self.load_persisted_query(chat_id=chat_id)
        if load_result.load_failed:
            return None
        if load_result.query is None:
            return False
        self.pending_by_chat[chat_id] = load_result.query
        return True

    def clear_pending(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False

        cleared = False
        previous_query = ""
        if chat_id in self.pending_by_chat:
            previous_query = self.pending_by_chat[chat_id]
            self.pending_by_chat.pop(chat_id, None)
            cleared = True
        if self.repo is None:
            return cleared
        try:
            cleared_result = self.repo.clear_pending(chat_id=chat_id)
            if cleared_result is None:
                raise ClarificationPersistenceError(CLARIFICATION_CLEAR_RESULT_MISSING_REASON)
            return cleared_result or cleared
        except (ClarificationPersistenceError, sqlite3.Error) as error:
            if str(error) == CLARIFICATION_CLEAR_RESULT_MISSING_REASON:
                _log_clarification_state_error(
                    title="搜索澄清态清理结果缺失",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint=(
                        "检查 clarification 表删除返回是否仍带有明确结果；"
                        "当前进程内待澄清状态已清掉，但重启后旧查询可能仍残留。"
                    ),
                )
            else:
                _log_clarification_state_error(
                    title="搜索澄清态清理失败",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint="检查 SQLite/clarification 表删除是否正常；当前进程内待澄清状态已清掉，但重启后旧查询可能仍残留。",
                )
            if previous_query:
                self.pending_by_chat[chat_id] = previous_query
            return False

    def set_pending(self, *, chat_id: int, query: str) -> bool:
        if chat_id <= 0:
            return False
        previous_query = self.pending_by_chat.get(chat_id, "")
        self.pending_by_chat[chat_id] = query
        if self.repo is None:
            return True
        try:
            self.repo.upsert_pending(chat_id=chat_id, query=query)
        except ClarificationPersistenceError as error:
            if str(error) == CLARIFICATION_MISSING_AFTER_UPSERT_REASON:
                _log_clarification_state_error(
                    title="搜索澄清态写入后记录缺失",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint=(
                        "检查 clarification_state 表是否被并发删除或触发器回滚；"
                        "如需继续待澄清流程，请先确认 SQLite 写入后能立即回读该记录。"
                    ),
                )
            elif str(error) == CLARIFICATION_QUERY_EMPTY_AFTER_READ_REASON:
                _log_clarification_state_error(
                    title="搜索澄清态写入命中坏记录",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint=(
                        "检查 clarification_state.query 是否在写后被写成空值或脏数据；"
                        "当前会按待澄清状态写入失败处理，避免把坏记录误判成已成功进入待澄清状态。"
                    ),
                )
            else:
                _log_clarification_state_error(
                    title="搜索澄清态持久化失败",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint="检查 SQLite/clarification 表写入是否正常；当前进程内仍保留待澄清状态，但重启后可能丢失这次待确认查询。",
                )
            if previous_query:
                self.pending_by_chat[chat_id] = previous_query
            else:
                self.pending_by_chat.pop(chat_id, None)
            return False
        except sqlite3.Error as error:
            _log_clarification_state_error(
                title="搜索澄清态持久化失败",
                detail=f"chat_id={chat_id} 错误={error}",
                fix_hint="检查 SQLite/clarification 表写入是否正常；当前进程内仍保留待澄清状态，但重启后可能丢失这次待确认查询。",
            )
            if previous_query:
                self.pending_by_chat[chat_id] = previous_query
            else:
                self.pending_by_chat.pop(chat_id, None)
            return False
        return True

    def load_persisted_query(self, *, chat_id: int) -> ClarificationQueryLoadResult:
        if self.repo is None:
            return ClarificationQueryLoadResult()
        try:
            return ClarificationQueryLoadResult(query=self.repo.get_pending_query(chat_id=chat_id))
        except (ClarificationPersistenceError, sqlite3.Error) as error:
            if str(error) == CLARIFICATION_QUERY_EMPTY_AFTER_READ_REASON:
                _log_clarification_state_error(
                    title="搜索澄清态记录损坏",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint=(
                        "检查 clarification_state.query 是否被写成空值或脏数据；"
                        "当前相关入口会按状态不可用处理，避免把坏记录误判成“无待澄清记录”。"
                    ),
                )
            else:
                _log_clarification_state_error(
                    title="搜索澄清态读取失败",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint="检查 SQLite/clarification 表读取是否正常；当前相关入口会按状态不可用处理，避免把持久化异常误判成“无待澄清记录”。",
                )
            return ClarificationQueryLoadResult(load_failed=True)


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
    except (httpx.HTTPError, ValueError) as error:
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
        except (httpx.HTTPError, ValueError) as error:
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
            load_bt_scoring_rules_func=_load_bt_scoring_rules,
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


def format_ambiguous_clarification(
    *,
    query: str,
    parsed_query: Any,
    raw_results: Sequence[Mapping[str, Any]],
) -> str | None:
    if str(parsed_query.year).strip():
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
        if not key[0] or key in seen_keys:
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


def order_media_bt_results(
    raw_results: Sequence[Mapping[str, Any]],
    *,
    query: str,
    load_bt_scoring_rules_func: Callable[[], Any] | None = None,
) -> Sequence[Mapping[str, Any]]:
    if load_bt_scoring_rules_func is None:
        load_bt_scoring_rules_func = load_bt_scoring_rules
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
        rules=load_bt_scoring_rules_func(),
    )
    if all(scored_candidate.drop_reason == "title_mismatch" for scored_candidate in scored_candidates):
        fallback_queries = _derive_media_title_fallback_queries(raw_results, query=query)
        best_fallback_metrics: tuple[int, float, float] | None = None
        best_rescored_candidates: Sequence[Any] | None = None
        for fallback_query in fallback_queries:
            rescored_candidates = filter_candidates(
                [candidate for candidate, _ in candidate_pairs],
                BTScoringContext(query=fallback_query, media_kind="movie"),
                rules=load_bt_scoring_rules_func(),
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
        if scored_candidate.drop_reason is not None:
            continue
        for candidate, item in candidate_pairs:
            if candidate is scored_candidate.candidate:
                ordered_results.append(item)
                break
    if not ordered_results:
        return ()
    ordered_results.extend(remainder)
    return tuple(_dedupe_media_bt_results_by_title(ordered_results))


def _dedupe_media_bt_results_by_title(results: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    deduped_results: list[Mapping[str, Any]] = []
    seen_titles: set[str] = set()
    for item in results:
        title_key = _media_bt_result_dedupe_key(item)
        if title_key:
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
        deduped_results.append(item)
    return deduped_results


def _media_bt_result_dedupe_key(item: Mapping[str, Any]) -> str:
    title = normalize_spaces(safe_text(item.get("title"), default=""))
    if not title:
        return ""
    normalized_title = _normalize_media_bt_title_for_dedupe(title)
    if not normalized_title:
        return title.lower()
    resolution = _extract_resolution_token(title)
    if not resolution:
        return normalized_title
    return f"{normalized_title}|{resolution}"


def _normalize_media_bt_title_for_dedupe(title: str) -> str:
    cleaned_title = re.sub(r"-[A-Za-z0-9][A-Za-z0-9-]*$", "", title.strip())
    normalized_title = normalize_match_key(cleaned_title)
    if not normalized_title:
        return ""
    filtered_tokens: list[str] = []
    stopwords = BT_RESULT_TITLE_NOISE_TOKENS | {"2audio", "gbr", "usa", "jpn", "fra"}
    for token in normalized_title.split():
        if re.fullmatch(r"(?:19|20)\d{2}", token):
            continue
        if token in stopwords:
            continue
        filtered_tokens.append(token)
    return compact_match_key(" ".join(filtered_tokens))


def _extract_resolution_token(title: str) -> str:
    match = re.search(r"\b(2160p|4k|1080p|720p|480p)\b", title, flags=re.IGNORECASE)
    if match is None:
        return ""
    token = str(match.group(1) or "").lower()
    if token == "4k":
        return "2160p"
    return token


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
    normalized = re.sub(r"\b\d\.\d\b", " ", title.strip(), flags=re.IGNORECASE)
    normalized = normalize_match_key(normalized)
    raw_tokens = [token for token in normalized.split() if token]
    stopwords = BT_RESULT_TITLE_NOISE_TOKENS | {"max"}
    has_part_two_marker = re.search(r"\bpart\s+(?:two|ii|2)\b", title, flags=re.IGNORECASE) is not None
    tokens: list[str] = []
    for index, token in enumerate(raw_tokens):
        if token in stopwords or re.fullmatch(r"(?:19|20)\d{2}", token):
            continue
        if token == "2" and has_part_two_marker:
            tokens.extend(("part", "two"))
            has_part_two_marker = False
            continue
        if token == "2" and index > 0 and raw_tokens[index - 1] == "part":
            tokens.append("two")
            continue
        tokens.append(token)
    return tokens


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
    if "webrip" in lowered_title:
        return "WEBRip"
    if "web-dl" in lowered_title or "webdl" in lowered_title:
        return "WEB-DL"
    if "hdtv" in lowered_title:
        return "HDTV"
    if "dvdrip" in lowered_title:
        return "DVDRip"
    return None


def _extract_release_group(title: str) -> str | None:
    match = re.search(r"-([A-Za-z0-9][A-Za-z0-9-]+)$", title.strip())
    if match is None:
        return None
    return str(match.group(1) or "").strip() or None


def _safe_optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
