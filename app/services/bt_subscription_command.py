from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.db.bt_subscription_repo import BtSubscriptionItem
from app.services.adult_content import extract_exact_adult_content_match
from app.services.command_parsing import (
    match_command_action,
    match_command_action_argument,
    parse_prefixed_command_tail,
)
from app.services.media_item_display import format_title_year

BT_SUBSCRIPTION_MEDIA_KIND_ADULT = "adult"
BT_SUBSCRIPTION_MEDIA_KIND_LABELS = {
    "adult": "成人",
    "movie": "电影",
    "series": "剧集",
    "anime": "动漫",
}

BT_SUBSCRIPTION_USAGE_TEXT = (
    "BT 订阅命令格式：\n"
    "btsub list\n"
    "btsub add <番号>\n"
    "btsub remove <条目ID>\n"
    "btsub clear\n"
    "btsub run"
)
BT_SUBSCRIPTION_EMPTY_TEXT = "BT 订阅清单为空。"
BT_SUBSCRIPTION_ADD_USAGE_TEXT = "添加格式：btsub add <番号>"
BT_SUBSCRIPTION_ADULT_ONLY_TEXT = "BT 订阅当前只支持成人 BT 资源追踪；影视资源包括动漫请继续走 PT 主链或 direct BT 问询。"
BT_SUBSCRIPTION_REMOVE_USAGE_TEXT = "删除格式：btsub remove <条目ID>"
BT_SUBSCRIPTION_CLEAR_EMPTY_TEXT = "BT 订阅清单本来就是空的。"
BT_SUBSCRIPTION_ACTION_ALIASES = {
    "list": ("list",),
    "clear": ("clear",),
    "run": ("run",),
    "add": ("add",),
    "remove": ("remove", "rm"),
}
BT_SUBSCRIPTION_ARGUMENT_ACTION_ALIASES = {
    "add": ("add",),
    "remove": ("remove", "rm"),
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
    tail = parse_prefixed_command_tail(text, prefix_pattern=r"(?i:btsub)")
    if tail is None:
        return None
    if not tail:
        return BtSubscriptionCommand(action="list", arg="")

    action = match_command_action(tail, BT_SUBSCRIPTION_ACTION_ALIASES)
    if action is not None:
        return BtSubscriptionCommand(action=action, arg="")

    action_argument = match_command_action_argument(tail, BT_SUBSCRIPTION_ARGUMENT_ACTION_ALIASES)
    if action_argument is not None:
        action, arg = action_argument
        return BtSubscriptionCommand(action=action, arg=arg)

    return BtSubscriptionCommand(action="add", arg=tail)


def parse_bt_subscription_add_request(raw_title: str) -> ParsedBtSubscriptionAddRequest | None:
    cleaned_title = raw_title.strip()
    if not cleaned_title:
        return None

    match = extract_exact_adult_content_match(cleaned_title)
    if match is None or not match.display_id.strip():
        return None
    return ParsedBtSubscriptionAddRequest(
        media_kind=BT_SUBSCRIPTION_MEDIA_KIND_ADULT,
        title=match.display_id.strip(),
        year="",
    )


def format_bt_subscription_list(items: Sequence[BtSubscriptionItem]) -> str:
    if not items:
        return BT_SUBSCRIPTION_EMPTY_TEXT

    lines = ["BT 订阅清单："]
    for index, item in enumerate(items, start=1):
        last_seen = item.last_seen_title.strip() or "-"
        lines.append(
            f"{index}. [{item.item_id}] {format_title_year(item.title, item.year)} | 类型: {bt_subscription_media_kind_label(item.media_kind)} | 上次命中资源: {last_seen}"
        )
    return "\n".join(lines)


def format_bt_subscription_add_result(item: BtSubscriptionItem, *, is_created: bool) -> str:
    title_year = format_title_year(item.title, item.year)
    kind_text = bt_subscription_media_kind_label(item.media_kind)
    if is_created:
        return f"已加入 BT 订阅：{title_year}\n类型: {kind_text}\n条目ID: {item.item_id}"
    return f"BT 订阅已存在：{title_year}\n类型: {kind_text}\n条目ID: {item.item_id}"


def format_bt_subscription_remove_result(item_id: int, *, removed: bool) -> str:
    if not removed:
        return "未找到对应 BT 订阅条目。"
    return f"已删除 BT 订阅条目：{item_id}"


def format_bt_subscription_clear_result(deleted: int) -> str:
    if deleted <= 0:
        return BT_SUBSCRIPTION_CLEAR_EMPTY_TEXT
    return f"已清空 BT 订阅清单，共删除 {deleted} 条。"


def bt_subscription_media_kind_label(media_kind: str) -> str:
    cleaned_kind = media_kind.strip().lower()
    return BT_SUBSCRIPTION_MEDIA_KIND_LABELS.get(cleaned_kind, "成人")
