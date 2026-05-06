from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.bot import telegram_bot as tg
from app.services.add_to_downloader import AddToDownloaderService
from app.services.search_media import SearchMediaService
from app.services.telegram_pt_resource_cards import build_telegram_pt_resource_callback_data
from app.db.telegram_update_repo import TelegramUpdatePersistenceError
from app.bot.telegram_bot import TELEGRAM_UPDATE_REPO_KEY
from app.bot.telegram_runtime_adapter import handle_telegram_callback_query, handle_telegram_message
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdateRepo


def _build_update(
    text: str,
    *,
    caption: str | None = None,
    chat_id: int = 1001,
    user_id: int = 2001,
    update_id: int = 9001,
) -> tuple[SimpleNamespace, AsyncMock]:
    reply_text = AsyncMock()
    message = SimpleNamespace(text=text, caption=caption, reply_text=reply_text)
    update = SimpleNamespace(
        update_id=update_id,
        effective_message=message,
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(id=user_id),
    )
    return update, reply_text


def _build_callback_update(
    data: str,
    *,
    chat_id: int = 1001,
    user_id: int = 2001,
    callback_query_id: str = "cb-1",
    include_effective_context: bool = True,
) -> tuple[SimpleNamespace, AsyncMock, AsyncMock]:
    reply_text = AsyncMock()
    answer = AsyncMock()
    message = SimpleNamespace(text="origin", reply_text=reply_text, chat=SimpleNamespace(id=chat_id))
    callback_query = SimpleNamespace(
        id=callback_query_id,
        data=data,
        message=message,
        answer=answer,
        from_user=SimpleNamespace(id=user_id),
    )
    update = SimpleNamespace(
        callback_query=callback_query,
        effective_message=message if include_effective_context else None,
        effective_chat=SimpleNamespace(id=chat_id) if include_effective_context else None,
        effective_user=SimpleNamespace(id=user_id) if include_effective_context else None,
    )
    return update, reply_text, answer


async def _fake_search(_query: str) -> list[dict[str, object]]:
    return []


class _ExecutionGateStub:
    def __init__(self) -> None:
        self.run = AsyncMock(side_effect=self._run)

    async def _run(self, _action: str, handler):
        result = handler()
        if asyncio.iscoroutine(result):
            return await result
        return result


def test_handle_telegram_message_routes_through_dispatch_private_chat_text(monkeypatch) -> None:
    update, _ = _build_update("dune")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"key": "value"}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_message(update, context))

    dispatch_private_chat_text.assert_awaited_once()
    kwargs = dispatch_private_chat_text.await_args.kwargs
    assert kwargs["query"] == "dune"
    assert kwargs["chat_id"] == 1001
    assert kwargs["user_id"] == 2001
    assert kwargs["bot_data"] is context.application.bot_data
    assert callable(kwargs["reply_func"])


def test_handle_telegram_message_uses_caption_when_text_missing(monkeypatch) -> None:
    update, _ = _build_update("", caption="magnet:?xt=urn:btih:abcdef1234567890")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"key": "value"}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_message(update, context))

    dispatch_private_chat_text.assert_awaited_once()
    kwargs = dispatch_private_chat_text.await_args.kwargs
    assert kwargs["query"] == "magnet:?xt=urn:btih:abcdef1234567890"


def test_handle_telegram_message_skips_when_text_and_caption_missing(monkeypatch) -> None:
    update, _ = _build_update("", caption="")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"key": "value"}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_message(update, context))

    dispatch_private_chat_text.assert_not_awaited()


def test_handle_telegram_callback_query_routes_through_dispatch_private_chat_text(monkeypatch) -> None:
    update, _, answer = _build_callback_update("confirm 87")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"key": "value"}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_awaited_once()
    dispatch_private_chat_text.assert_awaited_once()
    kwargs = dispatch_private_chat_text.await_args.kwargs
    assert kwargs["query"] == "confirm 87"
    assert kwargs["chat_id"] == 1001
    assert kwargs["user_id"] == 2001
    assert kwargs["bot_data"] is context.application.bot_data
    assert callable(kwargs["reply_func"])


def test_handle_telegram_callback_query_forwards_callback_data_unchanged(monkeypatch) -> None:
    update, _, answer = _build_callback_update("status hash-87")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"key": "value"}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_awaited_once()
    dispatch_private_chat_text.assert_awaited_once()
    assert dispatch_private_chat_text.await_args.kwargs["query"] == "status hash-87"


