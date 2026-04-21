from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.query_text_runtime import extract_bt_batch_confirm_request

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


async def handle_bt_batch_confirm_query(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    resolve_downloader_execution: Callable[[], tuple[object | None, str | None]],
    tg,
) -> bool:
    batch_confirm_request = extract_bt_batch_confirm_request(query)
    if batch_confirm_request is None:
        return False
    if not batch_confirm_request.selection_text:
        await reply_func("BT 批量确认格式：bt批量确认 1-3")
        return True
    if batch_confirm_request.invalid_selection:
        await reply_func(
            f"BT 批量确认编号格式无效：{batch_confirm_request.selection_text}\n"
            "请使用 1-3 或 2,4,6 这类范围表达。"
        )
        return True
    add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
    if not isinstance(add_service, tg.AddToDownloaderService) or chat_id is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    downloader_execution, resolution_error = resolve_downloader_execution()
    if resolution_error is not None:
        await reply_func(resolution_error)
        return True
    reply = await execution_gate.run(
        tg.ACTION_ADD_TO_DOWNLOADER,
        lambda: add_service.add_by_batch_selection(
            chat_id,
            batch_confirm_request.selected_indexes,
            user_id=user_id,
            channel=channel,
            downloader_name=downloader_execution.name if downloader_execution is not None else "",
            downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
            download_dir=downloader_execution.download_dir if downloader_execution is not None else "",
            auto_import_enabled=False,
        ),
    )
    await reply_func(reply)
    return True
