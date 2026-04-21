from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.cleanup_smoke_logging import log_cleanup_private_chat_smoke
from app.bot.execution_runtime import run_sync_with_policy

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


def _log_cleanup_service_not_ready(*, action: str, query: str) -> None:
    print(
        f"\033[31m[cleanup 服务未就绪]\033[0m 动作={action} 查询={query.strip() or '-'}\n"
        "\033[33m[处理建议]\033[0m 检查应用启动阶段是否已注入 cleanup_downloaded_source_service，"
        "并确认 CleanupDownloadedSourceService 实例创建成功后重试。"
    )


async def _run_cleanup_request(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    action: str,
    query: str,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    cleanup_runner: Callable[[object], str],
    tg,
) -> bool:
    cleanup_service = bot_data.get(tg.CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY)
    if not isinstance(cleanup_service, tg.CleanupDownloadedSourceService):
        _log_cleanup_service_not_ready(action=action, query=query)
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    reply = await run_sync_with_policy(
        execution_gate,
        action,
        lambda: cleanup_runner(cleanup_service),
    )
    await reply_func(reply)
    log_cleanup_private_chat_smoke(
        channel=channel,
        query=query,
        reply_text=reply,
        chat_id=chat_id,
        user_id=user_id,
    )
    return True


async def handle_cleanup_query(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    tg,
) -> bool:
    cleanup_inspect_ref = tg.parse_cleanup_inspect_query(query)
    if cleanup_inspect_ref is not None:
        return await _run_cleanup_request(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=chat_id,
            user_id=user_id,
            channel=channel,
            action=tg.ACTION_CLEANUP_INSPECT,
            query=query,
            cleanup_runner=lambda cleanup_service: cleanup_service.inspect_by_task_ref(
                cleanup_inspect_ref,
                chat_id=chat_id,
            ),
            tg=tg,
        )

    cleanup_ref = tg.parse_cleanup_query(query)
    if cleanup_ref is not None:
        return await _run_cleanup_request(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            action=tg.ACTION_CLEANUP_DOWNLOADER_SOURCE,
            query=query,
            chat_id=chat_id,
            user_id=user_id,
            channel=channel,
            cleanup_runner=lambda cleanup_service: cleanup_service.cleanup_by_task_ref(
                cleanup_ref,
                chat_id=chat_id,
            ),
            tg=tg,
        )

    return False
