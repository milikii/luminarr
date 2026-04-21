from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from app.bot.download_follow_up_runtime import (
    download_completion_polling_loop,
    poll_pending_download_completion_once,
    post_download_auto_import_scheduler_loop,
    start_download_follow_up_scheduler,
    stop_download_follow_up_scheduler,
)
from app.bot.telegram_bot import (
    DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
    DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
    POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
    POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
)
from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.get_download_status import GetDownloadStatusService
from app.services.post_download_auto_import import AutoImportRunResult, PostDownloadAutoImportService


def test_post_download_auto_import_scheduler_loop_runs_once_and_stops() -> None:
    stop_event = asyncio.Event()

    async def run_once() -> AutoImportRunResult:
        stop_event.set()
        return AutoImportRunResult(scanned=1, progressed=1, replies=("导入待确认",))

    service = SimpleNamespace(run_once=AsyncMock(side_effect=run_once))

    asyncio.run(
        post_download_auto_import_scheduler_loop(
            service=service,
            stop_event=stop_event,
            interval_seconds=300.0,
        )
    )

    service.run_once.assert_awaited_once()


def test_post_download_auto_import_scheduler_loop_logs_state_unavailable(capsys: pytest.CaptureFixture[str]) -> None:
    stop_event = asyncio.Event()

    async def run_once() -> AutoImportRunResult:
        stop_event.set()
        return AutoImportRunResult(scanned=2, progressed=0, replies=(), state_unavailable=True)

    service = SimpleNamespace(run_once=AsyncMock(side_effect=run_once))

    asyncio.run(
        post_download_auto_import_scheduler_loop(
            service=service,
            stop_event=stop_event,
            interval_seconds=300.0,
        )
    )

    output = capsys.readouterr().out
    assert "[下载完成后台轮询状态读取失败]" in output
    assert "scanned=2" in output
    assert "[处理建议]" in output


def test_poll_pending_download_completion_once_reuses_status_service() -> None:
    repo = SimpleNamespace(
        list_pending_completion=Mock(
            return_value=(SimpleNamespace(task_hash="hash-41", chat_id=1001), SimpleNamespace(task_hash="hash-42", chat_id=1002))
        )
    )
    status_service = SimpleNamespace(get_status_text=AsyncMock())

    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=repo,
            status_service=status_service,
        )
    )

    assert status_service.get_status_text.await_args_list == [call("hash-41", chat_id=1001), call("hash-42", chat_id=1002)]


def test_poll_pending_download_completion_once_logs_pending_list_failure(capsys: pytest.CaptureFixture[str]) -> None:
    repo = SimpleNamespace(list_pending_completion=Mock(side_effect=RuntimeError("db down")))
    status_service = SimpleNamespace(get_status_text=AsyncMock())

    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=repo,
            status_service=status_service,
        )
    )

    output = capsys.readouterr().out
    assert "[下载完成待轮询列表读取失败]" in output
    assert "db down" in output
    assert "[处理建议]" in output
    status_service.get_status_text.assert_not_awaited()


def test_poll_pending_download_completion_once_logs_pending_list_missing_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = SimpleNamespace(list_pending_completion=Mock(return_value=None))
    status_service = SimpleNamespace(get_status_text=AsyncMock())

    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=repo,
            status_service=status_service,
        )
    )

    output = capsys.readouterr().out
    assert "[下载完成待轮询列表结果缺失]" in output
    assert "download completion pending list result missing" in output
    assert "[处理建议]" in output
    status_service.get_status_text.assert_not_awaited()


def test_poll_pending_download_completion_once_logs_pending_list_row_corruption(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = SimpleNamespace(
        list_pending_completion=Mock(
            side_effect=DownloadMonitorPersistenceError("download monitor chat identity corrupted after read")
        )
    )
    status_service = SimpleNamespace(get_status_text=AsyncMock())

    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=repo,
            status_service=status_service,
        )
    )

    output = capsys.readouterr().out
    assert "[下载完成待轮询列表记录损坏]" in output
    assert "download monitor chat identity corrupted after read" in output
    assert "[处理建议]" in output
    status_service.get_status_text.assert_not_awaited()


def test_download_completion_polling_loop_runs_once_and_stops() -> None:
    stop_event = asyncio.Event()

    def list_pending_completion():
        stop_event.set()
        return ()

    repo = SimpleNamespace(list_pending_completion=Mock(side_effect=list_pending_completion))
    asyncio.run(
        download_completion_polling_loop(
            download_monitor_repo=repo,
            status_service=SimpleNamespace(get_status_text=AsyncMock()),
            stop_event=stop_event,
            interval_seconds=300.0,
        )
    )
    repo.list_pending_completion.assert_called_once_with()


