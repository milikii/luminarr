from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from typing import Protocol

from app.bot.raw_bt_destination_runtime import can_dispatch_bt_source
from app.clients.tmdb import TmdbMovie
from app.services.add_to_downloader import BT_SOURCE_UNSUPPORTED_TEXT, AddToDownloaderService
from app.services.search_media import parse_movie_query

BT_TMDB_ASSOCIATION_PROMPT_TEXT_TEMPLATE = (
    "已记录本次 BT 分类：{label}（{kind}）。\n"
    "请继续发送片名，可带年份，例如：{example}\n"
    "当前这一步只做 TMDB 关联，不会执行下载投递。"
)
BT_TMDB_ASSOCIATION_PENDING_REMINDER_TEMPLATE = (
    "当前正在等待 {label} 的 TMDB 关联标题。\n"
    "请发送：片名 或 片名 + 年份，例如：{example}"
)
BT_TMDB_ASSOCIATION_CANCELLED_TEXT = "已取消当前 BT TMDB 关联，请重新发送磁力或 BT 指令。"
BT_TMDB_ASSOCIATION_NOT_FOUND_TEMPLATE = (
    "未找到可用的 TMDB 关联：{query}\n"
    "请补充更准确的片名，可带年份，例如：{example}\n"
    "如果这不是影视资源，请改选 raw_bt。"
)
BT_TMDB_ASSOCIATION_AMBIGUOUS_TEMPLATE = (
    "TMDB 关联存在多个候选：{query}\n"
    "请补充年份或更完整片名后重试。\n"
    "参考候选：\n"
    "{options}"
)
BT_TMDB_ASSOCIATION_SUCCESS_TEMPLATE = (
    "BT {label} TMDB 关联成功。\n"
    "标题: {title}\n"
    "原始标题: {original_title}\n"
    "年份: {year}\n"
    "TMDB ID: {tmdb_id}"
)
BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT = "TMDB 关联服务未就绪，请稍后重试。"
BT_TMDB_ASSOCIATION_EXAMPLES = {
    "movie": "Dune 2021",
    "series": "三体 2023",
    "anime": "葬送的芙莉莲 2023",
}
BT_CLASSIFICATION_LABELS = {
    "movie": "电影",
    "series": "剧集",
    "anime": "动漫",
}


@dataclass(frozen=True, slots=True)
class BtTmdbAssociationPending:
    media_kind: str
    source: str


class ResolvedDownloaderExecutionLike(Protocol):
    name: str
    downloader_type: str
    download_dir: str


def format_bt_tmdb_association_prompt(media_kind: str) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, media_kind)
    example = BT_TMDB_ASSOCIATION_EXAMPLES.get(media_kind, "Dune 2021")
    return BT_TMDB_ASSOCIATION_PROMPT_TEXT_TEMPLATE.format(label=label, kind=media_kind, example=example)


def format_bt_tmdb_association_pending_reminder(media_kind: str) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, media_kind)
    example = BT_TMDB_ASSOCIATION_EXAMPLES.get(media_kind, "Dune 2021")
    return BT_TMDB_ASSOCIATION_PENDING_REMINDER_TEMPLATE.format(label=label, example=example)


def format_bt_tmdb_association_options(options: list[TmdbMovie]) -> str:
    lines: list[str] = []
    for index, option in enumerate(options, start=1):
        title = option.title or option.original_title or "-"
        year = option.year or "-"
        lines.append(f"{index}. {title} ({year}) [TMDB ID: {option.tmdb_id or '-'}]")
    return "\n".join(lines) if lines else "- 暂无可区分候选，请直接补充年份。"


def format_bt_tmdb_association_success(media_kind: str, match: TmdbMovie) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, media_kind)
    title = match.title or match.original_title or "-"
    original_title = match.original_title or title
    year = match.year or "-"
    tmdb_id = match.tmdb_id or "-"
    return BT_TMDB_ASSOCIATION_SUCCESS_TEMPLATE.format(
        label=label,
        title=title,
        original_title=original_title,
        year=year,
        tmdb_id=tmdb_id,
    )


def format_bt_dispatch_title(match: TmdbMovie) -> str:
    title = match.title or match.original_title or "(no title)"
    year = match.year.strip()
    if not year:
        return title
    return f"{title} ({year})"


async def handle_bt_tmdb_association_query(
    *,
    query: str,
    pending: BtTmdbAssociationPending,
    chat_id: int | None,
    user_id: int | None,
    bot_data: MutableMapping[str, object],
    add_to_downloader_service_key: str,
    clear_pending: Callable[[], bool | None],
    resolve_candidates_lookup: Callable[[str], Callable[[str, str], Awaitable[list[TmdbMovie]]] | None],
    resolve_downloader_execution: Callable[[], tuple[ResolvedDownloaderExecutionLike | None, str | None]],
    log_bt_tmdb_association_error: Callable[[str, str, Exception], None],
    service_not_ready_text: str,
    bt_tmdb_association_service_not_ready_text: str,
    bt_source_required_text: str,
) -> str:
    if chat_id is None:
        return service_not_ready_text
    parsed_query = parse_movie_query(query)
    if not parsed_query.title:
        return format_bt_tmdb_association_pending_reminder(pending.media_kind)

    lookup_func = resolve_candidates_lookup(pending.media_kind)
    if lookup_func is None:
        return bt_tmdb_association_service_not_ready_text

    try:
        matches = await lookup_func(parsed_query.title, parsed_query.year)
    except Exception as error:
        log_bt_tmdb_association_error(pending.media_kind, query, error)
        return bt_tmdb_association_service_not_ready_text

    if not matches:
        example = BT_TMDB_ASSOCIATION_EXAMPLES.get(pending.media_kind, "Dune 2021")
        return BT_TMDB_ASSOCIATION_NOT_FOUND_TEMPLATE.format(query=query.strip(), example=example)

    if not parsed_query.year and len(matches) > 1:
        return BT_TMDB_ASSOCIATION_AMBIGUOUS_TEMPLATE.format(
            query=query.strip(),
            options=format_bt_tmdb_association_options(matches),
        )

    cleared_tmdb_association = clear_pending()
    if cleared_tmdb_association is None:
        return service_not_ready_text
    association_text = format_bt_tmdb_association_success(pending.media_kind, matches[0])
    if not can_dispatch_bt_source(pending.source):
        return f"{association_text}\n\n{bt_source_required_text}"
    add_service = bot_data.get(add_to_downloader_service_key)
    if not isinstance(add_service, AddToDownloaderService):
        return service_not_ready_text
    downloader_execution, resolution_error = resolve_downloader_execution()
    if resolution_error is not None:
        return resolution_error
    pending_text = await add_service.add_bt_source(
        chat_id=chat_id,
        user_id=user_id,
        source=pending.source,
        title=format_bt_dispatch_title(matches[0]),
        downloader_name=downloader_execution.name if downloader_execution is not None else "",
        downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
        download_dir=downloader_execution.download_dir if downloader_execution is not None else "",
        auto_import_enabled=True,
    )
    if pending_text == BT_SOURCE_UNSUPPORTED_TEXT:
        return pending_text
    return f"{association_text}\n\n{pending_text}"