def test_handle_telegram_callback_query_consumes_pt_resource_card_without_shared_dispatch(monkeypatch) -> None:
    search_service = SearchMediaService(_fake_search)
    session = search_service.telegram_pt_resource_card_state.create_session(
        chat_id=1001,
        title="Dune",
        original_title="Dune",
        year="2021",
        media_type="movie",
        poster_url="https://image.tmdb.org/t/p/w500/dune.jpg",
        overview="Paul Atreides leads the fight for Arrakis.",
        resource_items=(
            {
                "title": "Dune 2021 2160p WEB-DL",
                "quality": "4K WEB-DL",
                "size": 45 * 1024 * 1024 * 1024,
                "seeders": 88,
                "indexerName": "PTP",
                "downloadUrl": "https://example.com/dune-2021.torrent",
                "media_identity": {
                    "title": "Dune",
                    "year": "2021",
                    "tmdb_id": "438631",
                    "media_type": "movie",
                },
            },
        ),
    )
    search_service._recent_candidates_by_chat[1001] = [  # type: ignore[attr-defined]
        {
            "title": "WRONG",
            "downloadUrl": "https://example.com/wrong.torrent",
        }
    ]
    add_service = AddToDownloaderService(search_service, AsyncMock())
    add_service.add_by_candidate_with_auto_confirm = AsyncMock(  # type: ignore[method-assign]
        return_value="已添加下载：Dune 2021 2160p WEB-DL\n任务 ID: 42\n任务 Hash: abc123"
    )
    execution_gate = _ExecutionGateStub()
    update, reply_text, answer = _build_callback_update(
        build_telegram_pt_resource_callback_data(session.session_token, 1)
    )
    edit_message_reply_markup = AsyncMock()
    update.callback_query.edit_message_reply_markup = edit_message_reply_markup
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                tg.SEARCH_SERVICE_KEY: search_service,
                tg.ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                tg.EXECUTION_GATE_KEY: execution_gate,
            }
        )
    )
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)
    monkeypatch.setattr("app.bot.telegram_runtime_adapter.resolve_execution_gate", lambda **_: execution_gate)

    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_awaited_once()
    dispatch_private_chat_text.assert_not_awaited()
    execution_gate.run.assert_awaited_once()
    add_service.add_by_candidate_with_auto_confirm.assert_awaited_once()
    kwargs = add_service.add_by_candidate_with_auto_confirm.await_args.kwargs
    assert kwargs["candidate"]["title"] == "Dune 2021 2160p WEB-DL"
    assert kwargs["task_ref"].startswith("pt-")
    edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "┏━ ✅ <b>下载已开始</b>" in sent_text
    assert "<code>42</code>" in sent_text
    assert "<code>abc123</code>" in sent_text
    assert "<code>status abc123</code>" in sent_text
    assert "下一阶段会在这里接入实时进度同步" in sent_text
    assert "不展示伪实时进度" in sent_text
    assert "confirm " not in sent_text
    stored_session = search_service.telegram_pt_resource_card_state.get_session(session.session_token)
    assert stored_session is not None
    assert stored_session.status == "selected"


def test_handle_telegram_callback_query_rejects_cancelled_pt_resource_card(monkeypatch) -> None:
    search_service = SearchMediaService(_fake_search)
    stale_session = search_service.telegram_pt_resource_card_state.create_session(
        chat_id=1001,
        title="Dune",
        original_title="Dune",
        year="2021",
        media_type="movie",
        poster_url="https://image.tmdb.org/t/p/w500/dune.jpg",
        overview="Paul Atreides leads the fight for Arrakis.",
        resource_items=(
            {
                "title": "Dune 2021 2160p WEB-DL",
                "quality": "4K WEB-DL",
                "size": 45 * 1024 * 1024 * 1024,
                "seeders": 88,
                "indexerName": "PTP",
                "downloadUrl": "https://example.com/dune-2021.torrent",
                "media_identity": {
                    "title": "Dune",
                    "year": "2021",
                    "tmdb_id": "438631",
                    "media_type": "movie",
                },
            },
        ),
    )
    search_service.telegram_pt_resource_card_state.create_session(
        chat_id=1001,
        title="Dune Messiah",
        original_title="Dune Messiah",
        year="2027",
        media_type="movie",
        poster_url="",
        overview="A newer search invalidates the old card.",
        resource_items=(
            {
                "title": "Dune Messiah 2027 1080p WEB-DL",
                "quality": "1080p WEB-DL",
                "size": 12 * 1024 * 1024 * 1024,
                "seeders": 55,
                "indexerName": "HDB",
                "downloadUrl": "https://example.com/dune-messiah.torrent",
                "media_identity": {
                    "title": "Dune Messiah",
                    "year": "2027",
                    "tmdb_id": "999",
                    "media_type": "movie",
                },
            },
        ),
    )
    add_service = AddToDownloaderService(search_service, AsyncMock())
    add_service.add_by_candidate = AsyncMock(return_value="不该被调用")  # type: ignore[method-assign]
    update, reply_text, answer = _build_callback_update(
        build_telegram_pt_resource_callback_data(stale_session.session_token, 1)
    )
    edit_message_reply_markup = AsyncMock()
    update.callback_query.edit_message_reply_markup = edit_message_reply_markup
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                tg.SEARCH_SERVICE_KEY: search_service,
                tg.ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                tg.EXECUTION_GATE_KEY: _ExecutionGateStub(),
            }
        )
    )
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)
    monkeypatch.setattr("app.bot.telegram_runtime_adapter.resolve_execution_gate", lambda **_: _ExecutionGateStub())

    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_awaited_once()
    dispatch_private_chat_text.assert_not_awaited()
    add_service.add_by_candidate.assert_not_called()
    edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
    reply_text.assert_awaited_once()
    assert "已失效" in reply_text.await_args.args[0]


