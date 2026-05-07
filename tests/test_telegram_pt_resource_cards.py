from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram import InlineKeyboardMarkup

from app.bot.telegram_update_runtime import build_telegram_reply_func
from app.services.search_request_context import PARTIAL_SEARCH_SOURCE_HINT_TEXT
from app.services.telegram_pt_resource_cards import (
    TELEGRAM_PT_RESOURCE_CARD_REPLY_PREFIX,
    TELEGRAM_PT_RESOURCE_CARD_STALE_TEXT,
    TelegramPtResourceCardState,
    build_telegram_pt_resource_callback_data,
    build_telegram_pt_resource_reply_marker,
    parse_telegram_pt_resource_callback_data,
)


def _build_session(
    *,
    poster_url: str = "https://image.tmdb.org/t/p/w500/dune.jpg",
    partial_failure_hint: str = "",
) -> TelegramPtResourceCardState:
    state = TelegramPtResourceCardState()
    state.create_session(
        chat_id=1001,
        title="Dune",
        original_title="Dune",
        year="2021",
        media_type="movie",
        poster_url=poster_url,
        overview="Paul Atreides leads the fight for Arrakis.",
        partial_failure_hint=partial_failure_hint,
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


def _build_large_session(*, poster_url: str = "https://image.tmdb.org/t/p/w500/dune.jpg") -> TelegramPtResourceCardState:
    state = TelegramPtResourceCardState()
    state.create_session(
        chat_id=1001,
        title="Dune",
        original_title="Dune",
        year="2021",
        media_type="movie",
        poster_url=poster_url,
        overview="Paul Atreides leads the fight for Arrakis and navigates multiple PT releases.",
        resource_items=(
            {
                "title": "Dune 2021 2160p WEB-DL PTP",
                "quality": "2160p WEB-DL",
                "size": 45 * 1024 * 1024 * 1024,
                "seeders": 88,
                "indexerName": "PTP",
                "downloadUrl": "https://example.com/dune-ptp-2160p.torrent",
            },
            {
                "title": "Dune 2021 1440p WEB-DL PTP",
                "quality": "1440p WEB-DL",
                "size": 32 * 1024 * 1024 * 1024,
                "seeders": 61,
                "indexerName": "PTP",
                "downloadUrl": "https://example.com/dune-ptp-1440p.torrent",
            },
            {
                "title": "Dune 2021 1080p WEB-DL PTP",
                "quality": "1080p WEB-DL",
                "size": 18 * 1024 * 1024 * 1024,
                "seeders": 57,
                "indexerName": "PTP",
                "downloadUrl": "https://example.com/dune-ptp-1080p.torrent",
            },
            {
                "title": "Dune 2021 2160p BluRay HDB",
                "quality": "2160p BluRay",
                "size": 56 * 1024 * 1024 * 1024,
                "seeders": 43,
                "indexerName": "HDB",
                "downloadUrl": "https://example.com/dune-hdb-2160p.torrent",
            },
            {
                "title": "Dune 2021 1440p BluRay HDB",
                "quality": "1440p BluRay",
                "size": 34 * 1024 * 1024 * 1024,
                "seeders": 35,
                "indexerName": "HDB",
                "downloadUrl": "https://example.com/dune-hdb-1440p.torrent",
            },
            {
                "title": "Dune 2021 1080p BluRay HDB",
                "quality": "1080p BluRay",
                "size": 22 * 1024 * 1024 * 1024,
                "seeders": 29,
                "indexerName": "HDB",
                "downloadUrl": "https://example.com/dune-hdb-1080p.torrent",
            },
            {
                "title": "Dune 2021 2160p WEB-DL BHD",
                "quality": "2160p WEB-DL",
                "size": 47 * 1024 * 1024 * 1024,
                "seeders": 22,
                "indexerName": "BHD",
                "downloadUrl": "https://example.com/dune-bhd-2160p.torrent",
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
    send_text = AsyncMock(return_value=SimpleNamespace(message_id=654))
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
    assert len(sent_media) == 1
    _, payload, caption, parse_mode, reply_markup = sent_media[0]
    assert payload == "downloaded:https://image.tmdb.org/t/p/w500/dune.jpg"
    assert parse_mode == "HTML"
    assert caption is not None and caption.startswith("🎬 <b>Dune (2021)</b>")
    assert "【资源 1】" not in caption
    assert "点下方按钮" in caption
    assert "详见下一条消息" in caption
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert tuple(tuple(button.text for button in row) for row in reply_markup.inline_keyboard) == (
        ("1 · 4K WEB-DL 45G", "2 · 1080p BluRay"),
    )
    send_text.assert_awaited_once()
    detail_kwargs = send_text.await_args.kwargs
    assert detail_kwargs["chat_id"] == 1001
    assert detail_kwargs["parse_mode"] == "HTML"
    assert "🧾 <b>PT 资源详情</b>" in detail_kwargs["text"]
    assert "<b>PTP</b>" in detail_kwargs["text"]
    assert "<b>HDB</b>" in detail_kwargs["text"]
    for row in reply_markup.inline_keyboard:
        for button in row:
            assert len((button.callback_data or "").encode("utf-8")) < 64
    stored_session = state.get_session(session.session_token)
    assert stored_session is not None
    assert stored_session.message_id == 321


def test_build_telegram_reply_func_sends_short_pt_caption_then_detail_message_with_matching_buttons() -> None:
    state = _build_large_session()
    session = next(iter(state._sessions_by_token.values()))  # type: ignore[attr-defined]
    reply_text = AsyncMock(return_value="fallback")
    send_text = AsyncMock(side_effect=[SimpleNamespace(message_id=654)])
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
    assert len(sent_media) == 1
    _, payload, caption, parse_mode, reply_markup = sent_media[0]
    assert payload == "downloaded:https://image.tmdb.org/t/p/w500/dune.jpg"
    assert parse_mode == "HTML"
    assert caption is not None and caption.startswith("🎬 <b>Dune (2021)</b>")
    assert "【资源 1】" not in caption
    assert "PTP" not in caption
    assert "点下方按钮" in caption
    assert "详见下一条消息" in caption
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert tuple(tuple(button.text for button in row) for row in reply_markup.inline_keyboard) == (
        ("1 · 2160p WEB-DL", "2 · 1440p WEB-DL"),
        ("3 · 1080p WEB-DL", "4 · 2160p BluRay"),
        ("5 · 1440p BluRay", "6 · 1080p BluRay"),
        ("7 · 2160p WEB-DL",),
    )
    assert send_text.await_count == 1
    detail_kwargs = send_text.await_args.kwargs
    assert detail_kwargs["chat_id"] == 1001
    assert detail_kwargs["parse_mode"] == "HTML"
    detail_text = detail_kwargs["text"]
    assert detail_text.startswith("🧾 <b>PT 资源详情</b>")
    assert "<b>PTP</b>" in detail_text
    assert "<b>HDB</b>" in detail_text
    assert "<b>BHD</b>" in detail_text
    assert "【1】" in detail_text
    assert "【7】" in detail_text
    assert "2160p WEB-DL" in detail_text
    assert "1440p WEB-DL" in detail_text
    assert "1080p BluRay" in detail_text
    assert len(detail_text) <= 4096


def test_build_telegram_reply_func_includes_partial_timeout_hint_in_detail_message() -> None:
    state = _build_session(partial_failure_hint=PARTIAL_SEARCH_SOURCE_HINT_TEXT)
    session = next(iter(state._sessions_by_token.values()))  # type: ignore[attr-defined]
    reply_text = AsyncMock(return_value="fallback")
    send_text = AsyncMock(return_value=SimpleNamespace(message_id=654))
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

    asyncio.run(reply_func(build_telegram_pt_resource_reply_marker(session.session_token)))

    detail_kwargs = send_text.await_args.kwargs
    assert f"⚠️ {PARTIAL_SEARCH_SOURCE_HINT_TEXT}" in detail_kwargs["text"]


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
    assert send_text.await_count == 2
    first_kwargs = send_text.await_args_list[0].kwargs
    assert first_kwargs["parse_mode"] == "HTML"
    assert first_kwargs["text"].startswith("🎬 <b>Dune (2021)</b>")
    assert isinstance(first_kwargs["reply_markup"], InlineKeyboardMarkup)
    second_kwargs = send_text.await_args_list[1].kwargs
    assert second_kwargs["parse_mode"] == "HTML"
    assert second_kwargs["text"].startswith("🧾 <b>PT 资源详情</b>")


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
