from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from app.db.clarification_repo import ClarificationPersistenceError, ClarificationRepo
from app.operational_logging import format_operational_log_message

CLARIFICATION_MISSING_AFTER_UPSERT_REASON = "clarification_state missing after upsert"
CLARIFICATION_CLEAR_RESULT_MISSING_REASON = "clarification clear result missing"
CLARIFICATION_QUERY_EMPTY_AFTER_READ_REASON = "clarification_state query empty after read"


@dataclass(frozen=True, slots=True)
class ClarificationQueryLoadResult:
    query: str | None = None
    load_failed: bool = False


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
                print(
                    format_operational_log_message(
                        title="搜索澄清态清理结果缺失",
                        detail=f"chat_id={chat_id} 错误={error}",
                        fix_hint=(
                            "检查 clarification 表删除返回是否仍带有明确结果；"
                            "当前进程内待澄清状态已清掉，但重启后旧查询可能仍残留。"
                        ),
                    ),
                    flush=True,
                )
            else:
                print(
                    format_operational_log_message(
                        title="搜索澄清态清理失败",
                        detail=f"chat_id={chat_id} 错误={error}",
                        fix_hint="检查 SQLite/clarification 表删除是否正常；当前进程内待澄清状态已清掉，但重启后旧查询可能仍残留。",
                    ),
                    flush=True,
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
                print(
                    format_operational_log_message(
                        title="搜索澄清态写入后记录缺失",
                        detail=f"chat_id={chat_id} 错误={error}",
                        fix_hint=(
                            "检查 clarification_state 表是否被并发删除或触发器回滚；"
                            "如需继续待澄清流程，请先确认 SQLite 写入后能立即回读该记录。"
                        ),
                    ),
                    flush=True,
                )
            elif str(error) == CLARIFICATION_QUERY_EMPTY_AFTER_READ_REASON:
                print(
                    format_operational_log_message(
                        title="搜索澄清态写入命中坏记录",
                        detail=f"chat_id={chat_id} 错误={error}",
                        fix_hint=(
                            "检查 clarification_state.query 是否在写后被写成空值或脏数据；"
                            "当前会按待澄清状态写入失败处理，避免把坏记录误判成已成功进入待澄清状态。"
                        ),
                    ),
                    flush=True,
                )
            else:
                print(
                    format_operational_log_message(
                        title="搜索澄清态持久化失败",
                        detail=f"chat_id={chat_id} 错误={error}",
                        fix_hint="检查 SQLite/clarification 表写入是否正常；当前进程内仍保留待澄清状态，但重启后可能丢失这次待确认查询。",
                    ),
                    flush=True,
                )
            if previous_query:
                self.pending_by_chat[chat_id] = previous_query
            else:
                self.pending_by_chat.pop(chat_id, None)
            return False
        except sqlite3.Error as error:
            print(
                format_operational_log_message(
                    title="搜索澄清态持久化失败",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint="检查 SQLite/clarification 表写入是否正常；当前进程内仍保留待澄清状态，但重启后可能丢失这次待确认查询。",
                ),
                flush=True,
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
            return ClarificationQueryLoadResult(
                query=self.repo.get_pending_query(chat_id=chat_id),
            )
        except (ClarificationPersistenceError, sqlite3.Error) as error:
            if str(error) == CLARIFICATION_QUERY_EMPTY_AFTER_READ_REASON:
                print(
                    format_operational_log_message(
                        title="搜索澄清态记录损坏",
                        detail=f"chat_id={chat_id} 错误={error}",
                        fix_hint=(
                            "检查 clarification_state.query 是否被写成空值或脏数据；"
                            "当前相关入口会按状态不可用处理，避免把坏记录误判成“无待澄清记录”。"
                        ),
                    ),
                    flush=True,
                )
            else:
                print(
                    format_operational_log_message(
                        title="搜索澄清态读取失败",
                        detail=f"chat_id={chat_id} 错误={error}",
                        fix_hint="检查 SQLite/clarification 表读取是否正常；当前相关入口会按状态不可用处理，避免把持久化异常误判成“无待澄清记录”。",
                    ),
                    flush=True,
                )
            return ClarificationQueryLoadResult(load_failed=True)
