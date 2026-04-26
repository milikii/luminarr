from __future__ import annotations

from pathlib import Path

from app.db.job_repo import WORKFLOW_IMPORT_TO_LIBRARY
from app.services.workflow_trace_logger import WorkflowTraceLogger


class ImportTraceLogger:
    def __init__(self, trace_log_path: Path | None) -> None:
        self._trace_logger = WorkflowTraceLogger(WORKFLOW_IMPORT_TO_LIBRARY, trace_log_path)

    def log(
        self,
        *,
        event: str,
        result: str,
        stage: str,
        chat_id: int | None = None,
        user_id: int | None = None,
        task_ref: str = "",
        task_id: str = "",
        task_hash: str = "",
        detail: str = "",
    ) -> None:
        self._trace_logger.log(
            event=event,
            result=result,
            stage=stage,
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            detail=detail,
        )
