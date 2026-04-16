from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.db.sqlite import SqliteDatabase

VALID_MEDIA_KINDS = frozenset({"movie", "series", "anime"})


class WatchlistPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WatchlistItem:
    item_id: int
    chat_id: int
    title: str
    year: str
    media_kind: str
    created_at: str
    updated_at: str


class WatchlistRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def add_item(
        self,
        *,
        chat_id: int,
        title: str,
        year: str,
        media_kind: str,
    ) -> tuple[WatchlistItem, bool] | None:
        cleaned_title = title.strip()
        cleaned_year = year.strip()
        cleaned_media_kind = _normalize_media_kind(media_kind)
        if chat_id <= 0:
            raise WatchlistPersistenceError("watchlist_item chat identity missing")
        if not cleaned_title:
            raise WatchlistPersistenceError("watchlist_item title missing")

        existing = self.get_item_by_identity(
            chat_id=chat_id,
            title=cleaned_title,
            year=cleaned_year,
            media_kind=cleaned_media_kind,
        )
        if existing is not None:
            return existing, False

        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO watchlist_item (
                    chat_id,
                    title,
                    year,
                    media_kind,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (chat_id, cleaned_title, cleaned_year, cleaned_media_kind),
            )
            connection.commit()
            item_id = int(cursor.lastrowid)

        created_item = self.get_item_by_id(chat_id=chat_id, item_id=item_id)
        if created_item is None:
            raise WatchlistPersistenceError("watchlist_item missing after insert")
        return created_item, True

    def list_items(self, *, chat_id: int) -> list[WatchlistItem]:
        if chat_id <= 0:
            raise WatchlistPersistenceError("watchlist_item chat identity missing for list")
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    title,
                    year,
                    media_kind,
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
            raise WatchlistPersistenceError("watchlist_item identity missing for remove")
        with self._database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM watchlist_item WHERE chat_id = ? AND id = ?",
                (chat_id, item_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def clear_items(self, *, chat_id: int) -> int:
        if chat_id <= 0:
            raise WatchlistPersistenceError("watchlist_item chat identity missing for clear")
        with self._database.connect() as connection:
            cursor = connection.execute("DELETE FROM watchlist_item WHERE chat_id = ?", (chat_id,))
            connection.commit()
        return max(0, cursor.rowcount)

    def get_item_by_id(self, *, chat_id: int, item_id: int) -> WatchlistItem | None:
        if chat_id <= 0 or item_id <= 0:
            raise WatchlistPersistenceError("watchlist_item identity missing for id lookup")
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    title,
                    year,
                    media_kind,
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

    def get_item_by_identity(
        self,
        *,
        chat_id: int,
        title: str,
        year: str,
        media_kind: str,
    ) -> WatchlistItem | None:
        cleaned_title = title.strip()
        cleaned_year = year.strip()
        cleaned_media_kind = _normalize_media_kind(media_kind)
        if chat_id <= 0:
            raise WatchlistPersistenceError("watchlist_item identity missing for exact lookup")
        if not cleaned_title:
            raise WatchlistPersistenceError("watchlist_item title missing for exact lookup")
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    title,
                    year,
                    media_kind,
                    created_at,
                    updated_at
                FROM watchlist_item
                WHERE chat_id = ? AND title = ? AND year = ? AND media_kind = ?
                LIMIT 1
                """,
                (chat_id, cleaned_title, cleaned_year, cleaned_media_kind),
            ).fetchone()
        if row is None:
            return None
        return _to_watchlist_item(row)


def _to_watchlist_item(row: Mapping[str, object]) -> WatchlistItem:
    item_id = int(row["id"])
    chat_id = int(row["chat_id"])
    title = str(row["title"]).strip()
    raw_media_kind = str(row["media_kind"]).strip().lower()

    if item_id <= 0 or chat_id <= 0 or not title:
        raise WatchlistPersistenceError("watchlist_item row identity corrupted after read")
    if raw_media_kind not in VALID_MEDIA_KINDS:
        raise WatchlistPersistenceError("watchlist_item media kind corrupted after read")

    return WatchlistItem(
        item_id=item_id,
        chat_id=chat_id,
        title=title,
        year=str(row["year"]),
        media_kind=raw_media_kind,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _normalize_media_kind(media_kind: str) -> str:
    cleaned_media_kind = media_kind.strip().lower()
    if cleaned_media_kind in VALID_MEDIA_KINDS:
        return cleaned_media_kind
    return "movie"
