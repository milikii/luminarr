from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import errno
from pathlib import Path
from unittest.mock import AsyncMock

import app.services.import_to_library as import_module
from app.clients.transmission import TransmissionImportSource, TransmissionTask
from app.db.approval_repo import (
    ACTION_ADD_TO_DOWNLOADER,
    ACTION_IMPORT_TO_LIBRARY,
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_CANCELLED,
    APPROVAL_STATUS_PENDING,
    ApprovalRepo,
)
from app.db.candidate_repo import CandidateMappingRepo
from app.db.clarification_repo import ClarificationRepo
from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JOB_STATE_COMPLETED, JOB_STATE_PENDING_APPROVAL, JobRepo, WORKFLOW_ADD_TO_DOWNLOADER
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.services.add_to_downloader import (
    ADD_CANCELLED_TEXT,
    ADD_CONFIRM_NOT_PENDING_TEXT,
    AddToDownloaderService,
)
from app.services.import_to_library import (
    IMPORT_COPY_APPROVAL_PENDING_TEXT,
    IMPORT_CANCELLED_TEXT,
    IMPORT_CONFIRM_NOT_PENDING_TEXT,
    IMPORT_TARGET_EXISTS_TEXT,
    ImportToLibraryService,
)
from app.services.search_media import SearchMediaService


def test_candidate_mapping_persists_for_restart(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    candidate_repo = CandidateMappingRepo(database)

    search_service_before_restart = SearchMediaService(
        search_func=_fake_search_with_download_url,
        candidate_repo=candidate_repo,
    )
    _run(search_service_before_restart.search_and_format("dune", chat_id=1001))

    search_service_after_restart = SearchMediaService(
        search_func=_unexpected_search_call,
        candidate_repo=CandidateMappingRepo(SqliteDatabase(str(tmp_path / "state.sqlite3"))),
    )
    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42"))
    add_service = AddToDownloaderService(search_service=search_service_after_restart, add_torrent_func=add_torrent)

    pending_reply = _run(add_service.add_by_selection(1001, "1"))
    assert "下载待确认" in pending_reply

    confirm_reply = _run(add_service.confirm_add_by_task_ref("1", chat_id=1001))
    assert "任务 ID: 42" in confirm_reply
    assert "任务 Hash: hash-42" in confirm_reply
    add_torrent.assert_awaited_once_with("https://example.com/dune.torrent")


def test_job_event_repo_keeps_append_order(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = JobEventRepo(database)

    repo.append_event(task_ref="87", event_type="import.succeeded", message="/data/library/movies/demo.mkv")
    repo.append_event(task_ref="87", event_type="refresh.succeeded", message="媒体库刷新成功。")

    events = repo.list_events_for_task_ref("87")
    assert [event.event_type for event in events] == ["import.succeeded", "refresh.succeeded"]
    assert events[0].message.endswith("demo.mkv")
    assert events[1].message == "媒体库刷新成功。"


def test_telegram_update_repo_rejects_duplicate_message_after_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_repo = TelegramUpdateRepo(database)
    assert before_restart_repo.record_message_update(update_id=1001, chat_id=2001, user_id=3001) is True

    after_restart_repo = TelegramUpdateRepo(SqliteDatabase(str(db_path)))
    assert after_restart_repo.record_message_update(update_id=1001, chat_id=2001, user_id=3001) is False


def test_clarification_repo_persists_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_repo = ClarificationRepo(database)
    before_restart_repo.upsert_pending(chat_id=1001, query="Dune")

    after_restart_repo = ClarificationRepo(SqliteDatabase(str(db_path)))
    assert after_restart_repo.get_pending_query(chat_id=1001) == "Dune"
    assert after_restart_repo.clear_pending(chat_id=1001) is True

    verify_repo = ClarificationRepo(SqliteDatabase(str(db_path)))
    assert verify_repo.get_pending_query(chat_id=1001) is None


def test_job_repo_persists_version_and_lease_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    repo = JobRepo(database)

    first_job = repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
    )
    second_job = repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
    )

    assert first_job is not None
    assert second_job is not None
    assert first_job.version == 1
    assert second_job.version == 2
    assert repo.claim_lease(
        job_id=second_job.job_id,
        expected_version=second_job.version,
        lease_owner="test-owner",
        workflow_type=second_job.workflow_type,
    )

    restarted_repo = JobRepo(SqliteDatabase(str(db_path)))
    restarted_job = restarted_repo.get_import_job_for_chat_ref(chat_id=1001, task_ref="87")

    assert restarted_job is not None
    assert restarted_job.version == 2
    assert restarted_job.lease_owner == "test-owner"
    assert restarted_job.lease_until