def test_download_completion_polling_loop_logs_fix_hint_on_error(capsys: pytest.CaptureFixture[str]) -> None:
    stop_event = asyncio.Event()
    repo = SimpleNamespace(
        list_pending_completion=Mock(return_value=(SimpleNamespace(task_hash="hash-41", chat_id=1001),))
    )

    async def _boom(*args, **kwargs):
        stop_event.set()
        raise RuntimeError("boom")

    asyncio.run(
        download_completion_polling_loop(
            download_monitor_repo=repo,
            status_service=SimpleNamespace(get_status_text=AsyncMock(side_effect=_boom)),
            stop_event=stop_event,
            interval_seconds=300.0,
        )
    )
    captured = capsys.readouterr()
    assert "[下载完成状态轮询失败]" in captured.out
    assert "[处理建议]" in captured.out


def test_start_download_follow_up_scheduler_also_starts_download_completion_polling() -> None:
    database = SqliteDatabase(":memory:")
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    status_service = GetDownloadStatusService(AsyncMock(), download_monitor_repo=monitor_repo)
    app = SimpleNamespace(
        bot_data={
            GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
            POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY: PostDownloadAutoImportService(monitor_repo, JobEventRepo(database), AsyncMock()),
        },
        create_task=Mock(return_value=SimpleNamespace()),
    )

    start_download_follow_up_scheduler(
        application=app,
        post_download_auto_import_service_key=POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
        post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
        post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
        get_download_status_service_key=GET_DOWNLOAD_STATUS_SERVICE_KEY,
        download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
        download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
        interval_seconds=300.0,
    )

    assert [item.kwargs["name"] for item in app.create_task.call_args_list] == [
        "post_download_auto_import_scheduler",
        "download_completion_polling_scheduler",
    ]
    for item in app.create_task.call_args_list:
        item.args[0].close()


def test_start_download_follow_up_scheduler_starts_completion_polling_without_auto_import_service() -> None:
    database = SqliteDatabase(":memory:")
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    app = SimpleNamespace(
        bot_data={GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock(), download_monitor_repo=monitor_repo)},
        create_task=Mock(return_value=SimpleNamespace()),
    )

    start_download_follow_up_scheduler(
        application=app,
        post_download_auto_import_service_key=POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
        post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
        post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
        get_download_status_service_key=GET_DOWNLOAD_STATUS_SERVICE_KEY,
        download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
        download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
        interval_seconds=300.0,
    )

    assert [item.kwargs["name"] for item in app.create_task.call_args_list] == ["download_completion_polling_scheduler"]
    app.create_task.call_args_list[0].args[0].close()


def test_start_download_follow_up_scheduler_logs_fix_hint_when_completion_polling_missing_repo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = SimpleNamespace(
        bot_data={GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock())},
        create_task=Mock(return_value=SimpleNamespace()),
    )

    start_download_follow_up_scheduler(
        application=app,
        post_download_auto_import_service_key=POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
        post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
        post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
        get_download_status_service_key=GET_DOWNLOAD_STATUS_SERVICE_KEY,
        download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
        download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
        interval_seconds=300.0,
    )

    captured = capsys.readouterr()
    assert "[下载完成状态轮询未启动]" in captured.out
    assert "[处理建议]" in captured.out


def test_stop_download_follow_up_scheduler_stops_download_completion_polling_task() -> None:
    async def run() -> None:
        first_stop_event = asyncio.Event()
        first_task = asyncio.create_task(first_stop_event.wait())
        second_stop_event = asyncio.Event()
        second_task = asyncio.create_task(second_stop_event.wait())
        application = SimpleNamespace(
            bot_data={
                POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY: first_stop_event,
                POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY: first_task,
                DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY: second_stop_event,
                DOWNLOAD_COMPLETION_POLLING_TASK_KEY: second_task,
            }
        )

        await stop_download_follow_up_scheduler(
            application=application,
            post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
            post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
            download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
            download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
        )

        assert first_stop_event.is_set() and second_stop_event.is_set()
        assert first_task.done() and second_task.done()

    asyncio.run(run())


def test_stop_download_follow_up_scheduler_logs_fix_hint_when_completion_polling_task_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def boom() -> None:
        raise RuntimeError("boom")

    async def run() -> None:
        failing_task = asyncio.create_task(boom())
        application = SimpleNamespace(
            bot_data={
                DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY: asyncio.Event(),
                DOWNLOAD_COMPLETION_POLLING_TASK_KEY: failing_task,
            }
        )
        with pytest.raises(RuntimeError, match="boom"):
            await stop_download_follow_up_scheduler(
                application=application,
                post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
                post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
                download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
                download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
            )

    asyncio.run(run())
    captured = capsys.readouterr()
    assert "[下载完成状态轮询停止失败]" in captured.out
    assert "[处理建议]" in captured.out
