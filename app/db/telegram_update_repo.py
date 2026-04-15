from __future__ import annotations

from app.db.sqlite import SqliteDatabase

SOURCE_TYPE_CALLBACK = "callback"
SOURCE_TYPE_MESSAGE = "message"


class TelegramUpdatePersistenceError(RuntimeError):
    pass


class TelegramUpdateRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def record_message_update(
        self,
        *,
        update_id: int,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> bool:
        if update_id <= 0:
            raise TelegramUpdatePersistenceError("message update_id missing or invalid")
        return self._record_update(
            source_type=SOURCE_TYPE_MESSAGE,
            source_id=str(update_id),
            chat_id=chat_id,
            user_id=user_id,
        )

    def record_callback_update(
        self,
        *,
        callback_query_id: str,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> bool:
        cleaned_id = callback_query_id.strip()
        if not cleaned_id:
            raise TelegramUpdatePersistenceError("callback_query_id missing")
        return self._record_update(
            source_type=SOURCE_TYPE_CALLBACK,
            source_id=cleaned_id,
            chat_id=chat_id,
            user_id=user_id,
        )

    def _record_update(
        self,
        *,
        source_type: str,
        source_id: str,
        chat_id: int | None,
        user_id: int | None,
    ) -> bool:
        cleaned_type = source_type.strip()
        cleaned_id = source_id.strip()
        if not cleaned_type or not cleaned_id:
            raise TelegramUpdatePersistenceError("telegram update identity missing")

        update_key = f"{cleaned_type}:{cleaned_id}"
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO telegram_updates (
                    update_key,
                    source_type,
                    source_id,
                    chat_id,
                    user_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    update_key,
                    cleaned_type,
                    cleaned_id,
                    int(chat_id or 0),
                    int(user_id or 0),
                ),
            )
            connection.commit()
        return cursor.rowcount == 1
