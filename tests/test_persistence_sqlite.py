from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import errno
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import app.services.import_to_library as import_module
from app.clients.transmission import TransmissionImportSource, TransmissionTask, TransmissionTaskStatus
from app.db.approval_repo import (
    ACTION_ADD_TO_DOWNLOADER,
    ACTION_IMPORT_TO_LIBRARY,
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_CANCELLED,
    APPROVAL_STATUS_PENDING,
    ApprovalPersistenceError,
    ApprovalRepo,
)
from app.db.bt_subscription_repo import BtSubscriptionPersistenceError, BtSubscriptionRepo
from app.db.bt_pending_repo import (
    BT_PENDING_STAGE_RAW_BT_DESTINATION,
    BT_PENDING_STAGE_TMDB_ASSOCIATION,
    BtPendingPersistenceError,
    BtPendingRepo,
)
from app.db.candidate_repo import CandidateMappingRepo, CandidatePersistenceError
from app.db.clarification_repo import ClarificationPersistenceError, ClarificationRepo
from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRepo
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.db.job_repo import (
    JOB_STATE_COMPLETED,
    JOB_STATE_PENDING_APPROVAL,
    JobPersistenceError,
    JobRepo,
    WORKFLOW_ADD_TO_DOWNLOADER,
)
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdatePersistenceError, TelegramUpdateRepo
from app.db.watchlist_repo import WatchlistPersistenceError, WatchlistRepo
from app.services.add_to_downloader import (
    ADD_CANCELLED_TEXT,
    ADD_CONFIRM_NOT_PENDING_TEXT,
    AddToDownloaderService,
)
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import (
    IMPORT_COPY_APPROVAL_PENDING_TEXT,
    IMPORT_CANCELLED_TEXT,
    IMPORT_CONFIRM_NOT_PENDING_TEXT,
    IMPORT_TARGET_EXISTS_TEXT,
    ImportToLibraryService,
)
from app.services.post_download_auto_import import PostDownloadAutoImportService
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


def test_candidate_mapping_repo_raises_when_saved_count_mismatches(tmp_path: Path) -> None:
    class MissingCandidateRowRepo(CandidateMappingRepo):
        def _count_candidates(self, *, chat_id: int) -> int:
            _ = chat_id
            return 0

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = MissingCandidateRowRepo(database)

    with pytest.raises(CandidatePersistenceError, match="candidate_mapping count mismatch after save"):
        repo.save_candidates(1001, [{"title": "Dune"}])


