from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.db.bt_subscription_repo import BtSubscriptionItem, BtSubscriptionRepo
from app.services.add_to_downloader import AddToDownloaderService
from app.services.bt_sources import resolve_bt_source
from app.services.search_media import parse_movie_query

SearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]

BT_SUBSCRIPTION_USAGE_TEXT = (
    "BT 订阅命令格式：\n"
    "btsub list\n"
    "btsub add <movie|series|anime> <片名 [年份]>\n"
    "btsub remove <条目ID>\n"
    "btsub clear\n"
    "btsub run"
)
BT_SUBSCRIPTION_EMPTY_TEXT = "BT 订阅清单为空。"
BT_SUBSCRIPTION_LIST_FAILED_TEXT = "BT 订阅清单读取失败，请稍后重试。"
BT_SUBSCRIPTION_ADD_USAGE_TEXT = "添加格式：btsub add <movie|series|anime> <片名 [年份]>"
BT_SUBSCRIPTION_ADD_FAILED_TEXT = "BT 订阅写入失败，请稍后重试。"
BT_SUBSCRIPTION_REMOVE_USAGE_TEXT = "删除格式：btsub remove <条目ID>"
BT_SUBSCRIPTION_REMOVE_FAILED_TEXT = "BT 订阅删除失败，请稍后重试。"
BT_SUBSCRIPTION_CLEAR_EMPTY_TEXT = "BT 订阅清单本来就是空的。"
BT_SUBSCRIPTION_CLEAR_FAILED_TEXT = "BT 订阅清单清空失败，请稍后重试。"
BT_SUBSCRIPTION_RUN_EMPTY_TEXT = "当前没有可扫描的 BT 订阅。"
BT_SUBSCRIPTION_RUN_FAILED_TEXT = "BT 订阅扫描失败，请稍后重试。"
BT_SUBSCRIPTION_RUN_DONE_TEMPLATE = "BT 订阅扫描完成：共扫描 {scanned} 条，命中新资源 {matched} 条。"
BT_SUBSCRIPTION_RUN_NO_NEW_TEMPLATE = "BT 订阅扫描完成：共扫描 {scanned} 条，当前没有新资源。"
BT_SUBSCRIPTION_LAST_SEEN_UPDATE_WARNING_TEXT = (
    "注意：BT 订阅最近资源真相未更新，下次扫描可能重复命中同一资源。\n"
    "请检查 SQLite 是否可写、订阅条目是否仍存在，然后重新执行 btsub run。"
)
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


@dataclass(frozen=True, slots=True)
class BtSubscriptionCommand:
    action: str
    arg: str


@dataclass(frozen=True, slots=True)
class BtSubscriptionRunResult:
    scanned: int
    matched: int
    replies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BtSubscriptionDispatchContext:
    downloader_name: str
    downloader_type: str
    download_dir: str


@dataclass(frozen=True, slots=True)
class BtSubscriptionCandidate:
    index: int
    result: Mapping[str, Any]
    quality_rank: int
    preferred: bool
    seeders: int
    size_bytes: int


