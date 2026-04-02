from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.db.sqlite import SqliteDatabase


@dataclass(frozen=True, slots=True)
class WatchlistItem:
    item_id: int
    chat_id: int
    title: str
    year: str
    created_at: str
    updated_at: str


class WatchlistRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def add_item(self, *, chat_id: int, title: str, year: str) -> tuple[WatchlistItem, bool] | None:
        cleaned_title = title.strip()
        cleaned_year = year.strip()
        if chat_id <= 0 or not cleaned_title:
            return None

        existing = self.get_item_by_identity(chat_id=chat_id, title=cleaned_title, year=cleaned_year)
        if existing is not None:
            return existing, False

        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO watchlist_item (
                    chat_id,
                    title,
                    year,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (chat_id, cleaned_title, cleaned_year),
            )
            connection.commit()
            item_id = int(cursor.lastrowid)

        created_item = self.get_item_by_id(chat_id=chat_id, item_id=item_id)
        if created_item is None:
            return None
        return created_item, True

    def list_items(self, *, chat_id: int) -> list[WatchlistItem]:
        if chat_id <= 0:
            return []
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    title,
                    year,
                    created_at,
                    updated_at
                FROM watchlist_item
                WHERE chat_id = ?
                ORDER BY id DESC
                """,
                (chat_id,),
            ).fetchall()
        return [_to_watchlist_item(row) for row in rows]

    def remove_item(self, *, chat_id: int, item_id: int) -> bool:
        if chat_id <= 0 or item_id <= 0:
            return False
        with self._database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM watchlist_item WHERE chat_id = ? AND id = ?",
                (chat_id, item_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def clear_items(self, *, chat_id: int) -> int:
        if chat_id <= 0:
            return 0
        with self._database.connect() as connection:
            cursor = connection.execute("DELETE FROM watchlist_item WHERE chat_id = ?", (chat_id,))
            connection.commit()
        return max(0, cursor.rowcount)

    def get_item_by_id(self, *, chat_id: int, item_id: int) -> WatchlistItem | None:
        if chat_id <= 0 or item_id <= 0:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    title,
                    year,
                    created_at,
                    updated_at
                FROM watchlist_item
                WHERE chat_id = ? AND id = ?
                LIMIT 1
                """,
                (chat_id, item_id),
            ).fetchone()
        if row is None:
            return None
        return _to_watchlist_item(row)

    def get_item_by_identity(self, *, chat_id: int, title: str, year: str) -> WatchlistItem | None:
        cleaned_title = title.strip()
        cleaned_year = year.strip()
        if chat_id <= 0 or not cleaned_title:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    title,
                    year,
                    created_at,
                    updated_at
                FROM watchlist_item
                WHERE chat_id = ? AND title = ? AND year = ?
                LIMIT 1
                """,
                (chat_id, cleaned_title, cleaned_year),
            ).fetchone()
        if row is None:
            return None
        return _to_watchlist_item(row)


def _to_watchlist_item(row: Mapping[str, object]) -> WatchlistItem:
    return WatchlistItem(
        item_id=int(row["id"]),
        chat_id=int(row["chat_id"]),
        title=str(row["title"]),
        year=str(row["year"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
