from __future__ import annotations

from pathlib import Path

import pytest

from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
from app.services import cleanup_downloaded_source as cleanup_module
from app.services.cleanup_downloaded_source import (
    CLEANUP_CORRELATION_MISSING_TEXT,
    CLEANUP_GUARD_REJECTED_TEXT,
    CLEANUP_INSPECT_QUERY_USAGE_TEXT,
    CLEANUP_QUERY_USAGE_TEXT,
    CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT,
    CLEANUP_TARGET_MISSING_TEXT,
    CleanupDownloadedSourceService,
    parse_cleanup_inspect_query,
    parse_cleanup_query,
)


def test_parse_cleanup_query_supports_prefixes() -> None:
    assert parse_cleanup_query("cleanup 87") == "87"
    assert parse_cleanup_query("CLEANUP hash-87") == "hash-87"
    assert parse_cleanup_query("ClEaNuP hash-87") == "hash-87"
    assert parse_cleanup_query("清理 abc123") == "abc123"
    assert parse_cleanup_query("cleanup") == ""


def test_parse_cleanup_inspect_query_supports_prefixes() -> None:
    assert parse_cleanup_inspect_query("cleanup inspect 87") == "87"
    assert parse_cleanup_inspect_query("cleanup inspect hash-87") == "hash-87"
    assert parse_cleanup_inspect_query("ClEaNuP InSpEcT hash-87") == "hash-87"
    assert parse_cleanup_inspect_query("清理检查 abc123") == "abc123"
    assert parse_cleanup_inspect_query("cleanup inspect") == ""


def test_parse_cleanup_query_rejects_non_cleanup_text() -> None:
    assert parse_cleanup_query("import 87") is None
    assert parse_cleanup_query("dune") is None
    assert parse_cleanup_inspect_query("cleanup 87") is None


def test_inspect_by_task_ref_usage_when_empty(tmp_path: Path) -> None:
    service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))
    assert service.inspect_by_task_ref("  ") == CLEANUP_INSPECT_QUERY_USAGE_TEXT
    assert "只读预检，不删除任何文件" in CLEANUP_INSPECT_QUERY_USAGE_TEXT
    assert "实际清理下载源资产" in CLEANUP_INSPECT_QUERY_USAGE_TEXT


def test_inspect_by_task_ref_returns_ready_text_without_deleting_source(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.inspect_by_task_ref("87")

    assert "清理预检结果：" in reply
    assert "关联: 已找到" in reply
    assert f"源路径: {source_file}" in reply
    assert "源路径状态: 存在" in reply
    assert f"目标路径: {target_file}" in reply
    assert "目标路径状态: 存在" in reply
    assert "当前 guardrail: 允许 cleanup" in reply
    assert "下一步：" in reply
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply
    assert source_file.exists()
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert len(events) == 1


def test_inspect_by_task_ref_returns_correlation_missing_state(tmp_path: Path) -> None:
    service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))

    reply = service.inspect_by_task_ref("87")

    assert "任务 ID: -" in reply
    assert "任务 Hash: -" in reply
    assert "关联: 未找到" in reply
    assert "源路径状态: 未找到关联" in reply
    assert "目标路径状态: 未找到关联" in reply
    assert "当前 guardrail: 拒绝 cleanup" in reply
    assert f"结论: {CLEANUP_CORRELATION_MISSING_TEXT}" in reply
    assert "下一步：" not in reply


def test_inspect_by_task_ref_returns_blocked_follow_up_when_guard_rejected(tmp_path: Path) -> None:
    source_dir = tmp_path / "downloads" / "Dune.Part.Two.2024"
    source_dir.mkdir(parents=True)
    target_file = source_dir / "movie.mkv"
    target_file.write_bytes(b"demo")

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_dir),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.inspect_by_task_ref("87")

    assert "当前 guardrail: 拒绝 cleanup" in reply
    assert "下一步：" in reply
    assert "当前先不要执行 cleanup" in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in reply