class ManageBtSubscriptionService:
    def __init__(
        self,
        bt_subscription_repo: BtSubscriptionRepo,
        search_func: SearchFunc,
        add_to_downloader_service: AddToDownloaderService,
    ) -> None:
        self._bt_subscription_repo = bt_subscription_repo
        self._search_func = search_func
        self._add_to_downloader_service = add_to_downloader_service

    def handle(self, command: BtSubscriptionCommand, *, chat_id: int | None) -> str:
        if chat_id is None or chat_id <= 0:
            return BT_SUBSCRIPTION_USAGE_TEXT

        if command.action == "list":
            return self._list_text(chat_id=chat_id)
        if command.action == "add":
            return self._add_text(chat_id=chat_id, raw_title=command.arg)
        if command.action == "remove":
            return self._remove_text(chat_id=chat_id, item_ref=command.arg)
        if command.action == "clear":
            return self._clear_text(chat_id=chat_id)
        return BT_SUBSCRIPTION_USAGE_TEXT

    async def run_once(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        dispatch_context: BtSubscriptionDispatchContext,
    ) -> str:
        if chat_id is None or chat_id <= 0:
            return BT_SUBSCRIPTION_USAGE_TEXT

        result = await self._scan_chat_once(
            chat_id=chat_id,
            user_id=user_id,
            dispatch_context=dispatch_context,
        )
        if result is None:
            return BT_SUBSCRIPTION_RUN_FAILED_TEXT
        if result.scanned <= 0:
            return BT_SUBSCRIPTION_RUN_EMPTY_TEXT
        return _format_bt_subscription_run_result(result)

    async def run_scheduler_tick(
        self,
        *,
        dispatch_context: BtSubscriptionDispatchContext,
    ) -> tuple[tuple[int, str], ...]:
        notifications: list[tuple[int, str]] = []
        try:
            chat_ids = self._bt_subscription_repo.list_chat_ids()
        except Exception as error:
            _log_bt_subscription_scan_chat_ids_failed(reason=str(error))
            return ()
        for chat_id in chat_ids:
            result = await self._scan_chat_once(
                chat_id=chat_id,
                user_id=None,
                dispatch_context=dispatch_context,
            )
            if result is None:
                continue
            if result.matched <= 0:
                continue
            notifications.append((chat_id, _format_bt_subscription_run_result(result)))
        return tuple(notifications)

    def _list_text(self, *, chat_id: int) -> str:
        items = self._list_items(chat_id=chat_id)
        if items is None:
            return BT_SUBSCRIPTION_LIST_FAILED_TEXT
        if not items:
            return BT_SUBSCRIPTION_EMPTY_TEXT

        lines = ["BT 订阅清单："]
        for index, item in enumerate(items, start=1):
            year_text = item.year if item.year else "-"
            last_seen = item.last_seen_title.strip() or "-"
            lines.append(
                f"{index}. [{item.item_id}] {item.title} ({year_text}) | 类型: {_media_kind_label(item.media_kind)} | 最近资源: {last_seen}"
            )
        return "\n".join(lines)

    def _add_text(self, *, chat_id: int, raw_title: str) -> str:
        cleaned_title = raw_title.strip()
        if not cleaned_title:
            return BT_SUBSCRIPTION_ADD_USAGE_TEXT

        media_kind, parsed_title = _parse_media_kind_prefix(cleaned_title)
        if media_kind not in {"movie", "series", "anime"}:
            return BT_SUBSCRIPTION_ADD_USAGE_TEXT
        parsed = parse_movie_query(parsed_title)
        title = parsed.title.strip()
        year = parsed.year.strip()
        if not title:
            return BT_SUBSCRIPTION_ADD_USAGE_TEXT

        created = self._add_item(
            chat_id=chat_id,
            title=title,
            year=year,
            media_kind=media_kind,
        )
        if created is None:
            return BT_SUBSCRIPTION_ADD_FAILED_TEXT
        item, is_created = created
        year_text = item.year if item.year else "-"
        if is_created:
            return (
                f"已加入 BT 订阅：{item.title} ({year_text})\n"
                f"类型: {_media_kind_label(item.media_kind)}\n"
                f"条目ID: {item.item_id}"
            )
        return (
            f"BT 订阅已存在：{item.title} ({year_text})\n"
            f"类型: {_media_kind_label(item.media_kind)}\n"
            f"条目ID: {item.item_id}"
        )

    def _remove_text(self, *, chat_id: int, item_ref: str) -> str:
        cleaned_ref = item_ref.strip()
        if not cleaned_ref.isdigit():
            return BT_SUBSCRIPTION_REMOVE_USAGE_TEXT
        item_id = int(cleaned_ref)
        if item_id <= 0:
            return BT_SUBSCRIPTION_REMOVE_USAGE_TEXT
        removed = self._remove_item(chat_id=chat_id, item_id=item_id)
        if removed is None:
            return BT_SUBSCRIPTION_REMOVE_FAILED_TEXT
        if not removed:
            return "未找到对应 BT 订阅条目。"
        return f"已删除 BT 订阅条目：{item_id}"

    def _clear_text(self, *, chat_id: int) -> str:
        deleted = self._clear_items(chat_id=chat_id)
        if deleted is None:
            return BT_SUBSCRIPTION_CLEAR_FAILED_TEXT
        if deleted <= 0:
            return BT_SUBSCRIPTION_CLEAR_EMPTY_TEXT
        return f"已清空 BT 订阅清单，共删除 {deleted} 条。"

    def _add_item(
        self,
        *,
        chat_id: int,
        title: str,
        year: str,
        media_kind: str,
    ):
        try:
            created = self._bt_subscription_repo.add_item(
                chat_id=chat_id,
                title=title,
                year=year,
                media_kind=media_kind,
            )
        except Exception as error:
            _log_bt_subscription_add_failed(
                chat_id=chat_id,
                title=title,
                year=year,
                media_kind=media_kind,
                reason=str(error),
            )
            return None
        if created is not None:
            return created
        _log_bt_subscription_add_failed(
            chat_id=chat_id,
            title=title,
            year=year,
            media_kind=media_kind,
            reason="bt_subscription_repo.add_item returned None",
        )
        return None

    def _list_items(self, *, chat_id: int):
        try:
            return self._bt_subscription_repo.list_items(chat_id=chat_id)
        except Exception as error:
            _log_bt_subscription_list_failed(chat_id=chat_id, reason=str(error))
            return None

    def _remove_item(self, *, chat_id: int, item_id: int):
        try:
            return self._bt_subscription_repo.remove_item(chat_id=chat_id, item_id=item_id)
        except Exception as error:
            _log_bt_subscription_remove_failed(chat_id=chat_id, item_id=item_id, reason=str(error))
            return None

    def _clear_items(self, *, chat_id: int):
        try:
            return self._bt_subscription_repo.clear_items(chat_id=chat_id)
        except Exception as error:
            _log_bt_subscription_clear_failed(chat_id=chat_id, reason=str(error))
            return None

    async def _run_for_item(
        self,
        *,
        item: BtSubscriptionItem,
        chat_id: int,
        user_id: int | None,
        dispatch_context: BtSubscriptionDispatchContext,
    ) -> str | None:
        query = _build_subscription_query(item)
        try:
            results = await self._search_func(query)
        except Exception as error:
            _log_bt_subscription_scan_error(item=item, query=query, error=error)
            return None

        selected_result = _pick_subscription_candidate(
            results,
            last_seen_source=item.last_seen_source,
        )
        if selected_result is None:
            return None

        selected_source = _resolve_candidate_source(selected_result)
        if not selected_source:
            return None

        candidate_title = _resolve_candidate_title(selected_result, item=item)
        pending_text = await self._add_to_downloader_service.add_candidate_source(
            chat_id=chat_id,
            user_id=user_id,
            source=selected_source,
            title=candidate_title,
            downloader_name=dispatch_context.downloader_name,
            downloader_type=dispatch_context.downloader_type,
            download_dir=dispatch_context.download_dir,
            auto_import_enabled=True,
        )
        if "下载待确认：" not in pending_text:
            return None

        year_text = item.year if item.year else "-"
        reply = (
            f"BT 订阅命中新资源：{item.title} ({year_text})\n"
            f"类型: {_media_kind_label(item.media_kind)}\n"
            f"命中资源: {candidate_title}\n\n"
            f"{pending_text}"
        )
        if self._update_last_seen(
            item=item,
            chat_id=chat_id,
            source=selected_source,
            title=candidate_title,
        ):
            return reply
        return f"{reply}\n\n{BT_SUBSCRIPTION_LAST_SEEN_UPDATE_WARNING_TEXT}"

    async def _scan_chat_once(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        dispatch_context: BtSubscriptionDispatchContext,
    ) -> BtSubscriptionRunResult | None:
        try:
            items = self._bt_subscription_repo.list_items(chat_id=chat_id)
        except Exception as error:
            _log_bt_subscription_scan_items_failed(chat_id=chat_id, reason=str(error))
            return None
        if not items:
            return BtSubscriptionRunResult(scanned=0, matched=0, replies=())

        replies: list[str] = []
        matched = 0
        for item in items:
            reply = await self._run_for_item(
                item=item,
                chat_id=chat_id,
                user_id=user_id,
                dispatch_context=dispatch_context,
            )
            if reply is None:
                continue
            matched += 1
            replies.append(reply)
        return BtSubscriptionRunResult(scanned=len(items), matched=matched, replies=tuple(replies))

    def _update_last_seen(
        self,
        *,
        item: BtSubscriptionItem,
        chat_id: int,
        source: str,
        title: str,
    ) -> bool:
        try:
            updated = self._bt_subscription_repo.update_last_seen(
                chat_id=chat_id,
                item_id=item.item_id,
                source=source,
                title=title,
            )
        except Exception as error:
            _log_bt_subscription_last_seen_update_failed(
                item=item,
                chat_id=chat_id,
                source=source,
                title=title,
                reason=str(error),
            )
            return False
        if updated:
            return True
        _log_bt_subscription_last_seen_update_failed(
            item=item,
            chat_id=chat_id,
            source=source,
            title=title,
            reason="bt_subscription_repo.update_last_seen returned False",
        )
        return False


