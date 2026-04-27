from __future__ import annotations

import sqlite3
import re
from dataclasses import dataclass

from app.db.watchlist_repo import WatchlistPersistenceError, WatchlistRepo
from app.services.search_request_context import parse_movie_query

WATCHLIST_USAGE_TEXT = (
    "想看命令格式：\n"
    "watchlist list\n"
    "watchlist add <片名 [年份]>\n"
    "watchlist add <movie|series|anime> <片名 [年份]>\n"
    "watchlist remove <条目ID>\n"
    "watchlist clear"
)
WATCHLIST_EMPTY_TEXT = "想看清单为空。"
WATCHLIST_LIST_FAILED_TEXT = "想看清单读取失败，请稍后重试。"
WATCHLIST_ADD_USAGE_TEXT = (
    "添加格式：watchlist add <片名 [年份]>\n"
    "或：watchlist add <movie|series|anime> <片名 [年份]>"
)
WATCHLIST_ADD_FAILED_TEXT = "想看写入失败，请稍后重试。"
WATCHLIST_REMOVE_USAGE_TEXT = "删除格式：watchlist remove <条目ID>"
WATCHLIST_REMOVE_FAILED_TEXT = "想看删除失败，请稍后重试。"
WATCHLIST_CLEAR_EMPTY_TEXT = "想看清单本来就是空的。"
WATCHLIST_CLEAR_FAILED_TEXT = "想看清单清空失败，请稍后重试。"
MEDIA_KIND_ALIASES = {
    "movie": "movie",
    "film": "movie",
    "电影": "movie",
    "series": "series",
    "tv": "series",
    "show": "series",
    "电视剧": "series",
    "剧集": "series",
    "anime": "anime",
    "动漫": "anime",
    "动画": "anime",
}
MEDIA_KIND_LABELS = {
    "movie": "电影",
    "series": "剧集",
    "anime": "动漫",
}
WATCHLIST_ITEM_MISSING_AFTER_ADD_REASON = "watchlist_item missing after insert"
WATCHLIST_ADD_RESULT_MISSING_REASON = "watchlist add result missing"


@dataclass(frozen=True, slots=True)
class WatchlistCommand:
    action: str
    arg: str