def test_import_persists_minimal_events(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        refresh_media_server_func=AsyncMock(return_value="媒体库刷新成功。"),
        job_event_repo=event_repo,
        approval_repo=ApprovalRepo(database),
    )

    pending_reply = _run(service.import_by_task_ref("87"))
    assert "导入待确认" in pending_reply
    confirm_reply = _run(service.confirm_import_by_task_ref("87"))
    assert "导入成功" in confirm_reply

    events = event_repo.list_events_for_task_ref("87")
    assert [event.event_type for event in events] == [
        "import.approval_pending",
        "import.approval_confirmed",
        "import.succeeded",
        "refresh.succeeded",
    ]
    assert events[2].task_id == "87"
    assert events[2].task_hash == "hash-87"


def test_import_not_completed_persists_event(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name="Dune.2021.mkv",
        download_dir=str(tmp_path / "downloads"),
        is_finished=False,
        percent_done=0.2,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
        job_event_repo=event_repo,
    )

    reply = _run(service.import_by_task_ref("87"))
    assert "任务尚未完成" in reply

    events = event_repo.list_events_for_task_ref("87")
    assert len(events) == 1
    assert events[0].event_type == "import.not_completed"


def test_approval_repo_persists_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_repo = ApprovalRepo(database)
    before_restart_repo.upsert_import_approval(task_id="87", task_hash="hash-87", task_ref="87")

    after_restart_repo = ApprovalRepo(SqliteDatabase(str(db_path)))
    record = after_restart_repo.get_import_approval(task_id="87", task_hash="hash-87")

    assert record is not None
    assert record.action_type == ACTION_IMPORT_TO_LIBRARY
    assert record.status == APPROVAL_STATUS_APPROVED
    assert record.lease_version == 1
    assert record.executed_version == 1
    assert record.last_task_ref == "87"


def test_pending_approval_persists_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_repo = ApprovalRepo(database)
    before_restart_repo.request_import_approval(task_id="87", task_hash="hash-87", task_ref="87")

    after_restart_repo = ApprovalRepo(SqliteDatabase(str(db_path)))
    record = after_restart_repo.get_import_approval(task_id="87", task_hash="hash-87")

    assert record is not None
    assert record.action_type == ACTION_IMPORT_TO_LIBRARY
    assert record.status == APPROVAL_STATUS_PENDING
    assert record.lease_version == 1
    assert record.executed_version == 0
    assert record.last_task_ref == "87"


def test_pending_approval_persists_expiry_truth(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    repo = ApprovalRepo(database)

    lease_version = repo.request_import_approval(
        task_id="87",
        task_hash="hash-87",
        task_ref="87",
        timeout_seconds=-1,
    )
    assert lease_version == 1

    record = repo.get_import_approval(task_id="87", task_hash="hash-87")
    assert record is not None
    assert record.expires_at
    assert repo.is_import_pending_expired(
        task_id="87",
        task_hash="hash-87",
        expected_lease_version=lease_version,
    )


def test_downloader_pending_approval_persists_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    search_before_restart = SearchMediaService(
        search_func=_fake_search_with_download_url,
        candidate_repo=CandidateMappingRepo(database),
    )
    _run(search_before_restart.search_and_format("dune", chat_id=1001))

    before_restart_service = AddToDownloaderService(
        search_service=search_before_restart,
        add_torrent_func=AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42")),
        approval_repo=ApprovalRepo(database),
        job_repo=JobRepo(database),
    )
    pending_reply = _run(before_restart_service.add_by_selection(1001, "1", user_id=2001))
    assert "下载待确认" in pending_reply

    after_restart_service = AddToDownloaderService(
        search_service=SearchMediaService(_unexpected_search_call),
        add_torrent_func=AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42")),
        approval_repo=ApprovalRepo(SqliteDatabase(str(db_path))),
        job_repo=JobRepo(SqliteDatabase(str(db_path))),
    )
    confirm_reply = _run(after_restart_service.confirm_add_by_task_ref("1", chat_id=1001, user_id=2001))

    assert "任务 ID: 42" in confirm_reply
    assert "任务 Hash: hash-42" in confirm_reply

    restarted_job = JobRepo(SqliteDatabase(str(db_path))).get_downloader_job_for_chat_ref(
        chat_id=1001,
        task_ref="1",
    )
    assert restarted_job is not None
    assert restarted_job.workflow_type == WORKFLOW_ADD_TO_DOWNLOADER
    assert restarted_job.state == JOB_STATE_COMPLETED
    assert restarted_job.payload_json

    approval_record = ApprovalRepo(SqliteDatabase(str(db_path))).get_downloader_approval(
        task_id="selection:1",
        task_hash=restarted_job.task_hash,
    )
    assert approval_record is not None
    assert approval_record.action_type == ACTION_ADD_TO_DOWNLOADER
    assert approval_record.status == APPROVAL_STATUS_APPROVED
    assert approval_record.executed_version == approval_record.lease_version


def test_downloader_confirm_stale_guard_blocks_duplicate_after_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    search_service = SearchMediaService(
        search_func=_fake_search_with_download_url,
        candidate_repo=CandidateMappingRepo(database),
    )
    _run(search_service.search_and_format("dune", chat_id=1001))

    first_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42")),
        approval_repo=ApprovalRepo(database),
        job_repo=JobRepo(database),
    )
    _run(first_service.add_by_selection(1001, "1", user_id=2001))
    first_confirm = _run(first_service.confirm_add_by_task_ref("1", chat_id=1001, user_id=2001))
    assert "任务 ID: 42" in first_confirm

    restarted_service = AddToDownloaderService(
        search_service=SearchMediaService(_unexpected_search_call),
        add_torrent_func=AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42")),
        approval_repo=ApprovalRepo(SqliteDatabase(str(db_path))),
        job_repo=JobRepo(SqliteDatabase(str(db_path))),
    )
    stale_reply = _run(restarted_service.confirm_add_by_task_ref("1", chat_id=1001, user_id=2001))

    assert stale_reply == ADD_CONFIRM_NOT_PENDING_TEXT