def parse_bt_subscription_query(text: str) -> BtSubscriptionCommand | None:
    cleaned_text = text.strip()
    if not cleaned_text:
        return None

    matched = re.match(r"^(?i:btsub)(?:\s+(.*))?$", cleaned_text)
    if not matched:
        return None
    tail = (matched.group(1) or "").strip()
    if not tail:
        return BtSubscriptionCommand(action="list", arg="")

    lowered_tail = tail.lower()
    if lowered_tail == "list":
        return BtSubscriptionCommand(action="list", arg="")
    if lowered_tail == "clear":
        return BtSubscriptionCommand(action="clear", arg="")
    if lowered_tail == "run":
        return BtSubscriptionCommand(action="run", arg="")
    if lowered_tail == "add":
        return BtSubscriptionCommand(action="add", arg="")
    if lowered_tail in {"remove", "rm"}:
        return BtSubscriptionCommand(action="remove", arg="")

    matched_add = re.match(r"^(?i:add)\s+(.*)$", tail)
    if matched_add:
        return BtSubscriptionCommand(action="add", arg=(matched_add.group(1) or "").strip())

    matched_remove = re.match(r"^(?:(?i:remove)|(?i:rm))\s+(.*)$", tail)
    if matched_remove:
        return BtSubscriptionCommand(action="remove", arg=(matched_remove.group(1) or "").strip())

    return BtSubscriptionCommand(action="add", arg=tail)


