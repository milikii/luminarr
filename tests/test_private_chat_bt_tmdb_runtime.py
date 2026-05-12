from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx

from app.bot import telegram_bot as tg
from app.bot.bt_tmdb_association_runtime import BtTmdbAssociationPending
from app.bot.private_chat_bt_tmdb_runtime import handle_bt_tmdb_follow_up
from app.clients.tmdb import TmdbMovie
from app.services.add_to_downloader import AddToDownloaderService
from app.services.search_media import SearchMediaService


async def _fake_search(_: str) -> list[dict[str, object]]:
    return []


def test_handle_bt_tmdb_follow_up_returns_false_without_pending() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_tmdb_follow_up(
            bot_data={},
            reply_func=reply_func,
            query="Dune 2021",
            chat_id=1001,
            user_id=2001,
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is False
    reply_func.assert_not_awaited()


def test_handle_bt_tmdb_follow_up_replies_service_not_ready_without_lookup() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_tmdb_follow_up(
            bot_data={
                "bt_tmdb_association_pending_by_chat": {
                    1001: BtTmdbAssociationPending(
                        media_kind="movie",
                        source="magnet:?xt=urn:btih:abcdef1234567890",
                    )
                }
            },
            reply_func=reply_func,
            query="Dune 2021",
            chat_id=1001,
            user_id=2001,
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is True
    reply_func.assert_awaited_once_with(tg.BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT)


def test_handle_bt_tmdb_follow_up_succeeds_for_movie() -> None:
    reply_func = AsyncMock()
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), AsyncMock())
    add_service.add_bt_source = AsyncMock(return_value="下载待确认")  # type: ignore[method-assign]

    async def fake_movie_lookup(title: str, year: str) -> list[TmdbMovie]:
        assert title == "Dune"
        assert year == "2021"
        return [TmdbMovie(title="Dune", original_title="Dune", year="2021", tmdb_id="438631")]

    handled = asyncio.run(
        handle_bt_tmdb_follow_up(
            bot_data={
                tg.ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                tg.BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY: fake_movie_lookup,
                "bt_tmdb_association_pending_by_chat": {
                    1001: BtTmdbAssociationPending(
                        media_kind="movie",
                        source="magnet:?xt=urn:btih:abcdef1234567890",
                    )
                },
            },
            reply_func=reply_func,
            query="Dune 2021",
            chat_id=1001,
            user_id=2001,
            resolve_downloader_execution=lambda: (
                SimpleNamespace(
                    name="bt",
                    downloader_type="transmission",
                    download_dir="/downloads/bt",
                ),
                None,
            ),
            tg=tg,
        )
    )

    assert handled is True
    sent_text = reply_func.await_args.args[0]
    assert "BT 电影 TMDB 关联成功。" in sent_text
    assert "TMDB ID: 438631" in sent_text
    assert "下载待确认" in sent_text


def test_handle_bt_tmdb_follow_up_replies_service_not_ready_on_http_failure() -> None:
    reply_func = AsyncMock()

    async def failing_movie_lookup(_: str, __: str) -> list[TmdbMovie]:
        request = httpx.Request("GET", "https://api.tmdb.org/3/search/movie")
        raise httpx.ConnectError("tmdb down", request=request)

    handled = asyncio.run(
        handle_bt_tmdb_follow_up(
            bot_data={
                tg.BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY: failing_movie_lookup,
                "bt_tmdb_association_pending_by_chat": {
                    1001: BtTmdbAssociationPending(
                        media_kind="movie",
                        source="magnet:?xt=urn:btih:abcdef1234567890",
                    )
                },
            },
            reply_func=reply_func,
            query="Dune 2021",
            chat_id=1001,
            user_id=2001,
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is True
    reply_func.assert_awaited_once_with(tg.BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT)
