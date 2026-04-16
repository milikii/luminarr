from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.db.sqlite import SqliteDatabase

VALID_BT_SUBSCRIPTION_MEDIA_KINDS = frozenset({"movie", "series", "anime"})


class BtSubscriptionPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BtSubscriptionItem:
    item_id: int
    chat_id: int
    title: str
    year: str
    media_kind: str
    last_seen_source: str
    last_seen_title: str
    created_at: str
    updated_at: str


class BtSubscriptionRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def add_item(
        self,
        *,
        chat_id: int,
        title: str,
        year: str,
        media_kind: str,
    ) -> tuple[BtSubscriptionItem, bool] | None:
        cleaned_title = title.strip()
        cleaned_year = year.strip()
        cleaned_kind = media_kind.strip().lower()
        if chat_id <= 0:
            raise BtSubscriptionPersistenceError("bt_subscription_item chat identity missing")
        if not cleaned_title:
            raise BtSubscriptionPersistenceError("bt_subscription_item title missing")
        if not cleaned_kind:
            raise BtSubscriptionPersistenceError("bt_subscription_item media kind missing")
        if cleaned_kind not in VALID_BT_SUBSCRIPTION_MEDIA_KINDS:
            raise BtSubscriptionPersistenceError("bt_subscription_item media kind invalid")

        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO bt_subscription_item (
                    chat_id,
                    title,
                    year,
                    media_kind,
                    last_seen_source,
                    last_seen_title,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, '', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id, title, year, media_kind)
                DO NOTHING
                """,
                (chat_id, cleaned_title, cleaned_year, cleaned_kind),
            )
            row = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    title,
                    year,
                    media_kind,
                    last_seen_source,
                    last_seen_title,
                    created_at,
                    updated_at
                FROM bt_subscription_item
                WHERE chat_id = ? AND title = ? AND year = ? AND media_kind = ?
                LIMIT 1
                """,
                (chat_id, cleaned_title, cleaned_year, cleaned_kind),
            ).fetchone()
            connection.commit()
        if row is None:
            raise BtSubscriptionPersistenceError("bt_subscription_item missing after insert")
        return _to_bt_subscription_item(row), cursor.rowcount == 1

    def list_items(self, *, chat_id: int) -> list[BtSubscriptionItem]:
        if chat_id <= 0:
            raise BtSubscriptionPersistenceError("bt_subscription_item chat identity missing for list")
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    title,
                    year,
                    media_kind,
                    last_seen_source,
                    last_seen_title,
                    created_at,
                    updated_at
                FROM bt_subscription_item
                WHERE chat_id = ?
                ORDER BY id ASC
                """,
                (chat_id,),
            ).fetchall()
        return [_to_bt_subscription_item(row) for row in rows]

    def list_chat_ids(self) -> list[int]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT chat_id
                FROM bt_subscription_item
                WHERE chat_id > 0
                ORDER BY chat_id ASC
                """
            ).fetchall()
        return [int(row["chat_id"]) for row in rows]

    def remove_item(self, *, chat_id: int, item_id: int) -> bool:
        if chat_id <= 0 or item_id <= 0:
            raise BtSubscriptionPersistenceError("bt_subscription_item identity missing for remove")
        with self._database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM bt_subscription_item WHERE chat_id = ? AND id = ?",
                (chat_id, item_id),
            )
            connection.commit()
        return cursor.rowcount == 1

    def clear_items(self, *, chat_id: int) -> int:
        if chat_id <= 0:
            raise BtSubscriptionPersistenceError("bt_subscription_item chat identity missing for clear")
        with self._database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM bt_subscription_item WHERE chat_id = ?",
                (chat_id,),
            )
            connection.commit()
        return int(cursor.rowcount)

    def update_last_seen(
        self,
        *,
        chat_id: int,
        item_id: int,
        source: str,
        title: str,
    ) -> bool:
        cleaned_source = source.strip()
        cleaned_title = title.strip()
        if chat_id <= 0 or item_id <= 0:
            raise BtSubscriptionPersistenceError("bt_subscription_item identity missing for last_seen update")
        if not cleaned_source:
            raise BtSubscriptionPersistenceError("bt_subscription_item source missing for last_seen update")
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE bt_subscription_item
                SET
                    last_seen_source = ?,
                    last_seen_title = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE chat_id = ? AND id = ?
                """,
                (cleaned_source, cleaned_title, chat_id, item_id),
            )
            connection.commit()
        if cursor.rowcount == 1:
            return True
        raise BtSubscriptionPersistenceError("bt_subscription_item missing during last_seen update")


def _to_bt_subscription_item(row: Mapping[str, object]) -> BtSubscriptionItem:
    item_id = int(row["id"])
    chat_id = int(row["chat_id"])
    title = str(row["title"]).strip()
    media_kind = str(row["media_kind"]).strip().lower()

    if item_id <= 0 or chat_id <= 0 or not title:
        raise BtSubscriptionPersistenceError("bt_subscription_item row identity corrupted after read")
    if media_kind not in VALID_BT_SUBSCRIPTION_MEDIA_KINDS:
        raise BtSubscriptionPersistenceError("bt_subscription_item media kind corrupted after read")

    return BtSubscriptionItem(
        item_id=item_id,
        chat_id=chat_id,
        title=title,
        year=str(row["year"]),
        media_kind=media_kind,
        last_seen_source=str(row["last_seen_source"]),
        last_seen_title=str(row["last_seen_title"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
