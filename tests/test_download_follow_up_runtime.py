from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from app.clients.transmission import TransmissionTaskStatus
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
from app.services.post_download_auto_import import (
    AutoImportRunResult,
    POST_PROCESSING_SUMMARY_EVENT,
    PostDownloadAutoImportService,
)


def test_post_download_auto_import_scheduler_loop_runs_once_and_stops() -> None:
    stop_event = asyncio.Event()
    send_text = AsyncMock()

    async def run_once() -> AutoImportRunResult:
        stop_event.set()
        return AutoImportRunResult(
            scanned=1,
            progressed=1,
            replies=("导入成功",),
            notifications=(SimpleNamespace(chat_id=1001, text="导入成功"),),
        )

    service = SimpleNamespace(run_once=AsyncMock(side_effect=run_once))

    asyncio.run(
        post_download_auto_import_scheduler_loop(
            service=service,
            send_text_func=send_text,
            stop_event=stop_event,
            interval_seconds=300.0,
        )
    )

    service.run_once.assert_awaited_once()
    send_text.assert_awaited_once_with(chat_id=1001, text="导入成功")


def test_post_download_auto_import_scheduler_loop_sends_single_final_summary_notification() -> None:
    stop_event = asyncio.Event()
    send_text = AsyncMock()

    async def run_once() -> AutoImportRunResult:
        stop_event.set()
        return AutoImportRunResult(
            scanned=1,
            progressed=1,
            replies=("后处理总结",),
            notifications=(
                SimpleNamespace(
                    chat_id=1001,
                    text="🏁 <b>入库完成</b>\n<b>Dune 2024</b>\n\n✅ 全部后处理已完成\n\n📁 <b>入库路径：</b>\n<code>/library/Dune 2024</code>",
                ),
            ),
        )

    service = SimpleNamespace(run_once=AsyncMock(side_effect=run_once))

    asyncio.run(
        post_download_auto_import_scheduler_loop(
            service=service,
            send_text_func=send_text,
            stop_event=stop_event,
            interval_seconds=300.0,
        )
    )

    assert send_text.await_args_list == [
        call(
            chat_id=1001,
            text="🏁 <b>入库完成</b>\n<b>Dune 2024</b>\n\n✅ 全部后处理已完成\n\n📁 <b>入库路径：</b>\n<code>/library/Dune 2024</code>",
        ),
    ]


def test_post_download_auto_import_scheduler_loop_logs_state_unavailable(capsys: pytest.CaptureFixture[str]) -> None:
    stop_event = asyncio.Event()
    send_text = AsyncMock()

    async def run_once() -> AutoImportRunResult:
        stop_event.set()
        return AutoImportRunResult(scanned=2, progressed=0, replies=(), state_unavailable=True)

    service = SimpleNamespace(run_once=AsyncMock(side_effect=run_once))

    asyncio.run(
        post_download_auto_import_scheduler_loop(
            service=service,
            send_text_func=send_text,
            stop_event=stop_event,
            interval_seconds=300.0,
        )
    )

    output = capsys.readouterr().out
    assert "[下载完成后台轮询状态读取失败]" in output
    assert "scanned=2" in output
    assert "[处理建议]" in output
    send_text.assert_not_awaited()


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


def test_poll_pending_download_completion_once_edits_bound_telegram_message_and_dedupes_same_status(
    tmp_path,
) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 1984",
        chat_id=1001,
        user_id=2001,
    )
    monitor_repo.bind_telegram_message(task_id="87", task_hash="hash-87", message_id=321)
    status_service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=4,
                percent_done=0.56,
                rate_download=1048576,
                eta_seconds=121,
            )
        ),
        download_monitor_repo=monitor_repo,
    )
    edit_message_text = AsyncMock(return_value="edited")

    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=monitor_repo,
            status_service=status_service,
            telegram_edit_message_func=edit_message_text,
            min_telegram_progress_edit_interval_seconds=300.0,
        )
    )
    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=monitor_repo,
            status_service=status_service,
            telegram_edit_message_func=edit_message_text,
            min_telegram_progress_edit_interval_seconds=300.0,
        )
    )

    assert edit_message_text.await_count == 1
    assert status_service._get_status_func.await_count == 2  # type: ignore[attr-defined]
    kwargs = edit_message_text.await_args.kwargs
    assert kwargs["chat_id"] == 1001
    assert kwargs["message_id"] == 321
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["text"].startswith("⏳ <b>任务下载中</b>")
    assert "<b>状态：</b> 下载中" in kwargs["text"]
    assert "<b>下载进度：</b> 56%" in kwargs["text"]
    assert "<code>[██████░░░░]</code>" in kwargs["text"]
    assert "⚡ <b>速度：</b> 1.0 MB/s" in kwargs["text"]
    assert "reply_markup" not in kwargs