def test_cancel_pending_downloader_updates_persisted_truth(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    search_service = SearchMediaService(
        search_func=_fake_search_with_download_url,
        candidate_repo=CandidateMappingRepo(database),
    )
    _run(search_service.search_and_format("dune", chat_id=1001))

    approval_repo = ApprovalRepo(database)
    job_repo = JobRepo(database)
    service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42")),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )

    pending_reply = _run(service.add_by_selection(1001, "1", user_id=2001))
    assert "下载待确认" in pending_reply

    pending_job = job_repo.get_downloader_job_for_chat_ref(chat_id=1001, task_ref="1")
    assert pending_job is not None

    cancelled_reply = service.cancel_pending_add(1001)
    assert cancelled_reply == ADD_CANCELLED_TEXT

    record = approval_repo.get_downloader_approval(
        task_id=pending_job.task_id,
        task_hash=pending_job.task_hash,
    )
    assert record is not None
    assert record.status == APPROVAL_STATUS_CANCELLED

    confirm_reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001, user_id=2001))
    assert confirm_reply == ADD_CONFIRM_NOT_PENDING_TEXT


def test_import_request_advances_lease_version(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    approval_repo = ApprovalRepo(database)

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
        approval_repo=approval_repo,
    )

    first_reply = _run(service.import_by_task_ref("87"))
    second_reply = _run(service.import_by_task_ref("87"))

    assert "导入待确认" in first_reply
    assert "导入待确认" in second_reply
    record = approval_repo.get_import_approval(task_id="87", task_hash="hash-87")
    assert record is not None
    assert record.status == APPROVAL_STATUS_PENDING
    assert record.lease_version == 2
    assert record.executed_version == 0


def test_confirm_marks_executed_version(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    approval_repo = ApprovalRepo(database)

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
        approval_repo=approval_repo,
    )

    _run(service.import_by_task_ref("87"))
    confirm_reply = _run(service.confirm_import_by_task_ref("87"))

    assert "导入成功" in confirm_reply
    record = approval_repo.get_import_approval(task_id="87", task_hash="hash-87")
    assert record is not None
    assert record.status == APPROVAL_STATUS_APPROVED
    assert record.lease_version == 1
    assert record.executed_version == 1


def test_approve_import_requires_current_lease_version(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ApprovalRepo(database)

    first_lease = repo.request_import_approval(task_id="87", task_hash="hash-87", task_ref="87")
    second_lease = repo.request_import_approval(task_id="87", task_hash="hash-87", task_ref="87")

    assert first_lease == 1
    assert second_lease == 2
    assert (
        repo.approve_import(
            task_id="87",
            task_hash="hash-87",
            task_ref="87",
            expected_lease_version=first_lease,
        )
        is False
    )
    assert (
        repo.approve_import(
            task_id="87",
            task_hash="hash-87",
            task_ref="87",
            expected_lease_version=second_lease,
        )
        is True
    )


def test_import_stale_guard_blocks_duplicate_after_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    event_repo = JobEventRepo(database)
    approval_repo = ApprovalRepo(database)

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    first_service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        job_event_repo=event_repo,
        approval_repo=approval_repo,
    )
    first_pending = _run(first_service.import_by_task_ref("87"))
    assert "导入待确认" in first_pending
    first_confirm = _run(first_service.confirm_import_by_task_ref("87"))
    assert "导入成功" in first_confirm

    imported_target = target_dir / source_file.name
    assert imported_target.exists()
    imported_target.unlink()
    assert not imported_target.exists()

    restarted_service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        job_event_repo=JobEventRepo(SqliteDatabase(str(db_path))),
        approval_repo=ApprovalRepo(SqliteDatabase(str(db_path))),
    )
    stale_reply = _run(restarted_service.confirm_import_by_task_ref("hash-87"))

    assert stale_reply == IMPORT_TARGET_EXISTS_TEXT.format(target_path=str(imported_target))
    assert not imported_target.exists()