def test_cleanup_by_task_ref_usage_when_empty(tmp_path: Path) -> None:
    service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))
    assert service.cleanup_by_task_ref("  ") == CLEANUP_QUERY_USAGE_TEXT
    assert "实际清理下载源资产" in CLEANUP_QUERY_USAGE_TEXT
    assert "只读预检，不删除任何文件" in CLEANUP_QUERY_USAGE_TEXT


def test_cleanup_by_task_ref_removes_source_file_and_keeps_target(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    assert "已清理下载源资产" in reply
    assert str(source_file) in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    assert not source_file.exists()
    assert target_file.exists()
    assert target_file.read_bytes() == b"demo"
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert events[-1].event_type == "cleanup.succeeded"
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in events[-1].message


def test_inspect_by_task_ref_reports_source_missing_after_cleanup_success(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    cleanup_reply = service.cleanup_by_task_ref("87")
    inspect_reply = service.inspect_by_task_ref("87")

    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in cleanup_reply
    assert "源路径状态: 不存在" in inspect_reply
    assert "目标路径状态: 存在" in inspect_reply
    assert f"结论: 下载源资产已不存在，无需清理：{source_file}" in inspect_reply
    assert "当前先不要执行 cleanup" in inspect_reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in inspect_reply


def test_cleanup_by_task_ref_rejects_missing_structured_source_path(tmp_path: Path) -> None:
    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.write_bytes(b"demo")

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    assert CLEANUP_CORRELATION_MISSING_TEXT in reply
    assert "cleanup inspect 87 / 清理检查 87：只读预检，不删除任何文件" in reply
    assert "cleanup 87 / 清理 87：实际清理下载源资产" in reply


def test_cleanup_by_task_ref_logs_missing_structured_source_path(tmp_path: Path, capsys) -> None:
    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.write_bytes(b"demo")

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    assert CLEANUP_CORRELATION_MISSING_TEXT in reply
    output = capsys.readouterr().out
    assert "[cleanup 关联路径缺失]" in output
    assert "missing_fields=source_path" in output
    assert "[处理建议]" in output


def test_cleanup_by_task_ref_logs_missing_structured_target_path(tmp_path: Path, capsys) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    service = CleanupDownloadedSourceService(
        type(
            "MissingTargetPathRepo",
            (),
            {
                "find_latest_import_correlation": lambda self, **kwargs: type(
                    "Event",
                    (),
                    {
                        "task_ref": "87",
                        "task_id": "87",
                        "task_hash": "hash-87",
                        "event_type": "import.succeeded",
                        "message": "",
                        "source_path": str(source_file),
                        "target_path": "",
                    },
                )()
            },
        )()
    )

    reply = service.cleanup_by_task_ref("87")

    assert CLEANUP_CORRELATION_MISSING_TEXT in reply
    output = capsys.readouterr().out
    assert "[cleanup 关联路径缺失]" in output
    assert "missing_fields=target_path" in output
    assert "[处理建议]" in output


def test_cleanup_by_task_ref_rejects_when_target_missing(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_file = tmp_path / "library" / "Dune (2021).mkv"
    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    assert CLEANUP_TARGET_MISSING_TEXT.format(target_path=str(target_file)) in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    assert source_file.exists()


def test_cleanup_by_task_ref_rejects_overlapping_source_and_target(tmp_path: Path) -> None:
    source_dir = tmp_path / "downloads" / "Dune.Part.Two.2024"
    source_dir.mkdir(parents=True)
    target_file = source_dir / "movie.mkv"
    target_file.write_bytes(b"demo")

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_dir),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    assert CLEANUP_GUARD_REJECTED_TEXT.format(
        source_path=str(source_dir),
        target_path=str(target_file),
    ) in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    assert source_dir.exists()


def test_cleanup_by_task_ref_appends_follow_up_when_delete_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)
    monkeypatch.setattr(
        cleanup_module,
        "_delete_source_asset",
        lambda source_path: (_ for _ in ()).throw(OSError("mock delete denied")),
    )

    reply = service.cleanup_by_task_ref("87")

    assert "清理下载源资产失败：mock delete denied" in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    assert source_file.exists()
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert events[-1].event_type == "cleanup.failed"
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in events[-1].message


def test_cleanup_by_task_ref_logs_delete_failure_with_fix_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)
    monkeypatch.setattr(
        cleanup_module,
        "_delete_source_asset",
        lambda source_path: (_ for _ in ()).throw(OSError("mock delete denied")),
    )

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert "清理下载源资产失败：mock delete denied" in reply
    assert "[cleanup 执行失败]" in captured.out
    assert "task_ref=87" in captured.out
    assert "event_type=cleanup.failed" in captured.out
    assert "task_id=87" in captured.out
    assert "task_hash=hash-87" in captured.out
    assert f"source={source_file}" in captured.out
    assert f"target={target_file}" in captured.out
    assert "原因=mock delete denied" in captured.out
    assert "[处理建议]" in captured.out
    assert "检查 source_path 是否仍可访问、当前进程是否有删除权限" in captured.out
    assert source_file.exists()
    assert target_file.exists()


