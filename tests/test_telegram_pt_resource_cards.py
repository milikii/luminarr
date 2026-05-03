from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram import InlineKeyboardMarkup

from app.bot.telegram_update_runtime import build_telegram_reply_func
from app.services.telegram_pt_resource_cards import (
    TELEGRAM_PT_RESOURCE_CARD_REPLY_PREFIX,
    TELEGRAM_PT_RESOURCE_CARD_STALE_TEXT,
    TelegramPtResourceCardState,
    build_telegram_pt_resource_callback_data,
    build_telegram_pt_resource_reply_marker,
    parse_telegram_pt_resource_callback_data,
)


def _build_session(*, poster_url: str = "https://image.tmdb.org/t/p/w500/dune.jpg") -> TelegramPtResourceCardState:
    state = TelegramPtResourceCardState()
    state.create_session(
        chat_id=1001,
        title="Dune",
        original_title="Dune",
        year="2021",
        media_type="movie",
        poster_url=poster_url,
        overview="Paul Atreides leads the fight for Arrakis.",
        resource_items=(
            {
                "title": "Dune 2021 2160p WEB-DL",
                "quality": "4K WEB-DL",
                "size": 45 * 1024 * 1024 * 1024,
                "seeders": 88,
                "indexerName": "PTP",
                "downloadUrl": "https://example.com/dune-2021.torrent",
            },
            {
                "title": "Dune 2021 1080p BluRay",
                "quality": "1080p BluRay",
                "size": 28 * 1024 * 1024 * 1024,
                "seeders": 41,
                "indexerName": "HDB",
                "downloadUrl": "https://example.com/dune-2021-1080p.torrent",
            },
        ),
    )
    return state


def test_build_and_parse_pt_resource_callback_data_round_trip() -> None:
    state = _build_session()
    session = next(iter(state._sessions_by_token.values()))  # type: ignore[attr-defined]

    callback_data = build_telegram_pt_resource_callback_data(session.session_token, 1)

    assert len(callback_data.encode("utf-8")) < 64
    assert parse_telegram_pt_resource_callback_data(callback_data) == (session.session_token, 1)


def test_build_telegram_reply_func_sends_pt_resource_card_as_photo_caption_with_buttons() -> None:
    state = _build_session()
    session = next(iter(state._sessions_by_token.values()))  # type: ignore[attr-defined]
    reply_text = AsyncMock(return_value="fallback")
    send_text = AsyncMock(return_value="text-ok")
    sent_media: list[tuple[int, str, str | None, str | None, InlineKeyboardMarkup | None]] = []

    async def fake_send_media(
        chat_id: int,
        file_path: str | Path,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> object:
        resolved = Path(file_path)
        sent_media.append((chat_id, resolved.read_text(encoding="utf-8"), caption, parse_mode, reply_markup))
        return SimpleNamespace(message_id=321)

    async def fake_download_image(url: str) -> bytes:
        return f"downloaded:{url}".encode("utf-8")

    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=lambda value: value,
        chat_id=1001,
        send_text_func=send_text,
        send_media_func=fake_send_media,
        download_image_func=fake_download_image,
        telegram_pt_resource_card_state=state,
    )

    result = asyncio.run(reply_func(build_telegram_pt_resource_reply_marker(session.session_token)))

    assert result.message_id == 321
    reply_text.assert_not_called()
    send_text.assert_not_called()
    assert len(sent_media) == 1
    _, payload, caption, parse_mode, reply_markup = sent_media[0]
    assert payload == "downloaded:https://image.tmdb.org/t/p/w500/dune.jpg"
    assert parse_mode == "HTML"
    assert caption is not None and caption.startswith("🎬 <b>Dune (2021)</b>")
    assert "【资源 1】" in caption
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert tuple(tuple(button.text for button in row) for row in reply_markup.inline_keyboard) == (
        ("1 · 4K WEB-DL 45G", "2 · 1080p BluRay"),
    )
    for row in reply_markup.inline_keyboard:
        for button in row:
            assert len((button.callback_data or "").encode("utf-8")) < 64
    stored_session = state.get_session(session.session_token)
    assert stored_session is not None
    assert stored_session.message_id == 321


def test_build_telegram_reply_func_falls_back_to_text_for_pt_resource_card_without_poster() -> None:
    state = _build_session(poster_url="")
    session = next(iter(state._sessions_by_token.values()))  # type: ignore[attr-defined]
    reply_text = AsyncMock(return_value="fallback")
    send_text = AsyncMock(return_value=SimpleNamespace(message_id=654))

    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=lambda value: value,
        chat_id=1001,
        send_text_func=send_text,
        send_media_func=None,
        download_image_func=None,
        telegram_pt_resource_card_state=state,
    )

    result = asyncio.run(reply_func(build_telegram_pt_resource_reply_marker(session.session_token)))

    assert result.message_id == 654
    reply_text.assert_not_called()
    send_text.assert_awaited_once()
    kwargs = send_text.await_args.kwargs
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["text"].startswith("🎬 <b>Dune (2021)</b>")
    assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)


def test_pt_resource_card_state_marks_old_session_cancelled_when_new_one_created() -> None:
    state = _build_session()
    first_session = next(iter(state._sessions_by_token.values()))  # type: ignore[attr-defined]
    state.create_session(
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
            },
        ),
    )

    stale = state.consume_selection(
        session_token=first_session.session_token,
        chat_id=1001,
        selection_index=1,
    )

    assert stale.status == "cancelled"
    assert stale.rejection_text == TELEGRAM_PT_RESOURCE_CARD_STALE_TEXT
    assert stale.session is not None and stale.session.status == "cancelled"


def test_pt_resource_reply_marker_uses_expected_prefix() -> None:
    state = _build_session()
    session = next(iter(state._sessions_by_token.values()))  # type: ignore[attr-defined]

    marker = build_telegram_pt_resource_reply_marker(session.session_token)

    assert marker.startswith(TELEGRAM_PT_RESOURCE_CARD_REPLY_PREFIX)