def test_poll_pending_download_completion_once_edits_completion_card_once_then_stops(tmp_path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 1984",
        chat_id=1001,
        user_id=2001,
    )
    monitor_repo.bind_telegram_message(task_id="87", task_hash="hash-87", message_id=321)
    status_service = GetDownloadStatusService(
        AsyncMock(
            side_effect=[
                TransmissionTaskStatus(
                    task_id="87",
                    task_hash="hash-87",
                    name="Dune 1984",
                    status_code=4,
                    percent_done=0.56,
                    rate_download=1048576,
                    eta_seconds=121,
                ),
                TransmissionTaskStatus(
                    task_id="87",
                    task_hash="hash-87",
                    name="Dune 1984",
                    status_code=6,
                    percent_done=1.0,
                    rate_download=0,
                    eta_seconds=-1,
                ),
                TransmissionTaskStatus(
                    task_id="87",
                    task_hash="hash-87",
                    name="Dune 1984",
                    status_code=6,
                    percent_done=1.0,
                    rate_download=0,
                    eta_seconds=-1,
                ),
            ]
        ),
        download_monitor_repo=monitor_repo,
    )
    edit_message_text = AsyncMock(return_value="edited")

    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=monitor_repo,
            status_service=status_service,
            telegram_edit_message_func=edit_message_text,
            min_telegram_progress_edit_interval_seconds=300.0,
        )
    )
    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=monitor_repo,
            status_service=status_service,
            telegram_edit_message_func=edit_message_text,
            min_telegram_progress_edit_interval_seconds=300.0,
        )
    )
    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=monitor_repo,
            status_service=status_service,
            telegram_edit_message_func=edit_message_text,
            min_telegram_progress_edit_interval_seconds=300.0,
        )
    )

    assert edit_message_text.await_count == 2
    assert edit_message_text.await_args_list[1].kwargs["text"].startswith("✅ <b>下载完成</b>")
    assert "<b>状态：</b> 后处理中" in edit_message_text.await_args_list[1].kwargs["text"]
    assert monitor_repo.list_pending_completion() == []


def test_poll_pending_download_completion_once_sends_single_final_summary_after_terminal_post_processing(
    tmp_path,
) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    event_repo = JobEventRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 1984",
        chat_id=1001,
        user_id=2001,
    )
    monitor_repo.bind_telegram_message(task_id="87", task_hash="hash-87", message_id=321)
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message="/library/Dune 1984",
        target_path="/library/Dune 1984",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="metadata.succeeded",
        message="metadata 刮削成功：/tmp/demo.metadata.json",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="subtitle.succeeded",
        message="字幕翻译成功：已生成 1 个字幕文件。",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="refresh.succeeded",
        message="媒体库刷新成功。",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type=POST_PROCESSING_SUMMARY_EVENT,
        message=(
            "导入成功：Dune 1984\n"
            "任务 ID: 87\n"
            "任务 Hash: hash-87\n"
            "目标路径: /library/Dune 1984\n\n"
            "后处理总结\n"
            "- metadata：成功；metadata 刮削成功：/tmp/demo.metadata.json\n"
            "- 字幕：成功；字幕翻译成功：已生成 1 个字幕文件。\n"
            "- 刷新：成功；媒体库刷新成功。"
        ),
    )
    status_service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
    )
    edit_message_text = AsyncMock(return_value="edited")
    send_text = AsyncMock(return_value="sent")

    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=monitor_repo,
            status_service=status_service,
            send_text_func=send_text,
            telegram_edit_message_func=edit_message_text,
            min_telegram_progress_edit_interval_seconds=300.0,
        )
    )

    send_text.assert_awaited_once_with(
        chat_id=1001,
        text="🏁 <b>入库完成</b>\n<b>Dune 1984</b>\n\n✅ 全部后处理已完成\n\n📁 <b>入库路径：</b>\n<code>/library/Dune 1984</code>",
        parse_mode="HTML",
    )
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert any(event.event_type == "telegram.summary_sent" for event in events)