def test_cleanup_by_task_ref_keeps_chat_scoped_identity_when_delete_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)
    monkeypatch.setattr(
        cleanup_module,
        "_delete_source_asset",
        lambda source_path: (_ for _ in ()).throw(OSError("mock delete denied")),
    )

    reply = service.cleanup_by_task_ref("cleanup-shortcut", chat_id=1001)

    assert "清理下载源资产失败：mock delete denied" in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert events[-1].event_type == "cleanup.failed"
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in events[-1].message


def test_cleanup_by_task_ref_logs_delete_failure_with_chat_scoped_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)
    monkeypatch.setattr(
        cleanup_module,
        "_delete_source_asset",
        lambda source_path: (_ for _ in ()).throw(OSError("mock delete denied")),
    )

    reply = service.cleanup_by_task_ref("cleanup-shortcut", chat_id=1001)

    captured = capsys.readouterr()
    assert "清理下载源资产失败：mock delete denied" in reply
    assert "[cleanup 执行失败]" in captured.out
    assert "task_ref=hash-87" in captured.out
    assert "event_type=cleanup.failed" in captured.out
    assert "task_id=87" in captured.out
    assert "task_hash=hash-87" in captured.out
    assert f"source={source_file}" in captured.out
    assert f"target={target_file}" in captured.out
    assert "原因=mock delete denied" in captured.out


