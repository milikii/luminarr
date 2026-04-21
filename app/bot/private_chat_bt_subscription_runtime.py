from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.downloader_execution_runtime import resolve_bound_downloader_execution
from app.bot.execution_runtime import bt_subscription_policy_action, run_sync_with_policy
from app.services.manage_bt_subscription import BtSubscriptionDispatchContext

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


def _resolve_bt_subscription_dispatch_context(
    *,
    bot_data: MutableMapping[str, object],
    tg,
):
    downloader_execution, resolution_error = resolve_bound_downloader_execution(
        bot_data=bot_data,
        role="bt",
        downloader_role_binding_key=tg.DOWNLOADER_ROLE_BINDING_KEY,
        downloader_instances_key=tg.DOWNLOADER_INSTANCES_KEY,
        config_missing_template=tg.DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE,
    )
    if resolution_error is not None:
        return None, resolution_error
    if downloader_execution is None:
        return None, tg.SERVICE_NOT_READY_TEXT
    return (
        BtSubscriptionDispatchContext(
            downloader_name=downloader_execution.name,
            downloader_type=downloader_execution.downloader_type,
            download_dir=downloader_execution.download_dir,
        ),
        None,
    )


async def handle_bt_subscription_query(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    user_id: int | None,
    tg,
) -> bool:
    bt_subscription_command = tg.parse_bt_subscription_query(query)
    if bt_subscription_command is None:
        return False

    bt_subscription_service = bot_data.get(tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY)
    if not isinstance(bt_subscription_service, tg.ManageBtSubscriptionService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True

    if bt_subscription_command.action == "run":
        dispatch_context, reply_text = _resolve_bt_subscription_dispatch_context(
            bot_data=bot_data,
            tg=tg,
        )
        if reply_text is not None:
            await reply_func(reply_text)
            return True
        reply = await execution_gate.run(
            bt_subscription_policy_action(bt_subscription_command),
            lambda: bt_subscription_service.run_once(
                chat_id=chat_id,
                user_id=user_id,
                dispatch_context=dispatch_context,
            ),
        )
        await reply_func(reply)
        return True

    reply = await run_sync_with_policy(
        execution_gate,
        bt_subscription_policy_action(bt_subscription_command),
        lambda: bt_subscription_service.handle(
            bt_subscription_command,
            chat_id=chat_id,
        ),
    )
    await reply_func(reply)
    return True