def test_poll_pending_download_completion_once_resumes_completed_telegram_card_after_restart(tmp_path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()

    setup_monitor_repo = DownloadMonitorRepo(database)
    setup_event_repo = JobEventRepo(database)
    setup_monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 1984",
        chat_id=1001,
        user_id=2001,
    )
    setup_monitor_repo.bind_telegram_message(task_id="87", task_hash="hash-87", message_id=321)
    setup_monitor_repo.record_status(
        TransmissionTaskStatus(
            task_id="87",
            task_hash="hash-87",
            name="Dune 1984",
            status_code=6,
            percent_done=1.0,
            rate_download=0,
            eta_seconds=-1,
        )
    )
    setup_monitor_repo.record_telegram_progress_sync(
        task_id="87",
        task_hash="hash-87",
        text=(
            "✅ <b>下载完成</b>\n"
            "<i>Dune 1984</i>\n"
            "━━━━━━━━━━━━\n"
            "<b>状态：</b> 后处理中\n"
            "<b>下载进度：</b> 100%\n"
            "<code>[██████████]</code>\n\n"
            "━━━━━━━━━━━━\n"
            "<b>后处理</b>\n"
            "- 导入：等待\n"
            "- 刮削：等待\n"
            "- 字幕：等待\n"
            "- 刷新：等待\n"
            "━━━━━━━━━━━━\n"
            "🆔 <b>任务 ID：</b> <code>87</code>\n"
            "🔑 <b>Hash：</b> <code>hash-87</code>"
        ),
    )
    setup_event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message="/library/Dune 1984",
        target_path="/library/Dune 1984",
    )

    monitor_repo = DownloadMonitorRepo(database)
    event_repo = JobEventRepo(database)
    status_service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
    )
    edit_message_text = AsyncMock(return_value="edited")

    asyncio.run(
        poll_pending_download_completion_once(
            download_monitor_repo=monitor_repo,
            status_service=status_service,
            telegram_edit_message_func=edit_message_text,
            min_telegram_progress_edit_interval_seconds=300.0,
        )
    )

    edit_message_text.assert_awaited_once()
    kwargs = edit_message_text.await_args.kwargs
    assert kwargs["chat_id"] == 1001
    assert kwargs["message_id"] == 321
    assert kwargs["text"].startswith("✅ <b>下载完成</b>")
    assert "- 导入：✅ 已完成" in kwargs["text"]


def test_poll_pending_download_completion_once_logs_pending_list_failure(capsys: pytest.CaptureFixture[str]) -> None:
    repo = SimpleNamespace(list_pending_completion=Mock(side_effect=sqlite3.OperationalError("db down")))
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
            "sidecar_host_send_text_func": AsyncMock(),
        },
        create_task=Mock(return_value=SimpleNamespace()),
    )

    start_download_follow_up_scheduler(
        application=app,
        send_text_func_key="sidecar_host_send_text_func",
        post_download_auto_import_service_key=POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
        post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
        post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
        get_download_status_service_key=GET_DOWNLOAD_STATUS_SERVICE_KEY,
        download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
        download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
        interval_seconds=300.0,
        download_completion_interval_seconds=5.0,
    )

    assert [item.kwargs["name"] for item in app.create_task.call_args_list] == [
        "post_download_auto_import_scheduler",
        "download_completion_polling_scheduler",
    ]
    for item in app.create_task.call_args_list:
        item.args[0].close()


def test_start_download_follow_up_scheduler_uses_fast_completion_polling_interval() -> None:
    database = SqliteDatabase(":memory:")
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    status_service = GetDownloadStatusService(AsyncMock(), download_monitor_repo=monitor_repo)
    app = SimpleNamespace(
        bot_data={
            GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
            POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY: PostDownloadAutoImportService(monitor_repo, JobEventRepo(database), AsyncMock()),
            "sidecar_host_send_text_func": AsyncMock(),
        },
        create_task=Mock(return_value=SimpleNamespace()),
    )
    captured: list[tuple[str, float]] = []

    async def fake_auto_import_loop(*, interval_seconds: float, **kwargs) -> None:
        captured.append(("auto_import", interval_seconds))

    async def fake_completion_loop(*, interval_seconds: float, min_telegram_progress_edit_interval_seconds: float | None = None, **kwargs) -> None:
        captured.append(("completion", interval_seconds))
        captured.append(("completion_edit", float(min_telegram_progress_edit_interval_seconds or -1)))

    from app.bot import download_follow_up_runtime as runtime

    original_auto_import_loop = runtime.post_download_auto_import_scheduler_loop
    original_completion_loop = runtime.download_completion_polling_loop
    runtime.post_download_auto_import_scheduler_loop = fake_auto_import_loop
    runtime.download_completion_polling_loop = fake_completion_loop
    try:
        start_download_follow_up_scheduler(
            application=app,
            send_text_func_key="sidecar_host_send_text_func",
            post_download_auto_import_service_key=POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
            post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
            post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
            get_download_status_service_key=GET_DOWNLOAD_STATUS_SERVICE_KEY,
            download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
            download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
            interval_seconds=300.0,
            download_completion_polling_interval_seconds=5.0,
            min_telegram_progress_edit_interval_seconds=5.0,
        )
    finally:
        runtime.post_download_auto_import_scheduler_loop = original_auto_import_loop
        runtime.download_completion_polling_loop = original_completion_loop

    asyncio.run(app.create_task.call_args_list[0].args[0])
    asyncio.run(app.create_task.call_args_list[1].args[0])
    assert captured == [("auto_import", 300.0), ("completion", 5.0), ("completion_edit", 5.0)]


