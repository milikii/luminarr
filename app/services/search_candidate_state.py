from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.db.candidate_repo import CandidateMappingRepo, CandidatePayloadCorruptionError, CandidatePersistenceError

CANDIDATE_COUNT_RESULT_MISSING_AFTER_SAVE_REASON = "candidate_mapping count missing after query"
CANDIDATE_COUNT_MISMATCH_AFTER_SAVE_REASON = "candidate_mapping count mismatch after save"
CANDIDATE_CLEAR_RESULT_MISSING_REASON = "candidate clear result missing"
CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON = "candidate clear result missing during persist rollback"


@dataclass(frozen=True, slots=True)
class CandidateLoadResult:
    candidate: Mapping[str, Any] | None = None
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
        except Exception as error:
            print(
                f"\033[31m[BT 批量预览候选持久化失败]\033[0m chat_id={chat_id} 错误={error}\n"
                "\033[33m[处理建议]\033[0m 检查 SQLite/candidate_mapping 写入是否正常；"
                "当前会直接返回候选状态写入失败，避免把坏候选继续暴露给批量确认入口。",
                flush=True,
            )
            self.recent_by_chat.pop(chat_id, None)
            try:
                cleared_result = self.repo.clear_candidates(chat_id)
                if cleared_result is None:
                    raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON)
            except Exception as rollback_error:
                print(
                    f"\033[31m[BT 批量预览候选清理失败]\033[0m chat_id={chat_id} 错误={rollback_error}\n"
                    "\033[33m[处理建议]\033[0m 检查 SQLite/candidate_mapping 删除是否正常；"
                    "当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                    flush=True,
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
            self.recent_by_chat.pop(chat_id, None)
            self._rollback_failed_persist(chat_id=chat_id)
            return False
        except Exception as error:
            print(
                f"\033[31m[搜索候选持久化失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表写入是否正常；当前会直接返回候选状态写入失败，避免把持久化真相缺口混成仍可继续按序号选择的候选缓存。",
                flush=True,
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
                self.recent_by_chat[chat_id] = list(previous_candidates)
            return False

    def load_persisted_candidate(self, *, chat_id: int, index: int) -> CandidateLoadResult:
        if self.repo is None:
            return CandidateLoadResult()
        try:
            return CandidateLoadResult(candidate=self.repo.get_candidate(chat_id, index))
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

    def _rollback_failed_persist(self, *, chat_id: int) -> None:
        if self.repo is None:
            return
        try:
            cleared_result = self.repo.clear_candidates(chat_id)
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
