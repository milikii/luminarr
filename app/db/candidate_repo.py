from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.db.sqlite import SqliteDatabase


class CandidatePayloadCorruptionError(ValueError):
    pass


class CandidatePersistenceError(RuntimeError):
    pass


class CandidateMappingRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def save_candidates(self, chat_id: int, candidates: Sequence[Mapping[str, Any]]) -> None:
        normalized_candidates = [_normalize_payload(candidate) for candidate in candidates]
        with self._database.connect() as connection:
            connection.execute("DELETE FROM candidate_mapping WHERE chat_id = ?", (chat_id,))
            for index, candidate in enumerate(normalized_candidates, start=1):
                payload = json.dumps(candidate, ensure_ascii=False)
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
        if self._count_candidates(chat_id=chat_id) != len(normalized_candidates):
            raise CandidatePersistenceError("candidate_mapping count mismatch after save")

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
            raise CandidatePayloadCorruptionError("candidate_json invalid json") from None
        if not isinstance(payload, dict):
            raise CandidatePayloadCorruptionError("candidate_json not object")
        return {str(key): value for key, value in payload.items()}

    def _count_candidates(self, *, chat_id: int) -> int:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM candidate_mapping WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        if row is None:
            return 0
        return int(row["total"])


def _normalize_payload(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in candidate.items()}
