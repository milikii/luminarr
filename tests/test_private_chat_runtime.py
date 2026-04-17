from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.bot.personal_wechat_login import (
    PERSONAL_WECHAT_LOGIN_SERVICE_KEY,
    PERSONAL_WECHAT_LOGIN_STARTED_TEXT,
    PersonalWeChatLoginService,
)
from app.bot.private_chat_runtime import dispatch_private_chat_text
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    BT_PENDING_REPO_KEY,
    BT_PROCESSING_PATH_PROMPT_TEXT,
    CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    JOB_REPO_KEY,
    SEARCH_SERVICE_KEY,
    SERVICE_NOT_READY_TEXT,
    TELEGRAM_SEND_MEDIA_FUNC_KEY,
    TELEGRAM_SEND_TEXT_FUNC_KEY,
)
from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JobRepo
from app.db.bt_pending_repo import BtPendingRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import ADD_CANCEL_STATE_UNAVAILABLE_TEXT, AddToDownloaderService
from app.services.cleanup_downloaded_source import CleanupDownloadedSourceService
from app.services.cleanup_downloaded_source import (
    CLEANUP_INSPECT_QUERY_USAGE_TEXT,
    CLEANUP_QUERY_USAGE_TEXT,
)
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import ImportToLibraryService
from app.services.search_media import SearchMediaService


async def _fake_search(query: str) -> list[dict[str, object]]:
    return [
        {
            "title": f"title-{query}",
            "year": 2026,
            "quality": "1080p",
            "size": 1024,
            "indexerName": "idx",
            "downloadUrl": "https://example.com/sample.torrent",
        }
    ]


def _build_bot_data(
    *,
    cleanup_service: CleanupDownloadedSourceService | None = None,
) -> dict[str, object]:
    search_service = SearchMediaService(_fake_search)
    bot_data = {
        SEARCH_SERVICE_KEY: search_service,
        ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(search_service, AsyncMock()),
        GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
        IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies"),
    }
    if cleanup_service is not None:
        bot_data[CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY] = cleanup_service
    return bot_data


def test_dispatch_private_chat_text_routes_search_without_telegram_update() -> None:
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="dune",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(),
        )
    )

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "搜索结果：dune" in sent_text
    assert "title-dune" in sent_text


def test_dispatch_private_chat_text_routes_bt_prompt_without_telegram_update() -> None:
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="magnet:?xt=urn:btih:abcdef1234567890",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(),
        )
    )

    reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)


def test_dispatch_private_chat_text_replies_service_not_ready_when_bt_processing_path_persist_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
            raise RuntimeError("db down")

    database = _make_database(tmp_path)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="magnet:?xt=urn:btih:abcdef1234567890",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {BT_PENDING_REPO_KEY: _FailingPendingRepo(database)},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理持久化失败]" in captured.out
    assert "stage=processing_path" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_when_bt_processing_path_clear_fails_on_cancel(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            if expected_stage == "processing_path":
                raise RuntimeError("db down")
            return False

    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {
                BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:")),
                "bt_processing_path_pending_by_chat": {1001: "magnet:?xt=urn:btih:abcdef1234567890"},
            },
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理清理失败]" in captured.out
    assert "stage=processing_path" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_routes_personal_wechat_login_without_telegram_context(
    tmp_path: Path,
) -> None:
    async def start_login_func(*, api_base_url: str, force: bool = False) -> object:
        return SimpleNamespace(
            qrcode_url="https://wx.example/qrcode.png",
            session_key="session-1",
            message="ok",
        )

    async def wait_login_func(*, session_key: str, api_base_url: str, verbose: bool) -> object:
        return SimpleNamespace(
            connected=True,
            account_id="wx-account-runtime",
            bot_token="bot-token-runtime",
            base_url="https://ilinkai.weixin.qq.com",
            user_id="wx-user-runtime",
        )

    def build_qr_artifact(_: str) -> object:
        qr_dir = tmp_path / "runtime-login-qr"
        qr_dir.mkdir()
        file_path = qr_dir / "wechat-login.png"
        file_path.write_bytes(b"png")
        return SimpleNamespace(dir_path=qr_dir, file_path=file_path)

    service = PersonalWeChatLoginService(
        start_login_func=start_login_func,
        wait_login_func=wait_login_func,
        save_account_func=Mock(),
        register_account_func=Mock(),
        clear_stale_accounts_func=Mock(),
        close_client_func=AsyncMock(),
        qr_artifact_builder=build_qr_artifact,
    )
    reply_text = AsyncMock()
    send_media = AsyncMock(return_value="document-ok")
    send_text = AsyncMock(return_value="message-ok")
    bot_data = _build_bot_data()
    bot_data[TELEGRAM_SEND_MEDIA_FUNC_KEY] = send_media
    bot_data[TELEGRAM_SEND_TEXT_FUNC_KEY] = send_text
    bot_data[PERSONAL_WECHAT_LOGIN_SERVICE_KEY] = service

    asyncio.run(
        dispatch_private_chat_text(
            query="微信登录",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=bot_data,
        )
    )
    if service._wait_task is not None:
        asyncio.run(service._wait_task)

    reply_text.assert_awaited_once_with(PERSONAL_WECHAT_LOGIN_STARTED_TEXT)
    send_media.assert_awaited_once()
    send_text.assert_awaited_once_with(
        chat_id=1001,
        text="personal WeChat 登录成功。\n账号 ID: wx-account-runtime\n用户 ID: wx-user-runtime",
    )


