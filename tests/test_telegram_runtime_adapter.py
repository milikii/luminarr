from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.bot.telegram_bot import TELEGRAM_UPDATE_REPO_KEY
from app.bot.telegram_runtime_adapter import handle_telegram_callback_query, handle_telegram_message
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdateRepo


def _build_update(
    text: str,
    *,
    chat_id: int = 1001,
    user_id: int = 2001,
    update_id: int = 9001,
) -> tuple[SimpleNamespace, AsyncMock]:
    reply_text = AsyncMock()
    message = SimpleNamespace(text=text, reply_text=reply_text)
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


def test_handle_telegram_message_routes_through_dispatch_private_chat_text(monkeypatch) -> None:
    update, _ = _build_update("dune")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"key": "value"}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_message(update, context))

    dispatch_private_chat_text.assert_awaited_once()
    kwargs = dispatch_private_chat_text.await_args.kwargs
    assert kwargs["query"] == "dune"
    assert kwargs["chat_id"] == 1001
    assert kwargs["user_id"] == 2001
    assert kwargs["bot_data"] is context.application.bot_data
    assert callable(kwargs["reply_func"])


def test_handle_telegram_callback_query_routes_through_dispatch_private_chat_text(monkeypatch) -> None:
    update, _, answer = _build_callback_update("confirm 87")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"key": "value"}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_awaited_once()
    dispatch_private_chat_text.assert_awaited_once()
    kwargs = dispatch_private_chat_text.await_args.kwargs
    assert kwargs["query"] == "confirm 87"
    assert kwargs["chat_id"] == 1001
    assert kwargs["user_id"] == 2001
    assert kwargs["bot_data"] is context.application.bot_data
    assert callable(kwargs["reply_func"])


def test_handle_telegram_message_deduplicates_update(tmp_path, monkeypatch) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)
    update, _ = _build_update("dune", update_id=9001)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

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
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_callback_query(update, context))
    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_awaited_once()
    dispatch_private_chat_text.assert_awaited_once()


def test_handle_telegram_message_stops_when_update_dedup_persist_fails(tmp_path, capsys, monkeypatch) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    def _crash_record_message_update(**_: object) -> bool:
        raise RuntimeError("db down")

    update_repo.record_message_update = _crash_record_message_update  # type: ignore[method-assign]
    update, _ = _build_update("dune", update_id=9002)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

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
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

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
        raise RuntimeError("db down")

    update_repo.record_callback_update = _crash_record_callback_update  # type: ignore[method-assign]
    update, _, answer = _build_callback_update("dune", callback_query_id="cb-9002")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={TELEGRAM_UPDATE_REPO_KEY: update_repo}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

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
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

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
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

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
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

    asyncio.run(handle_telegram_callback_query(update, context))

    answer.assert_not_awaited()
    dispatch_private_chat_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重落盘失败]" in output
    assert "source_type=callback" in output
    assert "source_id=-" in output
    assert "callback_query_id missing" in output