def test_cleanup_by_task_ref_logs_correlation_missing_with_fix_hint(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert CLEANUP_CORRELATION_MISSING_TEXT in reply
    assert "[cleanup 执行受阻]" in captured.out
    assert "event_type=cleanup.correlation_missing" in captured.out
    assert "task_ref=87" in captured.out
    assert "task_id=" not in captured.out
    assert "task_hash=" not in captured.out
    assert f"结论={CLEANUP_CORRELATION_MISSING_TEXT}" in captured.out
    assert "检查 import.succeeded 事件是否已写入 source_path/target_path" in captured.out


def test_cleanup_by_task_ref_logs_target_missing_with_fix_hint(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_file = tmp_path / "library" / "Dune (2021).mkv"
    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert CLEANUP_TARGET_MISSING_TEXT.format(target_path=str(target_file)) in reply
    assert "[cleanup 执行受阻]" in captured.out
    assert "event_type=cleanup.target_missing" in captured.out
    assert "task_id=87" in captured.out
    assert "task_hash=hash-87" in captured.out
    assert f"source={source_file}" in captured.out
    assert f"target={target_file}" in captured.out
    assert "检查库内目标路径是否已被移动或删除" in captured.out


def test_cleanup_by_task_ref_logs_source_missing_with_fix_hint(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.write_bytes(b"demo")

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert f"下载源资产已不存在，无需清理：{source_file}" in reply
    assert "[cleanup 执行受阻]" in captured.out
    assert "event_type=cleanup.source_missing" in captured.out
    assert f"source={source_file}" in captured.out
    assert f"target={target_file}" in captured.out
    assert "下载源资产已经不存在，当前无需 cleanup" in captured.out


def test_inspect_by_task_ref_logs_job_lookup_failure_and_falls_back_to_task_ref(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )

    class FailingJobRepo:
        def get_job_for_chat_ref(self, *, chat_id: int, task_ref: str) -> None:
            raise RuntimeError("mock job lookup denied")

    service = CleanupDownloadedSourceService(event_repo, job_repo=FailingJobRepo())  # type: ignore[arg-type]

    reply = service.inspect_by_task_ref("87", chat_id=1001)

    captured = capsys.readouterr()
    assert "清理预检结果：" in reply
    assert "当前 guardrail: 允许 cleanup" in reply
    assert "[cleanup 任务解析失败]" in captured.out
    assert "mock job lookup denied" in captured.out
    assert "当前会回退到原始 task_ref 继续尝试匹配 import 关联" in captured.out


@pytest.mark.parametrize(
    ("run_cleanup", "expected_fragment", "expected_follow_up", "expect_source_exists"),
    [
        (False, "当前 guardrail: 允许 cleanup", "cleanup hash-87 / 清理 hash-87", True),
        (True, "已清理下载源资产", "cleanup inspect hash-87 / 清理检查 hash-87", False),
    ],
)
def test_cleanup_resolves_chat_scoped_task_ref_via_job_repo(
    tmp_path: Path,
    run_cleanup: bool,
    expected_fragment: str,
    expected_follow_up: str,
    expect_source_exists: bool,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)

    if run_cleanup:
        reply = service.cleanup_by_task_ref("cleanup-shortcut", chat_id=1001)
    else:
        reply = service.inspect_by_task_ref("cleanup-shortcut", chat_id=1001)

    assert expected_fragment in reply
    assert "任务 ID: 87" in reply
    assert "任务 Hash: hash-87" in reply
    assert expected_follow_up in reply
    assert source_file.exists() is expect_source_exists
    assert target_file.exists()


def test_inspect_by_task_ref_keeps_resolved_identity_when_chat_scoped_correlation_missing(tmp_path: Path) -> None:
    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)

    reply = service.inspect_by_task_ref("cleanup-shortcut", chat_id=1001)

    assert "查询引用: cleanup-shortcut" in reply
    assert "任务 ID: 87" in reply
    assert "任务 Hash: hash-87" in reply
    assert "关联: 未找到" in reply
    assert "当前 guardrail: 拒绝 cleanup" in reply
    assert f"结论: {CLEANUP_CORRELATION_MISSING_TEXT}" in reply
    assert "下一步：" not in reply


def test_cleanup_by_task_ref_uses_resolved_identity_when_chat_scoped_correlation_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)

    reply = service.cleanup_by_task_ref("cleanup-shortcut", chat_id=1001)

    captured = capsys.readouterr()
    assert CLEANUP_CORRELATION_MISSING_TEXT in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply
    assert "[cleanup 执行受阻]" in captured.out
    assert "event_type=cleanup.correlation_missing" in captured.out
    assert "task_ref=cleanup-shortcut" in captured.out
    assert "task_id=87" in captured.out
    assert "task_hash=hash-87" in captured.out
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert events[-1].event_type == "cleanup.correlation_missing"
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in events[-1].message


def test_cleanup_by_task_ref_logs_guard_rejected_with_fix_hint(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_dir = tmp_path / "downloads" / "Dune.Part.Two.2024"
    source_dir.mkdir(parents=True)
    target_file = source_dir / "movie.mkv"
    target_file.write_bytes(b"demo")

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_dir),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert CLEANUP_GUARD_REJECTED_TEXT.format(
        source_path=str(source_dir),
        target_path=str(target_file),
    ) in reply
    assert "[cleanup 执行受阻]" in captured.out
    assert "event_type=cleanup.guard_rejected" in captured.out
    assert "task_id=87" in captured.out
    assert "task_hash=hash-87" in captured.out
    assert f"source={source_dir}" in captured.out
    assert f"target={target_file}" in captured.out
    assert "检查 source_path 和 target_path 是否指向同一位置或互为父子目录" in captured.out


def test_inspect_by_task_ref_reports_source_type_unsupported_with_blocked_follow_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)
    monkeypatch.setattr(
        cleanup_module,
        "_validate_cleanup_paths",
        lambda **_: CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT,
    )

    reply = service.inspect_by_task_ref("87")

    assert "当前 guardrail: 拒绝 cleanup" in reply
    assert f"结论: {CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT}" in reply
    assert "下一步：" in reply
    assert "当前先不要执行 cleanup" in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in reply
    assert source_file.exists()
    assert target_file.exists()