def test_dispatch_private_chat_text_logs_pending_job_lookup_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    job_repo = JobRepo(_make_database(tmp_path))
    job_repo.get_latest_pending_job = Mock(side_effect=RuntimeError("sqlite busy"))  # type: ignore[method-assign]

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data={JOB_REPO_KEY: job_repo},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[待处理任务查询失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "sqlite busy" in captured.out
    assert "[处理建议]" in captured.out


def test_dispatch_private_chat_text_stops_on_pending_job_lookup_failure_even_with_services(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    bot_data = _build_bot_data()
    job_repo = JobRepo(_make_database(tmp_path))
    job_repo.get_latest_pending_job = Mock(side_effect=RuntimeError("sqlite busy"))  # type: ignore[method-assign]
    add_service = bot_data[ADD_TO_DOWNLOADER_SERVICE_KEY]
    import_service = bot_data[IMPORT_TO_LIBRARY_SERVICE_KEY]
    assert isinstance(add_service, AddToDownloaderService)
    assert isinstance(import_service, ImportToLibraryService)
    add_service.cancel_pending_add = Mock(return_value="已取消当前下载确认。请重新发送序号。")  # type: ignore[method-assign]
    import_service.cancel_pending_import = Mock(return_value="已取消当前导入确认。请重新发送 import <任务ID或Hash>。")  # type: ignore[method-assign]

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=bot_data | {JOB_REPO_KEY: job_repo},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    add_service.cancel_pending_add.assert_not_called()
    import_service.cancel_pending_import.assert_not_called()
    assert "[待处理任务查询失败]" in captured.out
    assert "sqlite busy" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_on_bt_processing_path_lookup_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def get_pending(self, *, chat_id: int):
            raise RuntimeError("db down")

    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="影视入库链",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理读取失败]" in captured.out
    assert "stage=processing_path" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_on_bt_processing_path_payload_corruption(
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = Path("/tmp/luminarr-bt-processing-payload-corruption.sqlite3")
    db_path.unlink(missing_ok=True)
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage="processing_path",
        payload_json="{",
    )

    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="影视入库链",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理载荷损坏]" in captured.out
    assert "stage=processing_path" in captured.out
    assert "payload_json invalid json" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_when_bt_processing_path_pop_clear_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            raise RuntimeError("db down")

    database = _make_database(tmp_path)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="影视入库链",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {
                BT_PENDING_REPO_KEY: _FailingPendingRepo(database),
                "bt_processing_path_pending_by_chat": {1001: "magnet:?xt=urn:btih:abcdef1234567890"},
            },
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理清理失败]" in captured.out
    assert "stage=processing_path" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_on_bt_classification_lookup_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def __init__(self, database: SqliteDatabase) -> None:
            super().__init__(database)
            self._calls = 0

        def get_pending(self, *, chat_id: int):
            self._calls += 1
            if self._calls == 1:
                return None
            raise RuntimeError("db down")

    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="movie",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理读取失败]" in captured.out
    assert "stage=classification" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_when_bt_classification_clear_fails_on_cancel(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            raise RuntimeError("db down")

    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {
                BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:")),
                "bt_classification_pending_by_chat": {1001: "magnet:?xt=urn:btih:abcdef1234567890"},
            },
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理清理失败]" in captured.out
    assert "stage=classification" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_on_bt_classification_payload_corruption(
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = Path("/tmp/luminarr-bt-classification-payload-corruption.sqlite3")
    db_path.unlink(missing_ok=True)
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage="classification",
        payload_json="{",
    )

    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="movie",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理载荷损坏]" in captured.out
    assert "stage=classification" in captured.out
    assert "payload_json invalid json" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_when_bt_classification_pop_clear_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            raise RuntimeError("db down")

    database = _make_database(tmp_path)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="movie",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {
                BT_PENDING_REPO_KEY: _FailingPendingRepo(database),
                "bt_classification_pending_by_chat": {1001: "magnet:?xt=urn:btih:abcdef1234567890"},
            },
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理清理失败]" in captured.out
    assert "stage=classification" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_on_bt_tmdb_lookup_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def __init__(self, database: SqliteDatabase) -> None:
            super().__init__(database)
            self._calls = 0

        def get_pending(self, *, chat_id: int):
            self._calls += 1
            if self._calls <= 2:
                return None
            raise RuntimeError("db down")

    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="movie",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理读取失败]" in captured.out
    assert "stage=tmdb_association" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_on_bt_tmdb_payload_corruption(
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = Path("/tmp/luminarr-bt-tmdb-payload-corruption.sqlite3")
    db_path.unlink(missing_ok=True)
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage="tmdb_association",
        payload_json="{",
    )

    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="movie",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理载荷损坏]" in captured.out
    assert "stage=tmdb_association" in captured.out
    assert "payload_json invalid json" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_on_raw_bt_destination_lookup_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def __init__(self, database: SqliteDatabase) -> None:
            super().__init__(database)
            self._calls = 0

        def get_pending(self, *, chat_id: int):
            self._calls += 1
            if self._calls <= 3:
                return None
            raise RuntimeError("db down")

    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="downloads",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理读取失败]" in captured.out
    assert "stage=raw_bt_destination" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_on_raw_bt_destination_payload_corruption(
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = Path("/tmp/luminarr-raw-bt-destination-payload-corruption.sqlite3")
    db_path.unlink(missing_ok=True)
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage="raw_bt_destination",
        payload_json="{",
    )

    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="downloads",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data()
            | {BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理载荷损坏]" in captured.out
    assert "stage=raw_bt_destination" in captured.out
    assert "payload_json invalid json" in captured.out