def test_handle_telegram_message_deduplicates_update(tmp_path, monkeypatch) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)
    update, _ = _build_update("dune", update_id=9001)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_message(update, context))
    asyncio.run(handle_telegram_message(update, context))

    dispatch_private_chat_text.assert_awaited_once()


def test_handle_telegram_callback_query_deduplicates_update(tmp_path, monkeypatch) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)
    update, _, answer = _build_callback_update("dune", callback_query_id="cb-9001")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_callback_query(update, context))
    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_awaited_once()
    dispatch_private_chat_text.assert_awaited_once()


def test_handle_telegram_message_stops_when_update_dedup_persist_fails(tmp_path, capsys, monkeypatch) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    def _crash_record_message_update(**_: object) -> bool:
        raise TelegramUpdatePersistenceError("db down")

    update_repo.record_message_update = _crash_record_message_update  # type: ignore[method-assign]
    update, _ = _build_update("dune", update_id=9002)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_message(update, context))

    dispatch_private_chat_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重落盘失败]" in output
    assert "source_type=message" in output
    assert "source_id=9002" in output
    assert "[处理建议]" in output


def test_handle_telegram_message_stops_when_update_dedup_result_missing(tmp_path, capsys, monkeypatch) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    def _missing_record_message_update(**_: object) -> None:
        return None

    update_repo.record_message_update = _missing_record_message_update  # type: ignore[method-assign]
    update, _ = _build_update("dune", update_id=9003)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_message(update, context))

    dispatch_private_chat_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重结果缺失]" in output
    assert "source_type=message" in output
    assert "source_id=9003" in output
    assert "telegram update record result missing" in output
    assert "[处理建议]" in output


def test_handle_telegram_callback_query_stops_when_update_dedup_persist_fails(tmp_path, capsys, monkeypatch) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    def _crash_record_callback_update(**_: object) -> bool:
        raise TelegramUpdatePersistenceError("db down")

    update_repo.record_callback_update = _crash_record_callback_update  # type: ignore[method-assign]
    update, _, answer = _build_callback_update("dune", callback_query_id="cb-9002")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_not_awaited()
    dispatch_private_chat_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重落盘失败]" in output
    assert "source_type=callback" in output
    assert "source_id=cb-9002" in output
    assert "[处理建议]" in output


def test_handle_telegram_callback_query_stops_when_update_dedup_result_missing(tmp_path, capsys, monkeypatch) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    def _missing_record_callback_update(**_: object) -> None:
        return None

    update_repo.record_callback_update = _missing_record_callback_update  # type: ignore[method-assign]
    update, _, answer = _build_callback_update("dune", callback_query_id="cb-9003")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_not_awaited()
    dispatch_private_chat_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重结果缺失]" in output
    assert "source_type=callback" in output
    assert "source_id=cb-9003" in output
    assert "telegram update record result missing" in output
    assert "[处理建议]" in output


def test_handle_telegram_message_stops_when_update_id_invalid(tmp_path, capsys, monkeypatch) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)
    update, _ = _build_update("dune", update_id=0)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_message(update, context))

    dispatch_private_chat_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重落盘失败]" in output
    assert "source_type=message" in output
    assert "source_id=0" in output
    assert "message update_id missing or invalid" in output


def test_handle_telegram_callback_query_stops_when_callback_id_missing(tmp_path, capsys, monkeypatch) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)
    update, _, answer = _build_callback_update("dune", callback_query_id="")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.handle_private_chat_query_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_not_awaited()
    dispatch_private_chat_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重落盘失败]" in output
    assert "source_type=callback" in output
    assert "source_id=-" in output
    assert "callback_query_id missing" in output