def test_cleanup_by_task_ref_records_source_type_unsupported_with_follow_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)
    monkeypatch.setattr(
        cleanup_module,
        "_validate_cleanup_paths",
        lambda **_: CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT,
    )

    reply = service.cleanup_by_task_ref("87")

    assert CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    assert source_file.exists()
    assert target_file.exists()
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert events[-1].event_type == "cleanup.source_type_unsupported"
    assert CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT in events[-1].message


def test_cleanup_by_task_ref_logs_source_type_unsupported_with_fix_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)
    monkeypatch.setattr(
        cleanup_module,
        "_validate_cleanup_paths",
        lambda **_: CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT,
    )

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT in reply
    assert "[cleanup 执行受阻]" in captured.out
    assert "event_type=cleanup.source_type_unsupported" in captured.out
    assert "task_id=87" in captured.out
    assert "task_hash=hash-87" in captured.out
    assert f"source={source_file}" in captured.out
    assert f"target={target_file}" in captured.out
    assert "检查 source_path 是否误指到管道、套接字、失效链接等非常规类型" in captured.out


def test_cleanup_by_task_ref_logs_source_type_unsupported_with_chat_scoped_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)
    monkeypatch.setattr(
        cleanup_module,
        "_validate_cleanup_paths",
        lambda **_: CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT,
    )

    reply = service.cleanup_by_task_ref("cleanup-shortcut", chat_id=1001)

    captured = capsys.readouterr()
    assert CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    assert "[cleanup 执行受阻]" in captured.out
    assert "task_ref=hash-87" in captured.out
    assert "event_type=cleanup.source_type_unsupported" in captured.out
    assert "task_id=87" in captured.out
    assert "task_hash=hash-87" in captured.out
    assert f"source={source_file}" in captured.out
    assert f"target={target_file}" in captured.out
    assert "检查 source_path 是否误指到管道、套接字、失效链接等非常规类型" in captured.out


def test_cleanup_by_task_ref_logs_event_append_failure_without_hiding_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    def _raise_append_error(**_: object) -> None:
        raise RuntimeError("mock append denied")

    monkeypatch.setattr(event_repo, "append_event", _raise_append_error)

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert "已清理下载源资产" in reply
    assert not source_file.exists()
    assert target_file.exists()
    assert "[cleanup 事件写入失败]" in captured.out
    assert "task_ref=87" in captured.out
    assert "event_type=cleanup.succeeded" in captured.out
    assert "task_id=87" in captured.out
    assert "task_hash=hash-87" in captured.out
    assert f"source={source_file}" in captured.out
    assert f"target={target_file}" in captured.out
    assert "mock append denied" in captured.out
    assert "当前 cleanup 文本结果已返回，但这次执行记录未成功落盘" in captured.out