class ManageWatchlistService:
    def __init__(self, watchlist_repo: WatchlistRepo) -> None:
        self._watchlist_repo = watchlist_repo

    def handle(self, command: WatchlistCommand, *, chat_id: int | None) -> str:
        if chat_id is None or chat_id <= 0:
            return WATCHLIST_USAGE_TEXT

        if command.action == "list":
            return self._list_text(chat_id=chat_id)
        if command.action == "add":
            return self._add_text(chat_id=chat_id, raw_title=command.arg)
        if command.action == "remove":
            return self._remove_text(chat_id=chat_id, item_ref=command.arg)
        if command.action == "clear":
            return self._clear_text(chat_id=chat_id)
        return WATCHLIST_USAGE_TEXT

    def _list_text(self, *, chat_id: int) -> str:
        items = self._list_items(chat_id=chat_id)
        if items is None:
            return WATCHLIST_LIST_FAILED_TEXT
        if not items:
            return WATCHLIST_EMPTY_TEXT

        lines = ["想看清单："]
        for index, item in enumerate(items, start=1):
            year_text = item.year if item.year else "-"
            lines.append(
                f"{index}. [{item.item_id}] {item.title} ({year_text}) | 类型: {_media_kind_label(item.media_kind)}"
            )
        return "\n".join(lines)

    def _add_text(self, *, chat_id: int, raw_title: str) -> str:
        cleaned_title = raw_title.strip()
        if not cleaned_title:
            return WATCHLIST_ADD_USAGE_TEXT

        media_kind, parsed_title = _parse_media_kind_prefix(cleaned_title)
        parsed = parse_movie_query(parsed_title)
        title = parsed.title.strip()
        year = parsed.year.strip()
        if not title:
            return WATCHLIST_ADD_USAGE_TEXT

        created = self._add_item(
            chat_id=chat_id,
            title=title,
            year=year,
            media_kind=media_kind,
        )
        if created is None:
            return WATCHLIST_ADD_FAILED_TEXT
        item, is_created = created
        year_text = item.year if item.year else "-"
        kind_text = _media_kind_label(item.media_kind)
        if is_created:
            return f"已加入想看：{item.title} ({year_text})\n类型: {kind_text}\n条目ID: {item.item_id}"
        return f"想看已存在：{item.title} ({year_text})\n类型: {kind_text}\n条目ID: {item.item_id}"

    def _remove_text(self, *, chat_id: int, item_ref: str) -> str:
        cleaned_ref = item_ref.strip()
        if not cleaned_ref.isdigit():
            return WATCHLIST_REMOVE_USAGE_TEXT
        item_id = int(cleaned_ref)
        if item_id <= 0:
            return WATCHLIST_REMOVE_USAGE_TEXT
        removed = self._remove_item(chat_id=chat_id, item_id=item_id)
        if removed is None:
            return WATCHLIST_REMOVE_FAILED_TEXT
        if not removed:
            return "未找到对应想看条目。"
        return f"已删除想看条目：{item_id}"

    def _clear_text(self, *, chat_id: int) -> str:
        deleted = self._clear_items(chat_id=chat_id)
        if deleted is None:
            return WATCHLIST_CLEAR_FAILED_TEXT
        if deleted <= 0:
            return WATCHLIST_CLEAR_EMPTY_TEXT
        return f"已清空想看清单，共删除 {deleted} 条。"

    def _add_item(
        self,
        *,
        chat_id: int,
        title: str,
        year: str,
        media_kind: str,
    ):
        try:
            created = self._watchlist_repo.add_item(
                chat_id=chat_id,
                title=title,
                year=year,
                media_kind=media_kind,
            )
            if created is None:
                raise WatchlistPersistenceError(WATCHLIST_ADD_RESULT_MISSING_REASON)
        except WatchlistPersistenceError as error:
            if str(error) == WATCHLIST_ITEM_MISSING_AFTER_ADD_REASON:
                _log_watchlist_add_item_missing_after_insert(
                    chat_id=chat_id,
                    title=title,
                    year=year,
                    media_kind=media_kind,
                    reason=str(error),
                )
                return None
            if str(error) == WATCHLIST_ADD_RESULT_MISSING_REASON:
                _log_watchlist_add_result_missing(
                    chat_id=chat_id,
                    title=title,
                    year=year,
                    media_kind=media_kind,
                    reason=str(error),
                )
                return None
            if _is_watchlist_row_corrupted_reason(str(error)):
                _log_watchlist_add_row_corrupted(
                    chat_id=chat_id,
                    title=title,
                    year=year,
                    media_kind=media_kind,
                    reason=str(error),
                )
                return None
            _log_watchlist_add_failed(
                chat_id=chat_id,
                title=title,
                year=year,
                media_kind=media_kind,
                reason=str(error),
            )
            return None
        except sqlite3.Error as error:
            _log_watchlist_add_failed(
                chat_id=chat_id,
                title=title,
                year=year,
                media_kind=media_kind,
                reason=str(error),
            )
            return None
        return created

    def _list_items(self, *, chat_id: int):
        try:
            items = self._watchlist_repo.list_items(chat_id=chat_id)
            if items is None:
                raise WatchlistPersistenceError("watchlist list result missing")
            return items
        except (WatchlistPersistenceError, sqlite3.Error) as error:
            if str(error) == "watchlist list result missing":
                _log_watchlist_list_result_missing(chat_id=chat_id, reason=str(error))
            elif _is_watchlist_row_corrupted_reason(str(error)):
                _log_watchlist_list_row_corrupted(chat_id=chat_id, reason=str(error))
            else:
                _log_watchlist_list_failed(chat_id=chat_id, reason=str(error))
            return None

    def _remove_item(self, *, chat_id: int, item_id: int):
        try:
            removed = self._watchlist_repo.remove_item(chat_id=chat_id, item_id=item_id)
            if removed is None:
                raise WatchlistPersistenceError("watchlist remove result missing")
            return removed
        except (WatchlistPersistenceError, sqlite3.Error) as error:
            if str(error) == "watchlist remove result missing":
                _log_watchlist_remove_result_missing(chat_id=chat_id, item_id=item_id, reason=str(error))
            elif _is_watchlist_row_corrupted_reason(str(error)):
                _log_watchlist_remove_row_corrupted(chat_id=chat_id, item_id=item_id, reason=str(error))
            else:
                _log_watchlist_remove_failed(chat_id=chat_id, item_id=item_id, reason=str(error))
            return None

    def _clear_items(self, *, chat_id: int):
        try:
            deleted = self._watchlist_repo.clear_items(chat_id=chat_id)
            if deleted is None:
                raise WatchlistPersistenceError("watchlist clear result missing")
            return deleted
        except (WatchlistPersistenceError, sqlite3.Error) as error:
            if str(error) == "watchlist clear result missing":
                _log_watchlist_clear_result_missing(chat_id=chat_id, reason=str(error))
            elif _is_watchlist_row_corrupted_reason(str(error)):
                _log_watchlist_clear_row_corrupted(chat_id=chat_id, reason=str(error))
            else:
                _log_watchlist_clear_failed(chat_id=chat_id, reason=str(error))
            return None


