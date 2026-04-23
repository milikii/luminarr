from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.db.bt_subscription_repo import BtSubscriptionItem
from app.services.search_request_context import parse_movie_query

BT_SUBSCRIPTION_USAGE_TEXT = (
    "BT 订阅命令格式：\n"
    "btsub list\n"
    "btsub add <movie|series|anime> <片名 [年份]>\n"
    "btsub remove <条目ID>\n"
    "btsub clear\n"
    "btsub run"
)
BT_SUBSCRIPTION_EMPTY_TEXT = "BT 订阅清单为空。"
BT_SUBSCRIPTION_ADD_USAGE_TEXT = "添加格式：btsub add <movie|series|anime> <片名 [年份]>"
BT_SUBSCRIPTION_REMOVE_USAGE_TEXT = "删除格式：btsub remove <条目ID>"
BT_SUBSCRIPTION_CLEAR_EMPTY_TEXT = "BT 订阅清单本来就是空的。"

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
class ParsedBtSubscriptionAddRequest:
    media_kind: str
    title: str
    year: str


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


def parse_bt_subscription_add_request(raw_title: str) -> ParsedBtSubscriptionAddRequest | None:
    cleaned_title = raw_title.strip()
    if not cleaned_title:
        return None

    media_kind, parsed_title = _parse_media_kind_prefix(cleaned_title)
    if media_kind not in {"movie", "series", "anime"}:
        return None

    parsed = parse_movie_query(parsed_title)
    title = parsed.title.strip()
    year = parsed.year.strip()
    if not title:
        return None
    return ParsedBtSubscriptionAddRequest(media_kind=media_kind, title=title, year=year)


def format_bt_subscription_list(items: Sequence[BtSubscriptionItem]) -> str:
    if not items:
        return BT_SUBSCRIPTION_EMPTY_TEXT

    lines = ["BT 订阅清单："]
    for index, item in enumerate(items, start=1):
        year_text = item.year if item.year else "-"
        last_seen = item.last_seen_title.strip() or "-"
        lines.append(
            f"{index}. [{item.item_id}] {item.title} ({year_text}) | 类型: {bt_subscription_media_kind_label(item.media_kind)} | 最近资源: {last_seen}"
        )
    return "\n".join(lines)


def format_bt_subscription_add_result(item: BtSubscriptionItem, *, is_created: bool) -> str:
    year_text = item.year if item.year else "-"
    kind_text = bt_subscription_media_kind_label(item.media_kind)
    if is_created:
        return f"已加入 BT 订阅：{item.title} ({year_text})\n类型: {kind_text}\n条目ID: {item.item_id}"
    return f"BT 订阅已存在：{item.title} ({year_text})\n类型: {kind_text}\n条目ID: {item.item_id}"


def format_bt_subscription_remove_result(item_id: int, *, removed: bool) -> str:
    if not removed:
        return "未找到对应 BT 订阅条目。"
    return f"已删除 BT 订阅条目：{item_id}"


def format_bt_subscription_clear_result(deleted: int) -> str:
    if deleted <= 0:
        return BT_SUBSCRIPTION_CLEAR_EMPTY_TEXT
    return f"已清空 BT 订阅清单，共删除 {deleted} 条。"


def bt_subscription_media_kind_label(media_kind: str) -> str:
    return MEDIA_KIND_LABELS.get(media_kind.strip().lower(), MEDIA_KIND_LABELS["movie"])


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
