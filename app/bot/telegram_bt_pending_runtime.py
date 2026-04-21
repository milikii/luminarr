from __future__ import annotations

from typing import Literal

from telegram.ext import ContextTypes

from app.bot.bt_classification_runtime import (
    clear_bt_classification_pending as clear_shared_bt_classification_pending,
    is_bt_classification_pending as is_shared_bt_classification_pending,
    pop_bt_classification_pending as pop_shared_bt_classification_pending,
    set_bt_classification_pending as set_shared_bt_classification_pending,
)
from app.bot.bt_processing_path_runtime import (
    clear_bt_processing_path_pending as clear_shared_bt_processing_path_pending,
    is_bt_processing_path_pending as is_shared_bt_processing_path_pending,
    pop_bt_processing_path_pending as pop_shared_bt_processing_path_pending,
    set_bt_processing_path_pending as set_shared_bt_processing_path_pending,
)
from app.bot.bt_tmdb_association_runtime import (
    BtTmdbAssociationPending,
    clear_bt_tmdb_association_pending as clear_shared_bt_tmdb_association_pending,
    get_bt_tmdb_association_pending as get_shared_bt_tmdb_association_pending,
    set_bt_tmdb_association_pending as set_shared_bt_tmdb_association_pending,
)
from app.bot.raw_bt_destination_runtime import (
    RawBtDestinationPending,
    clear_raw_bt_destination_pending as clear_shared_raw_bt_destination_pending,
    get_raw_bt_destination_pending as get_shared_raw_bt_destination_pending,
    set_raw_bt_destination_pending as set_shared_raw_bt_destination_pending,
)
from app.config import RawBtDestinationOption


def set_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
    bt_pending_repo_key: str,
) -> bool:
    return set_shared_bt_processing_path_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        source=source,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def is_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    bt_pending_repo_key: str,
) -> bool | None:
    return is_shared_bt_processing_path_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def clear_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    bt_pending_repo_key: str,
) -> bool | None:
    return clear_shared_bt_processing_path_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def pop_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    bt_pending_repo_key: str,
) -> str | Literal[False] | None:
    return pop_shared_bt_processing_path_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def set_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    query: str,
    bt_pending_repo_key: str,
) -> bool:
    return set_shared_bt_classification_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        query=query,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def is_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    bt_pending_repo_key: str,
) -> bool | None:
    return is_shared_bt_classification_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def clear_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    bt_pending_repo_key: str,
) -> bool | None:
    return clear_shared_bt_classification_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def pop_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    bt_pending_repo_key: str,
) -> str | Literal[False] | None:
    return pop_shared_bt_classification_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def set_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    media_kind: str,
    source: str,
    bt_pending_repo_key: str,
) -> bool:
    return set_shared_bt_tmdb_association_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        media_kind=media_kind,
        source=source,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def get_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    bt_pending_repo_key: str,
) -> BtTmdbAssociationPending | None | Literal[False]:
    return get_shared_bt_tmdb_association_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def clear_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    bt_pending_repo_key: str,
) -> bool | None:
    return clear_shared_bt_tmdb_association_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def set_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    options: tuple[RawBtDestinationOption, ...],
    source: str,
    bt_pending_repo_key: str,
) -> bool:
    return set_shared_raw_bt_destination_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        options=options,
        source=source,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def get_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    bt_pending_repo_key: str,
) -> RawBtDestinationPending | None | Literal[False]:
    return get_shared_raw_bt_destination_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=bt_pending_repo_key,
    )


def clear_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    bt_pending_repo_key: str,
) -> bool | None:
    return clear_shared_raw_bt_destination_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=bt_pending_repo_key,
    )
