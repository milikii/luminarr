from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


async def handle_personal_wechat_login_query(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    if not tg.parse_personal_wechat_login_query(query):
        return False

    personal_wechat_login_service = bot_data.get(tg.PERSONAL_WECHAT_LOGIN_SERVICE_KEY)
    telegram_send_media_func = bot_data.get(tg.TELEGRAM_SEND_MEDIA_FUNC_KEY)
    telegram_send_text_func = bot_data.get(tg.TELEGRAM_SEND_TEXT_FUNC_KEY)
    if (
        not isinstance(personal_wechat_login_service, tg.PersonalWeChatLoginService)
        or not callable(telegram_send_media_func)
        or chat_id is None
    ):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True

    reply = await execution_gate.run(
        tg.ACTION_PERSONAL_WECHAT_LOGIN,
        lambda: personal_wechat_login_service.start_login(
            chat_id=chat_id,
            send_media_func=telegram_send_media_func,
            send_text_func=telegram_send_text_func if callable(telegram_send_text_func) else None,
        ),
    )
    await reply_func(reply)
    return True
