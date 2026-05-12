from __future__ import annotations

from dataclasses import dataclass

from app.db.sqlite import SqliteDatabase

BT_PENDING_STAGE_PROCESSING_PATH = "processing_path"
BT_PENDING_STAGE_CLASSIFICATION = "classification"
BT_PENDING_STAGE_TMDB_ASSOCIATION = "tmdb_association"
BT_PENDING_STAGE_RAW_BT_DESTINATION = "raw_bt_destination"
BT_PENDING_STAGE_DUPLICATE_OVERRIDE = "duplicate_override"


@dataclass(frozen=True, slots=True)
class BtPendingState:
    stage: str
    payload_json: str


class BtPendingPersistenceError(RuntimeError):
    pass


class BtPendingRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
        if chat_id <= 0:
            raise BtPendingPersistenceError("bt_pending_state chat identity missing")
        cleaned_stage = stage.strip()
        if not cleaned_stage:
            raise BtPendingPersistenceError("bt_pending_state stage missing")
        cleaned_payload = payload_json.strip()
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO bt_pending_state (
                    chat_id,
                    stage,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    stage = excluded.stage,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (chat_id, cleaned_stage, cleaned_payload),
            )
            connection.commit()
        pending_state = self.get_pending(chat_id=chat_id)
        if pending_state is None:
            raise BtPendingPersistenceError("bt_pending_state missing after upsert")

    def get_pending(self, *, chat_id: int) -> BtPendingState | None:
        if chat_id <= 0:
            raise BtPendingPersistenceError("bt_pending_state chat identity missing for query")
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT stage, payload_json
                FROM bt_pending_state
                WHERE chat_id = ?
                """,
                (chat_id,),
            ).fetchone()
        if row is None:
            return None
        cleaned_stage = str(row["stage"]).strip()
        if not cleaned_stage:
            raise BtPendingPersistenceError("bt_pending_state stage empty after read")
        return BtPendingState(
            stage=cleaned_stage,
            payload_json=str(row["payload_json"]).strip(),
        )

    def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
        if chat_id <= 0:
            raise BtPendingPersistenceError("bt_pending_state chat identity missing for clear")
        with self._database.connect() as connection:
            if expected_stage is None:
                cursor = connection.execute(
                    "DELETE FROM bt_pending_state WHERE chat_id = ?",
                    (chat_id,),
                )
            else:
                cleaned_stage = expected_stage.strip()
                if not cleaned_stage:
                    raise BtPendingPersistenceError("bt_pending_state expected stage missing for clear")
                cursor = connection.execute(
                    "DELETE FROM bt_pending_state WHERE chat_id = ? AND stage = ?",
                    (chat_id, cleaned_stage),
                )
            connection.commit()
        return cursor.rowcount > 0
