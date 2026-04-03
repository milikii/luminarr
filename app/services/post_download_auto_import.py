from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.db.download_monitor_repo import DownloadMonitorRecord, DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo

AutoImportFunc = Callable[[str, int | None, int | None], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class AutoImportRunResult:
    scanned: int
    progressed: int
    replies: tuple[str, ...]


class PostDownloadAutoImportService:
    def __init__(
        self,
        download_monitor_repo: DownloadMonitorRepo,
        job_event_repo: JobEventRepo,
        auto_import_func: AutoImportFunc,
    ) -> None:
        self._download_monitor_repo = download_monitor_repo
        self._job_event_repo = job_event_repo
        self._auto_import_func = auto_import_func

    async def run_once(self, *, limit: int = 20) -> AutoImportRunResult:
        candidates = self._download_monitor_repo.list_completed_for_auto_import(limit=limit)
        replies: list[str] = []
        progressed = 0

        for candidate in candidates:
            reply = await self.run_for_record(candidate)
            if reply is None:
                continue
            replies.append(reply)
            progressed += 1

        return AutoImportRunResult(
            scanned=len(candidates),
            progressed=progressed,
            replies=tuple(replies),
        )

    async def run_for_record(self, candidate: DownloadMonitorRecord) -> str | None:
        if not candidate.is_complete or candidate.chat_id <= 0:
            return None
        if self._has_import_activity(candidate):
            return None
        user_id = candidate.user_id if candidate.user_id > 0 else None
        return await self._auto_import_func(candidate.task_hash, candidate.chat_id, user_id)

    def _has_import_activity(self, candidate: DownloadMonitorRecord) -> bool:
        try:
            events = self._job_event_repo.list_events_for_task_identity(
                task_id=candidate.task_id,
                task_hash=candidate.task_hash,
            )
        except Exception:
            return False
        return any(event.event_type.startswith("import.") for event in events)
