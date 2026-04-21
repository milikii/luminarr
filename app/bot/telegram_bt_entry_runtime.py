from __future__ import annotations

from telegram.ext import ContextTypes


def enter_pure_bt_flow(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
    enter_shared_pure_bt_flow,
    raw_bt_destination_options_key: str,
    bt_pending_repo_key: str,
    raw_bt_destination_service_not_ready_text: str,
    service_not_ready_text: str,
) -> str:
    return enter_shared_pure_bt_flow(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        source=source,
        raw_bt_destination_options_key=raw_bt_destination_options_key,
        bt_pending_repo_key=bt_pending_repo_key,
        raw_bt_destination_service_not_ready_text=raw_bt_destination_service_not_ready_text,
        service_not_ready_text=service_not_ready_text,
    )


def enter_media_import_bt_flow(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
    enter_shared_media_import_bt_flow,
    bt_pending_repo_key: str,
    service_not_ready_text: str,
    bt_classification_prompt_text: str,
    media_kind: str | None = None,
) -> str:
    return enter_shared_media_import_bt_flow(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        source=source,
        media_kind=media_kind,
        bt_pending_repo_key=bt_pending_repo_key,
        service_not_ready_text=service_not_ready_text,
        bt_classification_prompt_text=bt_classification_prompt_text,
    )