def _parse_media_kind_prefix(raw_title: str) -> tuple[str, str]:
    cleaned_title = raw_title.strip()
    if not cleaned_title:
        return "movie", ""

    head, separator, tail = cleaned_title.partition(" ")
    direct_media_kind = MEDIA_KIND_ALIASES.get(head.strip().lower())
    if not separator:
        if direct_media_kind is not None:
            return direct_media_kind, ""
        return "", cleaned_title
    if direct_media_kind is None:
        return "", cleaned_title
    return direct_media_kind, tail.strip()


def _media_kind_label(media_kind: str) -> str:
    return MEDIA_KIND_LABELS.get(media_kind.strip().lower(), MEDIA_KIND_LABELS["movie"])


def _build_subscription_query(item: BtSubscriptionItem) -> str:
    title = item.title.strip()
    year = item.year.strip()
    if title and year:
        return f"{title} {year}"
    return title


def _pick_subscription_candidate(
    results: Sequence[Mapping[str, Any]],
    *,
    last_seen_source: str,
) -> Mapping[str, Any] | None:
    ranked_candidates = sorted(
        _collect_subscription_candidates(results, last_seen_source=last_seen_source),
        key=_subscription_candidate_sort_key,
        reverse=True,
    )
    if not ranked_candidates:
        return None
    return ranked_candidates[0].result