def test_cleanup_by_task_ref_logs_event_append_failure_with_chat_scoped_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)

    def _raise_append_error(**_: object) -> None:
        raise RuntimeError("mock append denied")

    monkeypatch.setattr(event_repo, "append_event", _raise_append_error)

    reply = service.cleanup_by_task_ref("cleanup-shortcut", chat_id=1001)

    captured = capsys.readouterr()
    assert "已清理下载源资产" in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    assert not source_file.exists()
    assert target_file.exists()
    assert "[cleanup 事件写入失败]" in captured.out
    assert "task_ref=hash-87" in captured.out
    assert "event_type=cleanup.succeeded" in captured.out
    assert "task_id=87" in captured.out
    assert "task_hash=hash-87" in captured.out
    assert f"source={source_file}" in captured.out
    assert f"target={target_file}" in captured.out
    assert "mock append denied" in captured.out
    assert "当前 cleanup 文本结果已返回，但这次执行记录未成功落盘" in captured.out


def test_cleanup_by_task_ref_logs_missing_appended_event_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    def _raise_missing_result(**_: object) -> None:
        raise RuntimeError("job_event missing after append")

    monkeypatch.setattr(event_repo, "append_event", _raise_missing_result)

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert "已清理下载源资产" in reply
    assert not source_file.exists()
    assert target_file.exists()
    assert "[cleanup 事件结果缺失]" in captured.out
    assert "task_ref=87" in captured.out
    assert "event_type=cleanup.succeeded" in captured.out
    assert "cleanup event missing after append" in captured.out
    assert "当前 cleanup 文本结果已返回，但这次执行记录真相还没有确认落稳" in captured.out


def test_cleanup_by_task_ref_logs_row_corrupted_appended_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    def _raise_row_corrupted(**_: object) -> None:
        raise JobEventPersistenceError("job_event row identity corrupted after read")

    monkeypatch.setattr(event_repo, "append_event", _raise_row_corrupted)

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert "已清理下载源资产" in reply
    assert not source_file.exists()
    assert target_file.exists()
    assert "[cleanup 事件记录损坏]" in captured.out
    assert "task_ref=87" in captured.out
    assert "event_type=cleanup.succeeded" in captured.out
    assert "job_event row identity corrupted after read" in captured.out
    assert "当前 cleanup 文本结果已返回，但不会把这条坏事件当成已稳定落盘" in captured.out


def test_inspect_by_task_ref_logs_correlation_query_failure_and_returns_missing_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event_repo = JobEventRepo(_make_database(tmp_path))
    service = CleanupDownloadedSourceService(event_repo)

    monkeypatch.setattr(
        event_repo,
        "find_latest_import_correlation",
        lambda **_: (_ for _ in ()).throw(RuntimeError("mock correlation lookup denied")),
    )

    reply = service.inspect_by_task_ref("87")

    captured = capsys.readouterr()
    assert "关联: 未找到" in reply
    assert "当前 guardrail: 拒绝 cleanup" in reply
    assert f"结论: {CLEANUP_CORRELATION_MISSING_TEXT}" in reply
    assert "[cleanup 关联查询失败]" in captured.out
    assert "task_ref=87" in captured.out
    assert "lookup_task_ref=87" in captured.out
    assert "lookup_task_id=87" in captured.out
    assert "lookup_task_hash=87" in captured.out
    assert "mock correlation lookup denied" in captured.out
    assert "检查 SQLite job_event 是否可读、导入成功事件是否已落盘" in captured.out


def test_cleanup_by_task_ref_logs_correlation_query_failure_and_keeps_follow_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event_repo = JobEventRepo(_make_database(tmp_path))
    service = CleanupDownloadedSourceService(event_repo)

    monkeypatch.setattr(
        event_repo,
        "find_latest_import_correlation",
        lambda **_: (_ for _ in ()).throw(RuntimeError("mock correlation lookup denied")),
    )

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert CLEANUP_CORRELATION_MISSING_TEXT in reply
    assert "cleanup inspect 87 / 清理检查 87：只读预检，不删除任何文件" in reply
    assert "cleanup 87 / 清理 87：实际清理下载源资产" in reply
    assert "[cleanup 关联查询失败]" in captured.out
    assert "task_ref=87" in captured.out
    assert "lookup_task_ref=87" in captured.out
    assert "lookup_task_id=87" in captured.out
    assert "lookup_task_hash=87" in captured.out
    assert "mock correlation lookup denied" in captured.out
    assert "检查 SQLite job_event 是否可读、导入成功事件是否已落盘" in captured.out


