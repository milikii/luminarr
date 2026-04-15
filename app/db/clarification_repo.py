from __future__ import annotations

from app.db.sqlite import SqliteDatabase


class ClarificationPersistenceError(RuntimeError):
    pass


class ClarificationRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def upsert_pending(self, *, chat_id: int, query: str) -> None:
        if chat_id <= 0:
            raise ClarificationPersistenceError("clarification_state chat identity missing")
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ClarificationPersistenceError("clarification_state query missing")
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO clarification_state (
                    chat_id,
                    query,
                    updated_at
                ) VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    query = excluded.query,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (chat_id, cleaned_query),
            )
            connection.commit()
        persisted_query = self.get_pending_query(chat_id=chat_id)
        if persisted_query is None:
            raise ClarificationPersistenceError("clarification_state missing after upsert")

    def get_pending_query(self, *, chat_id: int) -> str | None:
        if chat_id <= 0:
            raise ClarificationPersistenceError("clarification_state chat identity missing for query")
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT query
                FROM clarification_state
                WHERE chat_id = ?
                """,
                (chat_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["query"]).strip()

    def clear_pending(self, *, chat_id: int) -> bool:
        if chat_id <= 0:
            raise ClarificationPersistenceError("clarification_state chat identity missing for clear")
        with self._database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM clarification_state WHERE chat_id = ?",
                (chat_id,),
            )
            connection.commit()
        return cursor.rowcount > 0