def _collect_subscription_candidates(
    results: Sequence[Mapping[str, Any]],
    *,
    last_seen_source: str,
) -> list[BtSubscriptionCandidate]:
    normalized_last_seen_source = last_seen_source.strip()
    candidates: list[BtSubscriptionCandidate] = []
    for index, result in enumerate(results):
        source = _resolve_candidate_source(result)
        if not source or source == normalized_last_seen_source:
            continue
        title = str(result.get("title", "")).strip()
        candidates.append(
            BtSubscriptionCandidate(
                index=index,
                result=result,
                quality_rank=_subscription_quality_rank(title),
                preferred=not _is_subscription_low_quality(title),
                seeders=_safe_int(result.get("seeders")),
                size_bytes=_safe_int(result.get("size")),
            )
        )
    return candidates


def _subscription_candidate_sort_key(candidate: BtSubscriptionCandidate) -> tuple[int, int, int, int, int]:
    return (
        1 if candidate.preferred else 0,
        candidate.quality_rank,
        candidate.seeders,
        candidate.size_bytes,
        -candidate.index,
    )


def _resolve_candidate_source(candidate: Mapping[str, Any]) -> str:
    return resolve_bt_source(candidate)


def _resolve_candidate_title(candidate: Mapping[str, Any], *, item: BtSubscriptionItem) -> str:
    title = str(candidate.get("title", "")).strip()
    if title:
        return title
    year_text = item.year if item.year else "-"
    return f"{item.title} ({year_text})"


def _subscription_quality_rank(title: str) -> int:
    lowered_title = title.strip().lower()
    if not lowered_title:
        return 0
    if re.search(r"\b(2160p|4k)\b", lowered_title):
        return 4
    if re.search(r"\b1080p\b", lowered_title):
        return 3
    if re.search(r"\b720p\b", lowered_title):
        return 2
    if re.search(r"\b480p\b", lowered_title):
        return 1
    return 0


def _is_subscription_low_quality(title: str) -> bool:
    lowered_title = title.strip().lower()
    if not lowered_title:
        return False
    return re.search(r"\b(cam|hdcam|ts|tc|telesync|telecine|screener)\b", lowered_title) is not None


def _safe_int(value: Any) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return 0
    if resolved > 0:
        return resolved
    return 0


def _log_bt_subscription_scan_error(
    *,
    item: BtSubscriptionItem,
    query: str,
    error: Exception,
) -> None:
    print(
        f"\033[31m[BT 订阅扫描失败]\033[0m 条目ID={item.item_id} 类型={item.media_kind} 查询={query} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 Prowlarr 地址、API Key 和网络连通性后重试。"
    )


def _log_bt_subscription_scan_items_failed(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅扫描读取失败]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可读，以及 bt_subscription_item 表是否正常。"
    )


def _log_bt_subscription_scan_chat_ids_failed(*, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅扫描 chat 列表读取失败]\033[0m 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可读，以及 bt_subscription_item 表是否正常。"
    )


def _log_bt_subscription_list_failed(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅清单读取失败]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可读，以及 bt_subscription_item 表是否正常。"
    )


def _log_bt_subscription_remove_failed(*, chat_id: int, item_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅删除失败]\033[0m chat_id={chat_id} item_id={item_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写，以及 bt_subscription_item 表和当前条目是否正常。"
    )


def _log_bt_subscription_clear_failed(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅清单清空失败]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写，以及 bt_subscription_item 表是否正常。"
    )


def _log_bt_subscription_add_failed(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅写入失败]\033[0m chat_id={chat_id} title={title} year={year or '-'} "
        f"media_kind={media_kind} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写，以及 bt_subscription_item 表和当前条目是否正常。"
    )


def _log_bt_subscription_last_seen_update_failed(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅最近资源回写失败]\033[0m chat_id={chat_id} 条目ID={item.item_id} "
        f"类型={item.media_kind} source={source} title={title} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写、订阅条目是否仍存在，然后重新执行 btsub run。"
    )


def _format_bt_subscription_run_result(result: BtSubscriptionRunResult) -> str:
    header = (
        BT_SUBSCRIPTION_RUN_DONE_TEMPLATE.format(scanned=result.scanned, matched=result.matched)
        if result.matched > 0
        else BT_SUBSCRIPTION_RUN_NO_NEW_TEMPLATE.format(scanned=result.scanned)
    )
    if not result.replies:
        return header
    return f"{header}\n\n" + "\n\n".join(result.replies)