def test_confirm_rebuilds_context_from_persisted_job_after_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    job_repo = JobRepo(database)

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )

    before_restart_service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    pending_reply = _run(before_restart_service.import_by_task_ref("87", chat_id=1001, user_id=2001))
    assert "导入待确认" in pending_reply

    async def _lookup_by_hash_only(task_ref: str) -> TransmissionImportSource | None:
        assert task_ref == "hash-87"
        return import_source

    after_restart_service = ImportToLibraryService(
        get_import_source_func=AsyncMock(side_effect=_lookup_by_hash_only),
        library_target_dir=str(target_dir),
        approval_repo=ApprovalRepo(SqliteDatabase(str(db_path))),
        job_repo=JobRepo(SqliteDatabase(str(db_path))),
    )

    confirm_reply = _run(
        after_restart_service.confirm_import_by_task_ref("87", chat_id=1001, user_id=2001)
    )

    assert "导入成功" in confirm_reply
    restarted_job = JobRepo(SqliteDatabase(str(db_path))).get_import_job_for_chat_ref(
        chat_id=1001,
        task_ref="87",
    )
    assert restarted_job is not None
    assert restarted_job.state == JOB_STATE_COMPLETED


def test_copy_fallback_pending_survives_restart_and_second_confirm_copies(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    job_repo = JobRepo(database)

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )

    before_restart_service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    pending_reply = _run(before_restart_service.import_by_task_ref("87", chat_id=1001, user_id=2001))
    assert "导入待确认" in pending_reply

    def _raise_exdev(src: str | Path, dst: str | Path) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(import_module.os, "link", _raise_exdev)
    first_confirm = _run(
        before_restart_service.confirm_import_by_task_ref("87", chat_id=1001, user_id=2001)
    )
    assert first_confirm == IMPORT_COPY_APPROVAL_PENDING_TEXT.format(task_ref="87")

    restarted_job = JobRepo(SqliteDatabase(str(db_path))).get_import_job_for_chat_ref(
        chat_id=1001,
        task_ref="87",
    )
    assert restarted_job is not None
    assert restarted_job.state == JOB_STATE_PENDING_APPROVAL
    assert '"mode": "copy"' in restarted_job.payload_json

    def _unexpected_hardlink(src: str | Path, dst: str | Path) -> None:
        raise AssertionError("copy confirm after restart should not call os.link")

    monkeypatch.setattr(import_module.os, "link", _unexpected_hardlink)
    after_restart_service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        approval_repo=ApprovalRepo(SqliteDatabase(str(db_path))),
        job_repo=JobRepo(SqliteDatabase(str(db_path))),
    )
    second_confirm = _run(
        after_restart_service.confirm_import_by_task_ref("87", chat_id=1001, user_id=2001)
    )

    target_file = target_dir / source_file.name
    assert "导入成功" in second_confirm
    assert "导入方式: 复制" in second_confirm
    assert target_file.exists()
    assert source_file.stat().st_ino != target_file.stat().st_ino


def test_cancel_pending_import_updates_persisted_truth(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    job_repo = JobRepo(database)

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )

    pending_reply = _run(service.import_by_task_ref("87", chat_id=1001, user_id=2001))
    assert "导入待确认" in pending_reply

    cancelled_reply = service.cancel_pending_import(1001)
    assert cancelled_reply == IMPORT_CANCELLED_TEXT

    record = approval_repo.get_import_approval(task_id="87", task_hash="hash-87")
    assert record is not None
    assert record.status == APPROVAL_STATUS_CANCELLED

    confirm_reply = _run(service.confirm_import_by_task_ref("87", chat_id=1001, user_id=2001))
    assert confirm_reply == IMPORT_CONFIRM_NOT_PENDING_TEXT


def test_job_event_repo_can_query_by_task_identity(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = JobEventRepo(database)

    repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message="/data/library/movies/Dune.2021.mkv",
    )
    repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="refresh.succeeded",
        message="媒体库刷新成功。",
    )

    events = repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert [event.event_type for event in events] == ["import.succeeded", "refresh.succeeded"]


async def _fake_search_with_download_url(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [
        {
            "title": "Dune: Part Two",
            "downloadUrl": "https://example.com/dune.torrent",
        }
    ]


async def _unexpected_search_call(_: str) -> list[dict[str, object]]:
    raise AssertionError("unexpected search call")


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)
