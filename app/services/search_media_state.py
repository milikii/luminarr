from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.db.candidate_repo import CandidateMappingRepo, CandidatePayloadCorruptionError, CandidatePersistenceError
from app.db.clarification_repo import ClarificationPersistenceError, ClarificationRepo
from app.operational_logging import emit_operational_log

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
        except (CandidatePersistenceError, sqlite3.Error, RuntimeError) as error:
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
        except (CandidatePersistenceError, sqlite3.Error, RuntimeError) as error:
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
        except (CandidatePersistenceError, sqlite3.Error, RuntimeError) as error:
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
        except (ClarificationPersistenceError, sqlite3.Error, RuntimeError) as error:
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