def parse_watchlist_query(text: str) -> WatchlistCommand | None:
    cleaned_text = text.strip()
    if not cleaned_text:
        return None

    matched = re.match(r"^(?:(?i:watchlist)|想看)(?:\s+(.*))?$", cleaned_text)
    if not matched:
        return None
    tail = (matched.group(1) or "").strip()
    if not tail:
        return WatchlistCommand(action="list", arg="")

    lowered_tail = tail.lower()
    if lowered_tail in {"list"} or tail in {"列表"}:
        return WatchlistCommand(action="list", arg="")
    if lowered_tail in {"clear"} or tail in {"清空"}:
        return WatchlistCommand(action="clear", arg="")
    if lowered_tail in {"add"} or tail in {"添加", "加"}:
        return WatchlistCommand(action="add", arg="")
    if lowered_tail in {"remove", "rm"} or tail in {"删除", "删"}:
        return WatchlistCommand(action="remove", arg="")

    matched_add = re.match(r"^(?:(?i:add)|添加|加)\s+(.*)$", tail)
    if matched_add:
        return WatchlistCommand(action="add", arg=(matched_add.group(1) or "").strip())

    matched_remove = re.match(r"^(?:(?i:remove)|(?i:rm)|删除|删)\s+(.*)$", tail)
    if matched_remove:
        return WatchlistCommand(action="remove", arg=(matched_remove.group(1) or "").strip())

    return WatchlistCommand(action="add", arg=tail)


def _parse_media_kind_prefix(raw_title: str) -> tuple[str, str]:
    cleaned_title = raw_title.strip()
    if not cleaned_title:
        return "movie", ""

    head, separator, tail = cleaned_title.partition(" ")
    direct_media_kind = MEDIA_KIND_ALIASES.get(head.strip().lower())
    if not separator:
        if direct_media_kind is not None:
            return direct_media_kind, ""
        return "movie", cleaned_title

    if direct_media_kind is None:
        return "movie", cleaned_title
    return direct_media_kind, tail.strip()


def _media_kind_label(media_kind: str) -> str:
    cleaned_kind = media_kind.strip().lower()
    return MEDIA_KIND_LABELS.get(cleaned_kind, MEDIA_KIND_LABELS["movie"])