def test_start_download_follow_up_scheduler_starts_completion_polling_without_auto_import_service() -> None:
    database = SqliteDatabase(":memory:")
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    app = SimpleNamespace(
        bot_data={
            GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock(), download_monitor_repo=monitor_repo),
            "sidecar_host_send_text_func": AsyncMock(),
        },
        create_task=Mock(return_value=SimpleNamespace()),
    )

    start_download_follow_up_scheduler(
        application=app,
        send_text_func_key="sidecar_host_send_text_func",
        post_download_auto_import_service_key=POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
        post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
        post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
        get_download_status_service_key=GET_DOWNLOAD_STATUS_SERVICE_KEY,
        download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
        download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
        interval_seconds=300.0,
        download_completion_interval_seconds=5.0,
    )

    assert [item.kwargs["name"] for item in app.create_task.call_args_list] == ["download_completion_polling_scheduler"]
    app.create_task.call_args_list[0].args[0].close()


def test_start_download_follow_up_scheduler_logs_fix_hint_when_completion_polling_missing_repo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = SimpleNamespace(
        bot_data={
            GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
            "sidecar_host_send_text_func": AsyncMock(),
        },
        create_task=Mock(return_value=SimpleNamespace()),
    )

    start_download_follow_up_scheduler(
        application=app,
        send_text_func_key="sidecar_host_send_text_func",
        post_download_auto_import_service_key=POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
        post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
        post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
        get_download_status_service_key=GET_DOWNLOAD_STATUS_SERVICE_KEY,
        download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
        download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
        interval_seconds=300.0,
        download_completion_interval_seconds=5.0,
    )

    captured = capsys.readouterr()
    assert "[下载完成状态轮询未启动]" in captured.out
    assert "[处理建议]" in captured.out


def test_start_download_follow_up_scheduler_logs_missing_send_text_for_auto_import_push(
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = SqliteDatabase(":memory:")
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    app = SimpleNamespace(
        bot_data={
            GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock(), download_monitor_repo=monitor_repo),
            POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY: PostDownloadAutoImportService(monitor_repo, JobEventRepo(database), AsyncMock()),
        },
        create_task=Mock(return_value=SimpleNamespace()),
    )

    start_download_follow_up_scheduler(
        application=app,
        send_text_func_key="sidecar_host_send_text_func",
        post_download_auto_import_service_key=POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
        post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
        post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
        get_download_status_service_key=GET_DOWNLOAD_STATUS_SERVICE_KEY,
        download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
        download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
        interval_seconds=300.0,
        download_completion_interval_seconds=5.0,
    )

    captured = capsys.readouterr()
    assert "[下载完成后台轮询未启动主动通知]" in captured.out
    assert [item.kwargs["name"] for item in app.create_task.call_args_list] == ["download_completion_polling_scheduler"]
    app.create_task.call_args_list[0].args[0].close()


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


def test_stop_download_follow_up_scheduler_logs_fix_hint_when_auto_import_task_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def boom() -> None:
        raise RuntimeError("auto import boom")

    async def run() -> None:
        failing_task = asyncio.create_task(boom())
        application = SimpleNamespace(
            bot_data={
                POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY: asyncio.Event(),
                POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY: failing_task,
            }
        )
        with pytest.raises(RuntimeError, match="auto import boom"):
            await stop_download_follow_up_scheduler(
                application=application,
                post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
                post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
                download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
                download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
            )

    asyncio.run(run())
    captured = capsys.readouterr()
    assert "[下载完成后台轮询停止失败]" in captured.out
    assert "auto import boom" in captured.out
    assert "[处理建议]" in captured.out


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
