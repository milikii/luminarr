from __future__ import annotations

from pathlib import Path

from app.trace_logging import log_trace_event


class WorkflowTraceLogger:
    def __init__(self, workflow: str, trace_log_path: Path | None) -> None:
        self._workflow = workflow
        self._trace_log_path = trace_log_path

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
        log_trace_event(
            scope="workflow",
            workflow=self._workflow,
            event=event,
            result=result,
            stage=stage,
            log_path=self._trace_log_path,
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            detail=detail,
        )