def test_inspect_by_task_ref_logs_correlation_lookup_result_missing_and_returns_missing_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event_repo = JobEventRepo(_make_database(tmp_path))
    service = CleanupDownloadedSourceService(event_repo)

    monkeypatch.setattr(
        event_repo,
        "find_latest_import_correlation",
        lambda **_: (_ for _ in ()).throw(RuntimeError("job_event list result missing during correlation lookup")),
    )

    reply = service.inspect_by_task_ref("87")

    captured = capsys.readouterr()
    assert "关联: 未找到" in reply
    assert "当前 guardrail: 拒绝 cleanup" in reply
    assert f"结论: {CLEANUP_CORRELATION_MISSING_TEXT}" in reply
    assert "[cleanup 关联结果缺失]" in captured.out
    assert "task_ref=87" in captured.out
    assert "lookup_task_ref=87" in captured.out
    assert "lookup_task_id=87" in captured.out
    assert "lookup_task_hash=87" in captured.out
    assert "job_event list result missing during correlation lookup" in captured.out
    assert "避免把缺失真相误判成普通“没有 import 关联”" in captured.out


def test_cleanup_by_task_ref_logs_correlation_lookup_result_missing_and_keeps_follow_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event_repo = JobEventRepo(_make_database(tmp_path))
    service = CleanupDownloadedSourceService(event_repo)

    monkeypatch.setattr(
        event_repo,
        "find_latest_import_correlation",
        lambda **_: (_ for _ in ()).throw(RuntimeError("job_event list result missing during correlation lookup")),
    )

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert CLEANUP_CORRELATION_MISSING_TEXT in reply
    assert "cleanup inspect 87 / 清理检查 87：只读预检，不删除任何文件" in reply
    assert "cleanup 87 / 清理 87：实际清理下载源资产" in reply
    assert "[cleanup 关联结果缺失]" in captured.out
    assert "task_ref=87" in captured.out
    assert "lookup_task_ref=87" in captured.out
    assert "lookup_task_id=87" in captured.out
    assert "lookup_task_hash=87" in captured.out
    assert "job_event list result missing during correlation lookup" in captured.out
    assert "避免把缺失真相误判成普通“没有 import 关联”" in captured.out


def test_inspect_by_task_ref_logs_correlation_row_corrupted_and_returns_missing_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event_repo = JobEventRepo(_make_database(tmp_path))
    service = CleanupDownloadedSourceService(event_repo)

    monkeypatch.setattr(
        event_repo,
        "find_latest_import_correlation",
        lambda **_: (_ for _ in ()).throw(JobEventPersistenceError("job_event row identity corrupted after read")),
    )

    reply = service.inspect_by_task_ref("87")

    captured = capsys.readouterr()
    assert "关联: 未找到" in reply
    assert "当前 guardrail: 拒绝 cleanup" in reply
    assert f"结论: {CLEANUP_CORRELATION_MISSING_TEXT}" in reply
    assert "[cleanup 关联记录损坏]" in captured.out
    assert "task_ref=87" in captured.out
    assert "lookup_task_ref=87" in captured.out
    assert "lookup_task_id=87" in captured.out
    assert "lookup_task_hash=87" in captured.out
    assert "job_event row identity corrupted after read" in captured.out
    assert "避免把坏记录误判成普通“没有 import 关联”" in captured.out