def _log_watchlist_add_failed(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[想看写入失败]\033[0m chat_id={chat_id} title={title} year={year or '-'} "
        f"media_kind={media_kind} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写，以及 watchlist_item 表和当前条目是否正常。"
    )


def _log_watchlist_add_item_missing_after_insert(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[想看写入后条目缺失]\033[0m chat_id={chat_id} title={title} year={year or '-'} "
        f"media_kind={media_kind} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 watchlist_item 表是否被并发删除或触发器回滚；"
        "如需继续添加，请先确认 SQLite 写入后能立即回读该条目。"
    )


def _log_watchlist_add_result_missing(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[想看写入结果缺失]\033[0m chat_id={chat_id} title={title} year={year or '-'} "
        f"media_kind={media_kind} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 watchlist_item 插入返回是否仍带有明确结果；"
        "当前会按写入失败处理，避免把缺失真相误判成“已成功加入想看”。"
    )


def _log_watchlist_add_row_corrupted(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[想看写入命中坏记录]\033[0m chat_id={chat_id} title={title} year={year or '-'} "
        f"media_kind={media_kind} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 watchlist_item 表里该 chat 的 id、title、media_kind 等真相字段；"
        "当前会按写入失败处理，避免把损坏记录误判成可复用旧条目或成功新建条目。"
    )


def _log_watchlist_list_failed(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[想看清单读取失败]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可读，以及 watchlist_item 表是否正常。"
    )


def _log_watchlist_list_result_missing(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[想看清单结果缺失]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 watchlist_item 查询返回是否仍带有完整列表；"
        "当前会按读取失败处理，避免把缺失真相误判成“清单为空”。"
    )


def _log_watchlist_list_row_corrupted(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[想看清单记录损坏]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 watchlist_item 表里该 chat 的 id、title、media_kind 等真相字段；"
        "当前会按读取失败处理，避免把损坏记录误判成正常清单。"
    )


def _log_watchlist_remove_failed(*, chat_id: int, item_id: int, reason: str) -> None:
    print(
        f"\033[31m[想看删除失败]\033[0m chat_id={chat_id} item_id={item_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写，以及 watchlist_item 表和当前条目是否正常。"
    )


def _log_watchlist_remove_result_missing(*, chat_id: int, item_id: int, reason: str) -> None:
    print(
        f"\033[31m[想看删除结果缺失]\033[0m chat_id={chat_id} item_id={item_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 watchlist_item 删除查询返回是否仍带有完整结果；"
        "当前会按删除失败处理，避免把缺失真相误判成“条目不存在”。"
    )


def _log_watchlist_remove_row_corrupted(*, chat_id: int, item_id: int, reason: str) -> None:
    print(
        f"\033[31m[想看删除命中坏记录]\033[0m chat_id={chat_id} item_id={item_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 watchlist_item 表里该 chat 的 id、title、media_kind 等真相字段；"
        "当前会按删除失败处理，避免把损坏记录误判成可正常删除或“条目不存在”。"
    )


def _log_watchlist_clear_failed(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[想看清单清空失败]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写，以及 watchlist_item 表是否正常。"
    )


def _log_watchlist_clear_result_missing(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[想看清单清空结果缺失]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 watchlist_item 清空查询返回是否仍带有完整结果；"
        "当前会按清空失败处理，避免把缺失真相误判成“本来就是空的”。"
    )


def _log_watchlist_clear_row_corrupted(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[想看清单清空命中坏记录]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 watchlist_item 表里该 chat 的 id、title、media_kind 等真相字段；"
        "当前会按清空失败处理，避免把损坏记录误判成可正常清空或“清单本来就是空的”。"
    )


def _is_watchlist_row_corrupted_reason(reason: str) -> bool:
    return reason in {
        "watchlist_item row identity corrupted after read",
        "watchlist_item media kind corrupted after read",
    }
