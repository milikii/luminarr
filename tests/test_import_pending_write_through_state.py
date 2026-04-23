from __future__ import annotations

from app.clients.transmission import TransmissionImportSource
from app.services.import_pending_write_through_state import ImportPendingWriteThroughState


def _build_import_source() -> TransmissionImportSource:
    return TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name="Dune.2021.mkv",
        download_dir="/data/downloads/tr",
        is_finished=True,
        percent_done=1.0,
    )


def test_persist_pending_import_records_event_and_trace_on_success() -> None:
    state = ImportPendingWriteThroughState(
        approval_repo=None,
        import_pending_state_unavailable_text="pending unavailable",
        import_approval_pending_text_template="导入待确认：{name}\n请发送 confirm {task_ref}",
    )
    events: list[dict[str, str]] = []
    traces: list[dict[str, str | int | None]] = []

    text = state.persist_pending_import(
        task_ref="87",
        import_source=_build_import_source(),
        chat_id=1001,
        user_id=2001,
        record_pending_approval=lambda **kwargs: 2,
        record_pending_job=lambda **kwargs: True,
        record_event=lambda **kwargs: events.append(kwargs),
        log_trace=lambda **kwargs: traces.append(kwargs),
    )

    assert "导入待确认：Dune.2021.mkv" in text
    assert "请发送 confirm 87" in text
    assert events == [
        {
            "task_ref": "87",
            "task_id": "87",
            "task_hash": "hash-87",
            "event_type": "import.approval_pending",
            "message": "87",
        }
    ]
    assert traces == [
        {
            "event": "approval_pending",
            "result": "created",
            "stage": "pending",
            "chat_id": 1001,
            "user_id": 2001,
            "task_ref": "87",
            "task_id": "87",
            "task_hash": "hash-87",
            "detail": "Dune.2021.mkv",
        }
    ]


def test_persist_pending_import_cancels_pending_approval_when_job_write_fails() -> None:
    cancelled: list[dict[str, str | int]] = []
    approval_repo = type("ApprovalRepo", (), {"cancel_import": lambda self, **kwargs: cancelled.append(kwargs)})()
    state = ImportPendingWriteThroughState(
        approval_repo=approval_repo,
        import_pending_state_unavailable_text="pending unavailable",
        import_approval_pending_text_template="unused {task_ref}",
    )

    text = state.persist_pending_import(
        task_ref="87",
        import_source=_build_import_source(),
        chat_id=1001,
        user_id=2001,
        record_pending_approval=lambda **kwargs: 2,
        record_pending_job=lambda **kwargs: False,
        record_event=lambda **kwargs: None,
        log_trace=lambda **kwargs: None,
    )

    assert text == "pending unavailable"
    assert cancelled == [
        {
            "task_id": "87",
            "task_hash": "hash-87",
            "task_ref": "87",
            "expected_lease_version": 2,
        }
    ]


def test_persist_pending_import_logs_when_cancel_pending_approval_fails(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"cancel_import": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))},
    )()
    state = ImportPendingWriteThroughState(
        approval_repo=approval_repo,
        import_pending_state_unavailable_text="pending unavailable",
        import_approval_pending_text_template="unused {task_ref}",
    )

    text = state.persist_pending_import(
        task_ref="87",
        import_source=_build_import_source(),
        chat_id=1001,
        user_id=2001,
        record_pending_approval=lambda **kwargs: 2,
        record_pending_job=lambda **kwargs: False,
        record_event=lambda **kwargs: None,
        log_trace=lambda **kwargs: None,
    )

    assert text == "pending unavailable"
    output = capsys.readouterr().out
    assert "[导入取消审批更新失败]" in output
    assert "task_ref=87" in output
    assert "lease_version=2" in output
    assert "db down" in output
