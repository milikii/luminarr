from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.db.sqlite import SqliteDatabase


class CandidateMappingRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def save_candidates(self, chat_id: int, candidates: Sequence[Mapping[str, Any]]) -> None:
        with self._database.connect() as connection:
            connection.execute("DELETE FROM candidate_mapping WHERE chat_id = ?", (chat_id,))
            for index, candidate in enumerate(candidates, start=1):
                payload = json.dumps(_normalize_payload(candidate), ensure_ascii=False)
                connection.execute(
                    """
                    INSERT INTO candidate_mapping (
                        chat_id,
                        selection_index,
                        candidate_json,
                        updated_at
                    ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (chat_id, index, payload),
                )
            connection.commit()

    def clear_candidates(self, chat_id: int) -> bool:
        with self._database.connect() as connection:
            cursor = connection.execute("DELETE FROM candidate_mapping WHERE chat_id = ?", (chat_id,))
            connection.commit()
        return cursor.rowcount > 0

    def get_candidate(self, chat_id: int, selection_index: int) -> Mapping[str, Any] | None:
        if selection_index < 1:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT candidate_json
                FROM candidate_mapping
                WHERE chat_id = ? AND selection_index = ?
                """,
                (chat_id, selection_index),
            ).fetchone()
        if row is None:
            return None
        raw_payload = row["candidate_json"]
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return {str(key): value for key, value in payload.items()}


def _normalize_payload(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in candidate.items()}