def test_dispatch_private_chat_text_stops_on_cached_candidate_lookup_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    search_service = SearchMediaService(
        _fake_search,
        candidate_repo=type("BoomRepo", (), {"get_candidate": lambda self, chat_id, index: (_ for _ in ()).throw(RuntimeError("db down"))})(),
    )

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data={SEARCH_SERVICE_KEY: search_service},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[搜索候选读取失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "index=1" in captured.out


def test_dispatch_private_chat_text_stops_on_clarification_lookup_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    search_service = SearchMediaService(
        _fake_search,
        clarification_repo=type(
            "BoomRepo",
            (),
            {"get_pending_query": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))},
        )(),
    )

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data={SEARCH_SERVICE_KEY: search_service},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[搜索澄清态读取失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_downloader_cancel_state_unavailable_without_job_repo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    add_service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search),
        add_torrent_func=AsyncMock(),
        job_repo=type(
            "BoomJobRepo",
            (),
            {"get_latest_pending_downloader_job": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))},
        )(),
    )

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data={ADD_TO_DOWNLOADER_SERVICE_KEY: add_service},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with("下载取消状态读取失败，请稍后重试。")
    assert "[下载取消查询失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_stops_on_pending_downloader_cancel_state_unavailable(
    tmp_path: Path,
) -> None:
    reply_text = AsyncMock()
    job_repo = JobRepo(_make_database(tmp_path))
    job_repo.upsert_downloader_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{}",
    )
    add_service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search),
        add_torrent_func=AsyncMock(),
    )
    add_service.cancel_pending_add = Mock(return_value=ADD_CANCEL_STATE_UNAVAILABLE_TEXT)  # type: ignore[method-assign]

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data={
                JOB_REPO_KEY: job_repo,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
            },
        )
    )

    add_service.cancel_pending_add.assert_called_once_with(1001)
    reply_text.assert_awaited_once_with(ADD_CANCEL_STATE_UNAVAILABLE_TEXT)


