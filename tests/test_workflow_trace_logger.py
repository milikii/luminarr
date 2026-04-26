from __future__ import annotations

from pathlib import Path

from app.services.workflow_trace_logger import WorkflowTraceLogger
from app.trace_logging import parse_trace_log_line


def test_workflow_trace_logger_writes_workflow_trace(tmp_path: Path) -> None:
    log_path = tmp_path / "trace.log"
    logger = WorkflowTraceLogger("cleanup", log_path)

    logger.log(
        event="inspect",
        result="ok",
        stage="preflight",
        chat_id=1001,
        user_id=2001,
        task_ref="ref-1",
        task_id="task-1",
        task_hash="hash-1",
        detail="cleanup inspect",
    )

    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    parsed = parse_trace_log_line(lines[0])
    assert parsed is not None
    assert parsed.workflow == "cleanup"
    assert parsed.event == "inspect"
    assert parsed.result == "ok"
    assert parsed.stage == "preflight"
    assert parsed.task_ref == "ref-1"