def test_cleanup_by_task_ref_logs_correlation_row_corrupted_and_keeps_follow_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event_repo = JobEventRepo(_make_database(tmp_path))
    service = CleanupDownloadedSourceService(event_repo)

    monkeypatch.setattr(
        event_repo,
        "find_latest_import_correlation",
        lambda **_: (_ for _ in ()).throw(JobEventPersistenceError("job_event row identity corrupted after read")),
    )

    reply = service.cleanup_by_task_ref("87")

    captured = capsys.readouterr()
    assert CLEANUP_CORRELATION_MISSING_TEXT in reply
    assert "cleanup inspect 87 / 清理检查 87：只读预检，不删除任何文件" in reply
    assert "cleanup 87 / 清理 87：实际清理下载源资产" in reply
    assert "[cleanup 关联记录损坏]" in captured.out
    assert "task_ref=87" in captured.out
    assert "lookup_task_ref=87" in captured.out
    assert "lookup_task_id=87" in captured.out
    assert "lookup_task_hash=87" in captured.out
    assert "job_event row identity corrupted after read" in captured.out
    assert "避免把坏记录误判成普通“没有 import 关联”" in captured.out


def test_inspect_by_task_ref_logs_correlation_query_failure_with_chat_scoped_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)

    monkeypatch.setattr(
        event_repo,
        "find_latest_import_correlation",
        lambda **_: (_ for _ in ()).throw(RuntimeError("mock correlation lookup denied")),
    )

    reply = service.inspect_by_task_ref("cleanup-shortcut", chat_id=1001)

    captured = capsys.readouterr()
    assert "查询引用: cleanup-shortcut" in reply
    assert "任务 ID: 87" in reply
    assert "任务 Hash: hash-87" in reply
    assert "关联: 未找到" in reply
    assert "当前 guardrail: 拒绝 cleanup" in reply
    assert "[cleanup 关联查询失败]" in captured.out
    assert "task_ref=cleanup-shortcut" in captured.out
    assert "lookup_task_ref=cleanup-shortcut" in captured.out
    assert "lookup_task_id=87" in captured.out
    assert "lookup_task_hash=hash-87" in captured.out


def test_cleanup_by_task_ref_logs_correlation_query_failure_with_chat_scoped_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)

    monkeypatch.setattr(
        event_repo,
        "find_latest_import_correlation",
        lambda **_: (_ for _ in ()).throw(RuntimeError("mock correlation lookup denied")),
    )

    reply = service.cleanup_by_task_ref("cleanup-shortcut", chat_id=1001)

    captured = capsys.readouterr()
    assert CLEANUP_CORRELATION_MISSING_TEXT in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply
    assert "[cleanup 关联查询失败]" in captured.out
    assert "task_ref=cleanup-shortcut" in captured.out
    assert "lookup_task_ref=cleanup-shortcut" in captured.out
    assert "lookup_task_id=87" in captured.out
    assert "lookup_task_hash=hash-87" in captured.out
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert events[-1].event_type == "cleanup.correlation_missing"
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in events[-1].message


def test_inspect_by_task_ref_keeps_chat_scoped_identity_when_import_event_lacks_structured_paths(
    tmp_path: Path,
) -> None:
    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.write_bytes(b"demo")

    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)

    reply = service.inspect_by_task_ref("cleanup-shortcut", chat_id=1001)

    assert "查询引用: cleanup-shortcut" in reply
    assert "任务 ID: 87" in reply
    assert "任务 Hash: hash-87" in reply
    assert "关联: 未找到" in reply
    assert "源路径状态: 未找到关联" in reply
    assert "目标路径状态: 未找到关联" in reply
    assert f"结论: {CLEANUP_CORRELATION_MISSING_TEXT}" in reply
    assert "下一步：" not in reply


def test_cleanup_by_task_ref_keeps_chat_scoped_identity_when_import_event_lacks_structured_paths(
    tmp_path: Path,
) -> None:
    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.write_bytes(b"demo")

    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="cleanup-shortcut",
        task_id="87",
        task_hash="hash-87",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)

    reply = service.cleanup_by_task_ref("cleanup-shortcut", chat_id=1001)

    assert CLEANUP_CORRELATION_MISSING_TEXT in reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert events[-1].event_type == "cleanup.correlation_missing"
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in events[-1].message


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database