def test_dispatch_private_chat_text_replies_import_cancel_state_unavailable_without_job_repo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    import_service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        job_repo=type(
            "BoomJobRepo",
            (),
            {"get_latest_pending_import_job": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))},
        )(),
    )

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data={IMPORT_TO_LIBRARY_SERVICE_KEY: import_service},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with("导入取消状态读取失败，请稍后重试。")
    assert "[导入取消查询失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_on_clarification_clear_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    search_service = SearchMediaService(
        _fake_search,
        clarification_repo=type(
            "BoomRepo",
            (),
            {"clear_pending": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))},
        )(),
    )
    search_service._clarification_pending_by_chat[1001] = "dune"

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data={SEARCH_SERVICE_KEY: search_service},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[搜索澄清态清理失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_replies_service_not_ready_on_candidate_clear_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    search_service = SearchMediaService(
        _fake_search,
        candidate_repo=type(
            "BoomRepo",
            (),
            {"clear_candidates": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))},
        )(),
    )
    search_service._recent_candidates_by_chat[1001] = [{"title": "title-dune"}]

    asyncio.run(
        dispatch_private_chat_text(
            query="取消",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data={SEARCH_SERVICE_KEY: search_service},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[搜索候选清理失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_digit_stops_on_clarification_lookup_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    search_service = SearchMediaService(
        _fake_search,
        clarification_repo=type(
            "BoomRepo",
            (),
            {"get_pending_query": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))},
        )(),
    )

    asyncio.run(
        dispatch_private_chat_text(
            query="1",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data() | {SEARCH_SERVICE_KEY: search_service},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[搜索澄清态读取失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "db down" in captured.out


def test_dispatch_private_chat_text_logs_confirm_job_lookup_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    job_repo = JobRepo(_make_database(tmp_path))
    job_repo.get_job_for_chat_ref = Mock(side_effect=RuntimeError("disk i/o error"))  # type: ignore[method-assign]

    asyncio.run(
        dispatch_private_chat_text(
            query="confirm 87",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data={JOB_REPO_KEY: job_repo},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[确认关联任务查询失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "task_ref=87" in captured.out
    assert "disk i/o error" in captured.out
    assert "[处理建议]" in captured.out


def test_dispatch_private_chat_text_stops_on_confirm_job_lookup_failure_even_with_services(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    bot_data = _build_bot_data()
    job_repo = JobRepo(_make_database(tmp_path))
    job_repo.get_job_for_chat_ref = Mock(side_effect=RuntimeError("disk i/o error"))  # type: ignore[method-assign]
    add_service = bot_data[ADD_TO_DOWNLOADER_SERVICE_KEY]
    import_service = bot_data[IMPORT_TO_LIBRARY_SERVICE_KEY]
    assert isinstance(add_service, AddToDownloaderService)
    assert isinstance(import_service, ImportToLibraryService)
    add_service.has_pending_add = Mock(return_value=True)  # type: ignore[method-assign]
    add_service.confirm_add_by_task_ref = AsyncMock(return_value="下载确认成功")  # type: ignore[method-assign]
    import_service.confirm_import_by_task_ref = AsyncMock(return_value="导入确认成功")  # type: ignore[method-assign]

    asyncio.run(
        dispatch_private_chat_text(
            query="confirm 87",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=bot_data | {JOB_REPO_KEY: job_repo},
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    add_service.has_pending_add.assert_not_called()
    add_service.confirm_add_by_task_ref.assert_not_awaited()
    import_service.confirm_import_by_task_ref.assert_not_awaited()
    assert "[确认关联任务查询失败]" in captured.out
    assert "disk i/o error" in captured.out


def test_dispatch_private_chat_text_stops_on_downloader_pending_lookup_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    add_service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search),
        add_torrent_func=AsyncMock(),
        job_repo=type(
            "BoomJobRepo",
            (),
            {"get_downloader_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))},
        )(),
    )
    import_service = type("ImportService", (), {"confirm_import_by_task_ref": Mock()})()

    asyncio.run(
        dispatch_private_chat_text(
            query="confirm 1",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data={
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            },
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[下载待确认查询失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "task_ref=1" in captured.out
    import_service.confirm_import_by_task_ref.assert_not_called()  # type: ignore[attr-defined]


def test_dispatch_private_chat_text_routes_cleanup_inspect_without_telegram_update(
    tmp_path: Path,
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
    cleanup_service = CleanupDownloadedSourceService(event_repo)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="cleanup inspect 87",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "清理预检结果：" in sent_text
    assert "当前 guardrail: 允许 cleanup" in sent_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in sent_text
    assert source_file.exists()
    assert target_file.exists()


def test_dispatch_private_chat_text_routes_cleanup_inspect_in_chinese_without_telegram_update(
    tmp_path: Path,
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
    cleanup_service = CleanupDownloadedSourceService(event_repo)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="清理检查 87",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "清理预检结果：" in sent_text
    assert "当前 guardrail: 允许 cleanup" in sent_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in sent_text
    assert source_file.exists()
    assert target_file.exists()


def test_dispatch_private_chat_text_routes_cleanup_execution_without_telegram_update(
    tmp_path: Path,
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
    cleanup_service = CleanupDownloadedSourceService(event_repo)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="cleanup 87",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "已清理下载源资产" in sent_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in sent_text
    assert not source_file.exists()
    assert target_file.exists()


def test_dispatch_private_chat_text_routes_cleanup_execution_in_chinese_without_telegram_update(
    tmp_path: Path,
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
    cleanup_service = CleanupDownloadedSourceService(event_repo)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="清理 87",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "已清理下载源资产" in sent_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in sent_text
    assert not source_file.exists()
    assert target_file.exists()


def test_dispatch_private_chat_text_routes_bare_cleanup_usage_without_telegram_update(
    tmp_path: Path,
) -> None:
    reply_text = AsyncMock()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))

    asyncio.run(
        dispatch_private_chat_text(
            query="cleanup",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once_with(CLEANUP_QUERY_USAGE_TEXT)


def test_dispatch_private_chat_text_routes_bare_cleanup_inspect_usage_without_telegram_update(
    tmp_path: Path,
) -> None:
    reply_text = AsyncMock()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))

    asyncio.run(
        dispatch_private_chat_text(
            query="cleanup inspect",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once_with(CLEANUP_INSPECT_QUERY_USAGE_TEXT)


def test_dispatch_private_chat_text_routes_bare_cleanup_usage_in_chinese_without_telegram_update(
    tmp_path: Path,
) -> None:
    reply_text = AsyncMock()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))

    asyncio.run(
        dispatch_private_chat_text(
            query="清理",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once_with(CLEANUP_QUERY_USAGE_TEXT)


def test_dispatch_private_chat_text_routes_bare_cleanup_inspect_usage_in_chinese_without_telegram_update(
    tmp_path: Path,
) -> None:
    reply_text = AsyncMock()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))

    asyncio.run(
        dispatch_private_chat_text(
            query="清理检查",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once_with(CLEANUP_INSPECT_QUERY_USAGE_TEXT)


@pytest.mark.parametrize(
    ("query", "expected_action"),
    [
        ("cleanup hash-87", "cleanup"),
        ("cleanup inspect hash-87", "cleanup_inspect"),
        ("cleanup", "cleanup"),
        ("cleanup inspect", "cleanup_inspect"),
        ("清理", "cleanup"),
        ("清理检查", "cleanup_inspect"),
    ],
)
def test_dispatch_private_chat_text_logs_cleanup_service_not_ready_without_telegram_update(
    query: str,
    expected_action: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query=query,
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(),
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[cleanup 服务未就绪]" in captured.out
    assert f"动作={expected_action}" in captured.out
    assert query in captured.out
    assert "[处理建议]" in captured.out
    assert "cleanup_downloaded_source_service" in captured.out


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database