def test_candidate_mapping_repo_rejects_missing_chat_identity(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = CandidateMappingRepo(database)

    with pytest.raises(CandidatePersistenceError, match="candidate_mapping chat identity missing"):
        repo.save_candidates(0, [{"title": "Dune"}])


def test_candidate_mapping_repo_rejects_missing_chat_identity_for_query(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = CandidateMappingRepo(database)

    with pytest.raises(CandidatePersistenceError, match="candidate_mapping chat identity missing for query"):
        repo.get_candidate(0, 1)


def test_candidate_mapping_repo_rejects_invalid_selection_index(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = CandidateMappingRepo(database)

    with pytest.raises(CandidatePersistenceError, match="candidate selection index invalid"):
        repo.get_candidate(1001, 0)


def test_candidate_mapping_repo_rejects_missing_chat_identity_for_clear(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = CandidateMappingRepo(database)

    with pytest.raises(CandidatePersistenceError, match="candidate_mapping chat identity missing for clear"):
        repo.clear_candidates(0)


def test_job_event_repo_keeps_append_order(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = JobEventRepo(database)

    repo.append_event(task_ref="87", event_type="import.succeeded", message="/data/library/movies/demo.mkv")
    repo.append_event(task_ref="87", event_type="refresh.succeeded", message="媒体库刷新成功。")

    events = repo.list_events_for_task_ref("87")
    assert [event.event_type for event in events] == ["import.succeeded", "refresh.succeeded"]
    assert events[0].message.endswith("demo.mkv")
    assert events[0].source_path == ""
    assert events[0].target_path == ""
    assert events[1].message == "媒体库刷新成功。"


def test_job_event_repo_raises_when_appended_row_missing(tmp_path: Path) -> None:
    class MissingRowJobEventRepo(JobEventRepo):
        def _get_event_by_id(self, event_id: int):
            _ = event_id
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = MissingRowJobEventRepo(database)

    with pytest.raises(JobEventPersistenceError, match="job_event missing after append"):
        repo.append_event(task_ref="87", event_type="import.succeeded", message="/data/library/movies/demo.mkv")


def test_job_event_repo_rejects_missing_task_ref(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = JobEventRepo(database)

    with pytest.raises(JobEventPersistenceError, match="job_event task_ref missing"):
        repo.append_event(task_ref="   ", event_type="import.succeeded")


def test_job_event_repo_rejects_missing_event_type(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = JobEventRepo(database)

    with pytest.raises(JobEventPersistenceError, match="job_event event_type missing"):
        repo.append_event(task_ref="87", event_type="   ")


def test_job_event_repo_rejects_missing_identity_for_query(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = JobEventRepo(database)

    with pytest.raises(JobEventPersistenceError, match="job_event task_ref missing for query"):
        repo.list_events_for_task_ref("   ")

    with pytest.raises(JobEventPersistenceError, match="job_event task identity missing for query"):
        repo.list_events_for_task_identity(task_id="   ", task_hash="   ")


def test_download_monitor_truth_persists_for_restart_and_completion_observation(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_repo = DownloadMonitorRepo(database)
    before_restart_repo.register_download(task_id="42", task_hash="hash-42", name="Dune: Part Two")

    after_restart_repo = DownloadMonitorRepo(SqliteDatabase(str(db_path)))
    pending_records = after_restart_repo.list_pending_completion()
    assert len(pending_records) == 1
    assert pending_records[0].task_id == "42"
    assert pending_records[0].is_complete is False

    status_service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="42",
                task_hash="hash-42",
                name="Dune: Part Two",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=after_restart_repo,
        job_event_repo=JobEventRepo(SqliteDatabase(str(db_path))),
    )
    status_reply = _run(status_service.get_status_text("42"))
    assert "状态: 做种中" in status_reply

    final_repo = DownloadMonitorRepo(SqliteDatabase(str(db_path)))
    final_record = final_repo.get_record(task_id="42", task_hash="hash-42")
    assert final_record is not None
    assert final_record.is_complete is True
    assert final_record.completion_observed_at
    assert final_repo.list_pending_completion() == []

    events = JobEventRepo(SqliteDatabase(str(db_path))).list_events_for_task_identity(
        task_id="42",
        task_hash="hash-42",
    )
    assert [event.event_type for event in events] == ["downloader.completed_observed"]


def test_download_monitor_repo_rejects_missing_task_identity(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = DownloadMonitorRepo(database)

    with pytest.raises(DownloadMonitorPersistenceError, match="download monitor task identity missing"):
        repo.register_download(task_id="", task_hash="hash-42", name="Dune: Part Two")

    with pytest.raises(DownloadMonitorPersistenceError, match="download monitor task identity missing"):
        repo.register_download(task_id="42", task_hash="", name="Dune: Part Two")


def test_download_monitor_repo_rejects_missing_identity_for_status_record(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = DownloadMonitorRepo(database)

    with pytest.raises(DownloadMonitorPersistenceError, match="download monitor task identity missing"):
        repo.record_status(
            TransmissionTaskStatus(
                task_id="",
                task_hash="hash-42",
                name="Dune: Part Two",
                status_code=4,
                percent_done=0.5,
                rate_download=1024,
                eta_seconds=60,
            )
        )


def test_download_monitor_repo_rejects_missing_identity_for_query(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = DownloadMonitorRepo(database)

    with pytest.raises(DownloadMonitorPersistenceError, match="download monitor task identity missing for query"):
        repo.get_record(task_id="", task_hash="hash-42")

    with pytest.raises(DownloadMonitorPersistenceError, match="download monitor task identity missing for query"):
        repo.get_record(task_id="42", task_hash="")


def test_download_monitor_repo_raises_when_status_row_missing_after_upsert(tmp_path: Path) -> None:
    class MissingRowDownloadMonitorRepo(DownloadMonitorRepo):
        def _get_record_by_identity(self, *, task_id: str, task_hash: str):
            _ = (task_id, task_hash)
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = MissingRowDownloadMonitorRepo(database)

    with pytest.raises(DownloadMonitorPersistenceError, match="download monitor state missing after status upsert"):
        repo.record_status(
            TransmissionTaskStatus(
                task_id="42",
                task_hash="hash-42",
                name="Dune: Part Two",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        )


def test_download_monitor_pending_completion_limit_is_stable(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = DownloadMonitorRepo(database)
    repo.register_download(task_id="41", task_hash="hash-41", name="first")
    repo.register_download(task_id="42", task_hash="hash-42", name="second")
    assert [record.task_id for record in repo.list_pending_completion(limit=1)] == ["41"]


def test_completed_download_truth_after_restart_can_progress_to_import_pending(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    before_restart_monitor = DownloadMonitorRepo(database)
    before_restart_monitor.register_download(
        task_id="42",
        task_hash="hash-42",
        name=source_file.name,
        chat_id=1001,
        user_id=2001,
    )
    before_restart_monitor.record_status(
        TransmissionTaskStatus(
            task_id="42",
            task_hash="hash-42",
            name=source_file.name,
            status_code=6,
            percent_done=1.0,
            rate_download=0,
            eta_seconds=-1,
        )
    )

    import_source = TransmissionImportSource(
        task_id="42",
        task_hash="hash-42",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    after_restart_database = SqliteDatabase(str(db_path))
    import_service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
        approval_repo=ApprovalRepo(after_restart_database),
        job_repo=JobRepo(after_restart_database),
    )
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=DownloadMonitorRepo(after_restart_database),
        job_event_repo=JobEventRepo(after_restart_database),
        auto_import_func=lambda task_ref, chat_id, user_id: import_service.import_by_task_ref(
            task_ref,
            chat_id=chat_id,
            user_id=user_id,
        ),
    )
    status_service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="42",
                task_hash="hash-42",
                name=source_file.name,
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=DownloadMonitorRepo(after_restart_database),
        job_event_repo=JobEventRepo(after_restart_database),
        post_download_auto_import_service=auto_import_service,
    )

    status_reply = _run(status_service.get_status_text("42"))

    assert "状态: 做种中" in status_reply
    assert "导入待确认" in status_reply
    pending_job = JobRepo(SqliteDatabase(str(db_path))).get_import_job_for_chat_ref(chat_id=1001, task_ref="hash-42")
    assert pending_job is not None
    assert pending_job.state == JOB_STATE_PENDING_APPROVAL


def test_telegram_update_repo_rejects_duplicate_message_after_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_repo = TelegramUpdateRepo(database)
    assert before_restart_repo.record_message_update(update_id=1001, chat_id=2001, user_id=3001) is True

    after_restart_repo = TelegramUpdateRepo(SqliteDatabase(str(db_path)))
    assert after_restart_repo.record_message_update(update_id=1001, chat_id=2001, user_id=3001) is False


def test_telegram_update_repo_rejects_invalid_update_identity(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = TelegramUpdateRepo(database)

    with pytest.raises(TelegramUpdatePersistenceError, match="message update_id missing or invalid"):
        repo.record_message_update(update_id=0, chat_id=2001, user_id=3001)

    with pytest.raises(TelegramUpdatePersistenceError, match="callback_query_id missing"):
        repo.record_callback_update(callback_query_id="", chat_id=2001, user_id=3001)


def test_telegram_update_repo_rejects_non_positive_explicit_chat_or_user_identity(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = TelegramUpdateRepo(database)

    with pytest.raises(TelegramUpdatePersistenceError, match="telegram update chat identity missing"):
        repo.record_message_update(update_id=1001, chat_id=0, user_id=3001)

    with pytest.raises(TelegramUpdatePersistenceError, match="telegram update user identity missing"):
        repo.record_callback_update(callback_query_id="cb-1", chat_id=2001, user_id=0)


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


def test_clarification_repo_raises_when_upsert_row_missing(tmp_path: Path) -> None:
    class MissingRowClarificationRepo(ClarificationRepo):
        def get_pending_query(self, *, chat_id: int) -> str | None:
            _ = chat_id
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = MissingRowClarificationRepo(database)

    with pytest.raises(ClarificationPersistenceError, match="clarification_state missing after upsert"):
        repo.upsert_pending(chat_id=1001, query="Dune")


def test_clarification_repo_rejects_empty_query_after_read(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO clarification_state (chat_id, query, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (1001, "   "),
        )
        connection.commit()

    repo = ClarificationRepo(SqliteDatabase(str(tmp_path / "state.sqlite3")))

    with pytest.raises(ClarificationPersistenceError, match="clarification_state query empty after read"):
        repo.get_pending_query(chat_id=1001)


def test_clarification_repo_rejects_missing_query(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ClarificationRepo(database)

    with pytest.raises(ClarificationPersistenceError, match="clarification_state query missing"):
        repo.upsert_pending(chat_id=1001, query="   ")


def test_clarification_repo_rejects_missing_chat_identity_for_upsert(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ClarificationRepo(database)

    with pytest.raises(ClarificationPersistenceError, match="clarification_state chat identity missing"):
        repo.upsert_pending(chat_id=0, query="Dune")


def test_clarification_repo_rejects_missing_chat_identity_for_query(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ClarificationRepo(database)

    with pytest.raises(ClarificationPersistenceError, match="clarification_state chat identity missing for query"):
        repo.get_pending_query(chat_id=0)


def test_clarification_repo_rejects_missing_chat_identity_for_clear(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ClarificationRepo(database)

    with pytest.raises(ClarificationPersistenceError, match="clarification_state chat identity missing for clear"):
        repo.clear_pending(chat_id=0)


def test_bt_pending_repo_persists_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_repo = BtPendingRepo(database)
    before_restart_repo.upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
        payload_json='{"media_kind":"movie"}',
    )

    after_restart_repo = BtPendingRepo(SqliteDatabase(str(db_path)))
    pending = after_restart_repo.get_pending(chat_id=1001)
    assert pending is not None
    assert pending.stage == BT_PENDING_STAGE_TMDB_ASSOCIATION
    assert pending.payload_json == '{"media_kind":"movie"}'
    assert after_restart_repo.clear_pending(chat_id=1001, expected_stage=BT_PENDING_STAGE_RAW_BT_DESTINATION) is False
    assert after_restart_repo.clear_pending(chat_id=1001, expected_stage=BT_PENDING_STAGE_TMDB_ASSOCIATION) is True


def test_bt_pending_repo_raises_when_upsert_row_missing(tmp_path: Path) -> None:
    class MissingRowBtPendingRepo(BtPendingRepo):
        def get_pending(self, *, chat_id: int):
            _ = chat_id
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = MissingRowBtPendingRepo(database)

    with pytest.raises(BtPendingPersistenceError, match="bt_pending_state missing after upsert"):
        repo.upsert_pending(
            chat_id=1001,
            stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
            payload_json='{"media_kind":"movie"}',
        )


def test_bt_pending_repo_rejects_empty_stage_after_read(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO bt_pending_state (chat_id, stage, payload_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (1001, "   ", '{"media_kind":"movie"}'),
        )
        connection.commit()

    repo = BtPendingRepo(SqliteDatabase(str(tmp_path / "state.sqlite3")))

    with pytest.raises(BtPendingPersistenceError, match="bt_pending_state stage empty after read"):
        repo.get_pending(chat_id=1001)


def test_bt_pending_repo_rejects_missing_stage(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = BtPendingRepo(database)

    with pytest.raises(BtPendingPersistenceError, match="bt_pending_state stage missing"):
        repo.upsert_pending(chat_id=1001, stage="   ", payload_json='{"media_kind":"movie"}')


def test_bt_pending_repo_rejects_missing_chat_identity_for_upsert(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = BtPendingRepo(database)

    with pytest.raises(BtPendingPersistenceError, match="bt_pending_state chat identity missing"):
        repo.upsert_pending(
            chat_id=0,
            stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
            payload_json='{"media_kind":"movie"}',
        )


def test_bt_pending_repo_rejects_missing_chat_identity_for_query(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = BtPendingRepo(database)

    with pytest.raises(BtPendingPersistenceError, match="bt_pending_state chat identity missing for query"):
        repo.get_pending(chat_id=0)


def test_bt_pending_repo_rejects_missing_chat_identity_for_clear(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = BtPendingRepo(database)

    with pytest.raises(BtPendingPersistenceError, match="bt_pending_state chat identity missing for clear"):
        repo.clear_pending(chat_id=0)


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


def test_job_repo_raises_when_pending_upsert_row_missing(tmp_path: Path) -> None:
    class MissingRowJobRepo(JobRepo):
        def _select_one(self, query: str, params: tuple[object, ...]):
            if "FROM jobs" in query and "WHERE job_id = ?" in query:
                return None
            return super()._select_one(query, params)

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = MissingRowJobRepo(database)

    with pytest.raises(JobPersistenceError, match="job missing after pending upsert"):
        repo.upsert_import_job_pending(
            chat_id=1001,
            user_id=2001,
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
        )

    with pytest.raises(JobPersistenceError, match="job missing after pending upsert"):
        repo.upsert_downloader_job_pending(
            chat_id=1001,
            user_id=2001,
            task_ref="88",
            task_id="88",
            task_hash="hash-88",
            payload_json='{"source":"https://example.com/demo.torrent"}',
        )


def test_job_repo_rejects_missing_identity_for_pending_upsert(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = JobRepo(database)

    with pytest.raises(JobPersistenceError, match="job chat identity missing for pending upsert"):
        repo.upsert_import_job_pending(
            chat_id=0,
            user_id=2001,
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
        )

    with pytest.raises(JobPersistenceError, match="job task identity missing for pending upsert"):
        repo.upsert_import_job_pending(
            chat_id=1001,
            user_id=2001,
            task_ref="87",
            task_id="",
            task_hash="hash-87",
        )

    with pytest.raises(JobPersistenceError, match="job task identity missing for pending upsert"):
        repo.upsert_downloader_job_pending(
            chat_id=1001,
            user_id=2001,
            task_ref="88",
            task_id="88",
            task_hash="",
            payload_json='{"source":"https://example.com/demo.torrent"}',
        )


def test_job_repo_rejects_missing_identity_for_state_transitions(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = JobRepo(database)

    with pytest.raises(JobPersistenceError, match="job state transition identity missing"):
        repo.release_lease_to_pending(
            job_id="",
            expected_version=1,
            lease_owner="owner-1",
            workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
        )

    with pytest.raises(JobPersistenceError, match="job state transition expected version missing"):
        repo.mark_completed(
            job_id="job-1",
            expected_version=0,
            lease_owner="owner-1",
            workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
        )

    with pytest.raises(JobPersistenceError, match="downloader completed job identity missing"):
        repo.mark_downloader_completed(
            job_id="job-1",
            expected_version=1,
            lease_owner="owner-1",
            task_id="",
            task_hash="hash-1",
            payload_json="{}",
        )

    with pytest.raises(JobPersistenceError, match="downloader completed job expected version missing"):
        repo.mark_downloader_completed(
            job_id="job-1",
            expected_version=0,
            lease_owner="owner-1",
            task_id="1",
            task_hash="hash-1",
            payload_json="{}",
        )


def test_job_repo_rejects_missing_identity_for_lease_and_cancel(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = JobRepo(database)

    with pytest.raises(JobPersistenceError, match="job lease identity missing"):
        repo.claim_lease(
            job_id="",
            expected_version=1,
            lease_owner="owner-1",
            workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
        )

    with pytest.raises(JobPersistenceError, match="job lease expected version missing"):
        repo.claim_lease(
            job_id="job-1",
            expected_version=0,
            lease_owner="owner-1",
            workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
        )

    with pytest.raises(JobPersistenceError, match="job cancel identity missing"):
        repo.cancel_pending_job(
            job_id="",
            expected_version=1,
            workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
        )

    with pytest.raises(JobPersistenceError, match="job cancel expected version missing"):
        repo.cancel_pending_job(
            job_id="job-1",
            expected_version=0,
            workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
        )


def test_job_repo_rejects_missing_identity_for_query(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = JobRepo(database)

    with pytest.raises(JobPersistenceError, match="job chat identity missing for query"):
        repo.get_pending_job_for_chat_ref(chat_id=0, task_ref="87")

    with pytest.raises(JobPersistenceError, match="job task ref missing for query"):
        repo.get_job_for_chat_ref(chat_id=1001, task_ref="   ")

    with pytest.raises(JobPersistenceError, match="job chat identity missing for pending query"):
        repo.get_latest_pending_job(chat_id=0)

    with pytest.raises(JobPersistenceError, match="job workflow missing for query"):
        repo._get_job_for_chat_ref(workflow_type="   ", chat_id=1001, task_ref="87")

    with pytest.raises(JobPersistenceError, match="job workflow missing for pending query"):
        repo._get_latest_pending_job_for_workflow(workflow_type="   ", chat_id=1001)


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
    assert events[2].source_path == str(source_file)
    assert events[2].target_path == str(target_dir / "Dune (2021).mkv")


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


def test_watchlist_repo_rejects_missing_identity_for_add(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = WatchlistRepo(database)

    with pytest.raises(WatchlistPersistenceError, match="watchlist_item chat identity missing"):
        repo.add_item(chat_id=0, title="Dune", year="2021", media_kind="movie")

    with pytest.raises(WatchlistPersistenceError, match="watchlist_item title missing"):
        repo.add_item(chat_id=1001, title="   ", year="2021", media_kind="movie")


def test_bt_subscription_repo_rejects_missing_identity_for_add(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = BtSubscriptionRepo(database)

    with pytest.raises(BtSubscriptionPersistenceError, match="bt_subscription_item chat identity missing"):
        repo.add_item(chat_id=0, title="Frieren", year="2023", media_kind="anime")

    with pytest.raises(BtSubscriptionPersistenceError, match="bt_subscription_item title missing"):
        repo.add_item(chat_id=1001, title="   ", year="2023", media_kind="anime")

    with pytest.raises(BtSubscriptionPersistenceError, match="bt_subscription_item media kind missing"):
        repo.add_item(chat_id=1001, title="Frieren", year="2023", media_kind="   ")


def test_bt_subscription_repo_rejects_missing_identity_for_last_seen_update(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = BtSubscriptionRepo(database)

    with pytest.raises(BtSubscriptionPersistenceError, match="bt_subscription_item identity missing for last_seen update"):
        repo.update_last_seen(
            chat_id=0,
            item_id=1,
            source="https://example.com/frieren.torrent",
            title="Frieren S01E01 1080p",
        )

    with pytest.raises(BtSubscriptionPersistenceError, match="bt_subscription_item source missing for last_seen update"):
        repo.update_last_seen(
            chat_id=1001,
            item_id=1,
            source="   ",
            title="Frieren S01E01 1080p",
        )


def test_bt_subscription_repo_rejects_missing_identity_for_remove(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = BtSubscriptionRepo(database)

    with pytest.raises(BtSubscriptionPersistenceError, match="bt_subscription_item identity missing for remove"):
        repo.remove_item(chat_id=0, item_id=1)

    with pytest.raises(BtSubscriptionPersistenceError, match="bt_subscription_item identity missing for remove"):
        repo.remove_item(chat_id=1001, item_id=0)


def test_bt_subscription_repo_rejects_missing_chat_identity_for_clear(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = BtSubscriptionRepo(database)

    with pytest.raises(BtSubscriptionPersistenceError, match="bt_subscription_item chat identity missing for clear"):
        repo.clear_items(chat_id=0)


def test_watchlist_repo_rejects_missing_identity_for_remove(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = WatchlistRepo(database)

    with pytest.raises(WatchlistPersistenceError, match="watchlist_item identity missing for remove"):
        repo.remove_item(chat_id=0, item_id=1)

    with pytest.raises(WatchlistPersistenceError, match="watchlist_item identity missing for remove"):
        repo.remove_item(chat_id=1001, item_id=0)


def test_watchlist_repo_rejects_missing_chat_identity_for_clear(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = WatchlistRepo(database)

    with pytest.raises(WatchlistPersistenceError, match="watchlist_item chat identity missing for clear"):
        repo.clear_items(chat_id=0)


def test_watchlist_repo_rejects_missing_chat_identity_for_list(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = WatchlistRepo(database)

    with pytest.raises(WatchlistPersistenceError, match="watchlist_item chat identity missing for list"):
        repo.list_items(chat_id=0)


def test_watchlist_repo_rejects_missing_identity_for_id_lookup(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = WatchlistRepo(database)

    with pytest.raises(WatchlistPersistenceError, match="watchlist_item identity missing for id lookup"):
        repo.get_item_by_id(chat_id=0, item_id=1)

    with pytest.raises(WatchlistPersistenceError, match="watchlist_item identity missing for id lookup"):
        repo.get_item_by_id(chat_id=1001, item_id=0)


def test_watchlist_repo_rejects_missing_identity_for_exact_lookup(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = WatchlistRepo(database)

    with pytest.raises(WatchlistPersistenceError, match="watchlist_item identity missing for exact lookup"):
        repo.get_item_by_identity(chat_id=0, title="Dune", year="2021", media_kind="movie")

    with pytest.raises(WatchlistPersistenceError, match="watchlist_item title missing for exact lookup"):
        repo.get_item_by_identity(chat_id=1001, title="   ", year="2021", media_kind="movie")


def test_bt_subscription_repo_rejects_missing_chat_identity_for_list(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = BtSubscriptionRepo(database)

    with pytest.raises(BtSubscriptionPersistenceError, match="bt_subscription_item chat identity missing for list"):
        repo.list_items(chat_id=0)


def test_approval_repo_raises_when_upsert_row_missing(tmp_path: Path) -> None:
    class MissingRowApprovalRepo(ApprovalRepo):
        def _get_exact_approval_record(
            self,
            *,
            action_type: str,
            task_id: str,
            task_hash: str,
        ):
            _ = (action_type, task_id, task_hash)
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = MissingRowApprovalRepo(database)

    with pytest.raises(ApprovalPersistenceError, match="approval_record missing after upsert"):
        repo.upsert_import_approval(task_id="87", task_hash="hash-87", task_ref="87")


def test_approval_repo_rejects_missing_identity_for_write_paths(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ApprovalRepo(database)

    with pytest.raises(ApprovalPersistenceError, match="approval task identity missing for upsert"):
        repo.upsert_import_approval(task_id="", task_hash="hash-87", task_ref="87")

    with pytest.raises(ApprovalPersistenceError, match="approval status missing for upsert"):
        repo.upsert_import_approval(task_id="87", task_hash="hash-87", task_ref="87", status="")

    with pytest.raises(ApprovalPersistenceError, match="approval task identity missing for pending request"):
        repo.request_import_approval(task_id="", task_hash="hash-87", task_ref="87")

    with pytest.raises(ApprovalPersistenceError, match="approval task identity missing for pending request"):
        repo.request_downloader_approval(task_id="88", task_hash="", task_ref="88")

    with pytest.raises(ApprovalPersistenceError, match="approval task identity missing for executed version update"):
        repo.mark_import_executed(task_id="", task_hash="hash-87", executed_lease_version=1)

    with pytest.raises(ApprovalPersistenceError, match="approval executed lease version missing"):
        repo.mark_downloader_executed(task_id="88", task_hash="hash-88", executed_lease_version=0)


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


def test_approval_repo_raises_when_pending_request_row_missing(tmp_path: Path) -> None:
    class MissingRowApprovalRepo(ApprovalRepo):
        def _get_requested_lease_version(
            self,
            *,
            action_type: str,
            task_id: str,
            task_hash: str,
        ) -> int | None:
            _ = (action_type, task_id, task_hash)
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = MissingRowApprovalRepo(database)

    with pytest.raises(ApprovalPersistenceError, match="approval_record missing after pending request"):
        repo.request_import_approval(task_id="87", task_hash="hash-87", task_ref="87")

    with pytest.raises(ApprovalPersistenceError, match="approval_record missing after pending request"):
        repo.request_downloader_approval(task_id="88", task_hash="hash-88", task_ref="88")


def test_approval_repo_raises_when_mark_executed_row_missing(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ApprovalRepo(database)

    with pytest.raises(ApprovalPersistenceError, match="approval_record missing during executed version update"):
        repo.mark_import_executed(task_id="87", task_hash="hash-87", executed_lease_version=1)

    with pytest.raises(ApprovalPersistenceError, match="approval_record missing during executed version update"):
        repo.mark_downloader_executed(task_id="88", task_hash="hash-88", executed_lease_version=1)


def test_approval_repo_rejects_missing_identity_for_pending_expiry_check(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ApprovalRepo(database)

    with pytest.raises(ApprovalPersistenceError, match="approval task identity missing for pending expiry check"):
        repo.is_import_pending_expired(
            task_id="",
            task_hash="hash-87",
            expected_lease_version=1,
        )

    with pytest.raises(ApprovalPersistenceError, match="approval expected lease version missing for pending expiry check"):
        repo.is_downloader_pending_expired(
            task_id="88",
            task_hash="hash-88",
            expected_lease_version=0,
        )


def test_approval_repo_rejects_missing_identity_for_query(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ApprovalRepo(database)

    with pytest.raises(ApprovalPersistenceError, match="approval task identity missing for query"):
        repo.get_import_approval(task_id="", task_hash="hash-87")

    with pytest.raises(ApprovalPersistenceError, match="approval task identity missing for query"):
        repo.get_downloader_approval(task_id="88", task_hash="")


def test_approval_repo_rejects_task_hash_mismatch_for_query(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ApprovalRepo(database)
    repo.request_import_approval(task_id="87", task_hash="hash-87", task_ref="87")

    with pytest.raises(ApprovalPersistenceError, match="approval task hash mismatch for query"):
        repo.get_import_approval(task_id="87", task_hash="hash-other")


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


def test_approval_repo_rejects_missing_identity_for_state_transition(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    repo = ApprovalRepo(database)

    with pytest.raises(ApprovalPersistenceError, match="approval task identity missing for state transition"):
        repo.approve_import(task_id="", task_hash="hash-87", task_ref="87", expected_lease_version=1)

    with pytest.raises(ApprovalPersistenceError, match="approval expected lease version missing for state transition"):
        repo.restore_import_pending(
            task_id="87",
            task_hash="hash-87",
            task_ref="87",
            expected_lease_version=0,
        )

    with pytest.raises(ApprovalPersistenceError, match="approval task identity missing for state transition"):
        repo.cancel_downloader(task_id="88", task_hash="", task_ref="88", expected_lease_version=1)


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

    imported_target = target_dir / "Dune (2021).mkv"
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

    target_file = target_dir / "Dune (2021).mkv"
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
        source_path="/data/downloads/Dune.2021.mkv",
        target_path="/data/library/movies/Dune.2021.mkv",
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
    assert events[0].source_path == "/data/downloads/Dune.2021.mkv"
    assert events[0].target_path == "/data/library/movies/Dune.2021.mkv"


def test_job_event_repo_finds_latest_import_correlation_with_message_fallback(tmp_path: Path) -> None:
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

    correlation = repo.find_latest_import_correlation(task_id="87", task_hash="hash-87")
    assert correlation is not None
    assert correlation.source_path == ""
    assert correlation.target_path == "/data/library/movies/Dune.2021.mkv"


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
