import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from telegram import InlineKeyboardMarkup

from app.clients.tmdb import TmdbMovie
from app.bot.telegram_update_runtime import build_telegram_reply_func
from app.bot.telegram_reply_formatter import format_telegram_reply
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_telegram_text
from app.services.search_query_parser import ParsedMovieQuery
from app.services.search_reply_formatter import (
    build_media_candidate_confirmation_delivery_item,
    format_adult_bt_resource_fallback_reply,
)


def test_format_telegram_reply_formats_search_result() -> None:
    text = (
        "电影海报卡片\n"
        "片名：Dune\n"
        "年份：2021\n\n"
        "搜索结果：dune 2021\n"
        "1. Dune (2021)\n"
        "2. Dune: Part Two (2024)"
    )

    formatted = format_telegram_reply(text)

    assert formatted == (
        "【电影卡片】\n"
        "片名：Dune\n"
        "年份：2021\n\n"
        "【搜索结果】 dune 2021\n"
        "1. Dune (2021)\n"
        "2. Dune: Part Two (2024)\n\n"
        "直接回复 1-2 中的序号继续，例如：1"
    )


def test_format_telegram_reply_formats_adult_bt_resource_result() -> None:
    text = (
        "成人资源候选：SSIS-123\n"
        "1. SSIS-123 Sample Title\n"
        "   站点: tokyotosho | 来源入口: tokyotosho | 做种: 12 | 大小: 2.0 GB\n"
        "   番号: SSIS-123 | 分类: censored\n"
        "   海报: https://img.example/ssis-123.jpg\n"
        "   标准信息: 标题: SSIS-123 Sample Title | 发行日: 2026-01-02 | 时长: 120 分钟\n"
        "   制作信息: 制作商: Prestige | 演员: Actor A, Actor B\n"
        "   Metadata源: avmoo | 角色: primary\n"
        "   磁力链接: magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12&dn=ssis-123\n"
        "   链接参考: magnet | infoHash=abcdef1234567890abcdef1234567890abcdef12\n"
        "只读说明：以上为当前已配置成人源返回的资源候选，不会创建审批或下载任务。\n"
        "如需走成人下载链，请直接发送磁力并选择 BT 成人链。"
    )

    formatted = format_telegram_reply(text)

    assert formatted.startswith("【成人资源候选】 SSIS-123\n海报: https://img.example/ssis-123.jpg")
    assert "🎬 <b>[SSIS-123] Sample Title</b>" in formatted
    assert "海报: https://img.example/ssis-123.jpg" in formatted
    assert "📅 <b>日期：</b> 2026-01-02  |  ⏳ <b>时长：</b> 120 分钟" in formatted
    assert "🏢 <b>片商：</b> Prestige" in formatted
    assert "👤 <b>演员：</b> Actor A, Actor B" in formatted
    assert "📦 <b>分类：</b> 有码 (Censored)" in formatted
    assert "<b>【资源 1】 tokyotosho | 2.0 GB | 做种: 12</b>" in formatted
    assert "<code>magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12</code>" in formatted
    assert "&amp;dn=ssis-123" not in formatted
    assert "链接参考:" not in formatted
    assert "➡️ 下一步：发送 magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12" in formatted


def test_format_telegram_reply_formats_add_approval() -> None:
    text = "下载待确认：Frieren S01E01 1080p\n选择序号: hash-1\n请发送 confirm hash-1 执行下载。"

    formatted = format_telegram_reply(text)

    assert formatted == (
        "【下载审批】\n"
        "标题: Frieren S01E01 1080p\n"
        "选择序号: hash-1\n"
        "确认命令: confirm hash-1\n\n"
        "直接回复 confirm hash-1 执行下载"
    )


def test_format_telegram_reply_formats_import_approval() -> None:
    text = (
        "导入待确认：Dune (2021).mkv\n"
        "任务 ID: 87\n"
        "任务 Hash: hash-87\n"
        "请发送 confirm hash-87 执行导入。"
    )

    formatted = format_telegram_reply(text)

    assert formatted == (
        "【导入审批】\n"
        "资源: Dune (2021).mkv\n"
        "任务 ID: 87\n"
        "任务 Hash: hash-87\n"
        "确认命令: confirm hash-87\n\n"
        "下一步\n"
        "确认导入：发送 confirm hash-87"
    )


def test_format_telegram_reply_formats_adult_resource_candidates_with_copyable_links() -> None:
    magnet = "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12&dn=SSIS-123"
    text = format_adult_bt_resource_fallback_reply(
        "SSIS-123",
        (
            {
                "title": "SSIS-123 Secret Mission Nurse",
                "source": magnet,
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
                "adult_display_id": "SSIS-123",
                "adult_archive_category": "censored",
                "read_only_adult_source_site": "javlibrary",
                "read_only_adult_title": "SSIS-123 Secret Mission Nurse",
                "read_only_adult_detail_url": "https://www.javlibrary.com/tw/?v=javli0001",
                "read_only_adult_poster_url": "https://img.example/ssis-123.jpg",
                "read_only_adult_release_date": "2026-04-01",
                "read_only_adult_actors": ("Aki", "Mei"),
                "read_only_adult_studio": "S1",
                "read_only_adult_series": "Secret Mission",
            },
        ),
    )

    formatted = format_telegram_reply(text)

    assert formatted.startswith("【成人资源候选】 SSIS-123")
    assert "🎬 <b>[SSIS-123] Secret Mission Nurse</b>" in formatted
    assert "📦 <b>分类：</b> 有码 (Censored)" in formatted
    assert "海报: https://img.example/ssis-123.jpg" in formatted
    assert "📅 <b>日期：</b> 2026-04-01" in formatted
    assert "👤 <b>演员：</b> Aki / Mei" in formatted
    assert "🏢 <b>片商：</b> S1" in formatted
    assert "🏷 <b>系列：</b> Secret Mission" in formatted
    assert "<code>magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12</code>" in formatted
    assert "&amp;dn=SSIS-123" not in formatted
    assert "🌐 查看详情 (javlibrary)：打开 https://www.javlibrary.com/tw/?v=javli0001" in formatted
    assert "链接参考: magnet | infoHash" not in formatted


def test_format_telegram_reply_preserves_avmoo_primary_adult_metadata() -> None:
    magnet = "magnet:?xt=urn:btih:1111111111111111111111111111111111111111&dn=SSIS-483"
    text = format_adult_bt_resource_fallback_reply(
        "SSIS-483",
        (
            {
                "title": "SSIS-483 Detail Title",
                "source": magnet,
                "infoHash": "1111111111111111111111111111111111111111",
                "seeders": 10,
                "size": 3 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
                "read_only_adult_source_site": "avmoo.shop",
                "read_only_adult_display_id": "SSIS-483",
                "read_only_adult_archive_category": "censored",
                "read_only_adult_title": "SSIS-483 Detail Title",
                "read_only_adult_detail_url": "https://avmoo.shop/cn/movie/4221ec1035fdf66f",
                "read_only_adult_poster_url": "https://jp.netcdn.space/digital/video/ssis00483/ssis00483pl.jpg",
                "read_only_adult_release_date": "2023-05-01",
                "read_only_adult_runtime": "120分钟",
                "read_only_adult_maker": "S1",
                "read_only_adult_label": "S1 Label",
                "read_only_adult_series": "Secret Mission",
                "read_only_adult_actors": ("Aki", "Mei"),
            },
        ),
    )

    formatted = format_telegram_reply(text)

    assert formatted.startswith("【成人资源候选】 SSIS-483")
    assert "🎬 <b>[SSIS-483] Detail Title</b>" in formatted
    assert "📦 <b>分类：</b> 有码 (Censored)" in formatted
    assert "海报: https://jp.netcdn.space/digital/video/ssis00483/ssis00483pl.jpg" in formatted
    assert "📅 <b>日期：</b> 2023-05-01  |  ⏳ <b>时长：</b> 120分钟" in formatted
    assert "🏢 <b>片商：</b> S1" in formatted
    assert "🏷 <b>系列：</b> Secret Mission" in formatted
    assert "👤 <b>演员：</b> Aki / Mei" in formatted
    assert "<code>magnet:?xt=urn:btih:1111111111111111111111111111111111111111</code>" in formatted
    assert "&amp;dn=SSIS-483" not in formatted
    assert "🌐 查看详情 (avmoo)：打开 https://avmoo.shop/cn/movie/4221ec1035fdf66f" in formatted
    assert "链接参考: magnet | infoHash" not in formatted


def test_format_telegram_reply_renders_adult_bt_as_poster_caption_card() -> None:
    long_magnet = (
        "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12"
        "&dn=SSIS-483&tr=https%3A%2F%2Ftracker.example%2Fannounce"
    )
    text = format_adult_bt_resource_fallback_reply(
        "SSIS-483",
        (
            {
                "title": "SSIS-483 resource title",
                "source": long_magnet,
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 3,
                "size": 3_328_599_654,
                "indexerName": "sukebei",
                "sourceProvider": "sukebei",
                "read_only_adult_source_site": "avmoo.shop",
                "read_only_adult_display_id": "SSIS-483",
                "read_only_adult_archive_category": "censored",
                "read_only_adult_title": "シン・交わる体液、濃密セックス 完全ノーカット5本番",
                "read_only_adult_detail_url": "https://avmoo.shop/cn/movie/4221ec1035fdf66f",
                "read_only_adult_poster_url": "https://jp.netcdn.space/digital/video/ssis00483/ssis00483pl.jpg",
                "read_only_adult_release_date": "2022-08-05",
                "read_only_adult_runtime": "220 分钟",
                "read_only_adult_maker": "S1 NO.1 STYLE",
                "read_only_adult_series": "交融的体液、浓密性爱",
                "read_only_adult_actors": ("七ツ森りり",),
            },
        ),
    )

    formatted = format_telegram_reply(text)

    assert formatted.startswith("【成人资源候选】 SSIS-483\n海报: https://jp.netcdn.space")
    assert "🎬 <b>[SSIS-483] シン・交わる体液、濃密セックス 完全ノーカット5本番</b>" in formatted
    assert "👤 <b>演员：</b> 七ツ森りり" in formatted
    assert "🏢 <b>片商：</b> S1 NO.1 STYLE" in formatted
    assert "🏷 <b>系列：</b> 交融的体液、浓密性爱" in formatted
    assert "📅 <b>日期：</b> 2022-08-05  |  ⏳ <b>时长：</b> 220 分钟" in formatted
    assert "📦 <b>分类：</b> 有码 (Censored)" in formatted
    assert "<b>【资源 1】 sukebei | 3.1 GB | 做种: 3</b>" in formatted
    assert "<code>magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12</code>" in formatted
    assert "&amp;dn=" not in formatted
    assert "&amp;tr=" not in formatted
    assert "链接参考:" not in formatted
    assert "🌐 查看详情 (avmoo)：打开 https://avmoo.shop/cn/movie/4221ec1035fdf66f" in formatted
    assert "➡️ 下一步：发送 magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12" in formatted


def test_build_telegram_reply_func_sends_adult_bt_card_as_photo_caption_with_buttons() -> None:
    reply_text = AsyncMock(return_value="text-sent")
    reply_photo = AsyncMock(return_value="photo-sent")
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        reply_photo_func=reply_photo,
    )
    text = (
        "成人资源候选：SSIS-483\n"
        "1. SSIS-483 resource title\n"
        "   站点: sukebei | 来源入口: sukebei | 做种: 3 | 大小: 3.1 GB\n"
        "   只读补全: avmoo.shop | 番号: SSIS-483 | 分类: censored\n"
        "   只读详情: https://avmoo.shop/cn/movie/4221ec1035fdf66f\n"
        "   海报: https://jp.netcdn.space/digital/video/ssis00483/ssis00483pl.jpg\n"
        "   标准信息: 标题: シン・交わる体液、濃密セックス 完全ノーカット5本番 | 发行日: 2022-08-05 | 时长: 220 分钟\n"
        "   制作信息: 制作商: S1 NO.1 STYLE | 系列: 交融的体液、浓密性爱 | 演员: 七ツ森りり\n"
        "   Metadata源: avmoo | 角色: primary\n"
        "   磁力链接: magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12&dn=SSIS-483\n"
        "只读说明：以上为当前已配置成人源返回的资源候选，不会创建审批或下载任务。"
    )

    result = asyncio.run(reply_func(text))

    assert result == "photo-sent"
    reply_text.assert_not_called()
    reply_photo.assert_awaited_once()
    kwargs = reply_photo.await_args.kwargs
    assert kwargs["photo"] == "https://jp.netcdn.space/digital/video/ssis00483/ssis00483pl.jpg"
    assert kwargs["parse_mode"] == "HTML"
    assert "海报:" not in kwargs["caption"]
    assert kwargs["caption"].startswith("🎬 <b>[SSIS-483]")
    assert "<code>magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12</code>" in kwargs["caption"]
    reply_markup = kwargs["reply_markup"]
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert tuple(tuple(button.text for button in row) for row in reply_markup.inline_keyboard) == (
        ("🌐 查看详情 (avmoo)", "➡️ 下一步"),
    )
    first_button, second_button = reply_markup.inline_keyboard[0]
    assert first_button.url == "https://avmoo.shop/cn/movie/4221ec1035fdf66f"
    assert second_button.callback_data == "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12"


def test_build_telegram_reply_func_sends_local_posters_before_candidate_confirmation_text() -> None:
    send_text = AsyncMock(return_value="text-ok")
    sent_media: list[tuple[int, str, str | None]] = []

    async def fake_send_media(
        chat_id: int,
        file_path: str | Path,
        caption: str | None = None,
        parse_mode: str | None = None,
    ) -> object:
        resolved_path = Path(file_path)
        assert resolved_path.is_file()
        sent_media.append((chat_id, resolved_path.read_text(encoding="utf-8"), caption))
        return "media-ok"

    async def fake_download_image(url: str) -> bytes:
        return f"downloaded:{url}".encode("utf-8")

    reply_text = AsyncMock(return_value="fallback")
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        chat_id=1001,
        send_text_func=send_text,
        send_media_func=fake_send_media,
        download_image_func=fake_download_image,
    )
    text = render_telegram_text(
        build_media_candidate_confirmation_delivery_item(
            query="你的名字",
            parsed_query=ParsedMovieQuery(title="你的名字", year=""),
            tmdb_candidates=(
                TmdbMovie(
                    title="你的名字。",
                    original_title="君の名は。",
                    year="2016",
                    tmdb_id="101",
                    media_type="movie",
                    poster_path="/your-name.jpg",
                    overview="Two teenagers share a supernatural connection.",
                ),
                TmdbMovie(
                    title="你的名字 特别收藏版",
                    original_title="君の名は。4K Collection",
                    year="2017",
                    tmdb_id="102",
                    media_type="movie",
                    poster_path="/your-name-collection.jpg",
                    overview="A longer noisy collection title that should stay behind the exact film.",
                ),
            ),
        )
    )

    result = asyncio.run(reply_func(text))

    assert result == "text-ok"
    assert len(sent_media) == 2
    assert sent_media[0][0] == 1001
    assert "https://image.tmdb.org/t/p/w500/your-name.jpg" in sent_media[0][1]
    assert sent_media[0][2] == (
        "【1】 你的名字。 (2016) | movie\n"
        "年份：2016\n"
        "类型：movie\n"
        "原名：君の名は。\n"
        "简介：Two teenagers share a supernatural connection."
    )
    assert "https://image.tmdb.org/t/p/w500/your-name-collection.jpg" in sent_media[1][1]
    assert sent_media[1][2] == (
        "【2】 你的名字 特别收藏版 (2017) | movie\n"
        "年份：2017\n"
        "类型：movie\n"
        "原名：君の名は。4K Collection\n"
        "简介：A longer noisy collection title that should stay behind the exact film."
    )
    reply_text.assert_not_called()
    send_text.assert_awaited_once()
    sent_text = send_text.await_args.kwargs["text"]
    assert "海报：" not in sent_text
    assert "【候选作品】 你的名字" in sent_text
    assert "【1】 你的名字。" in sent_text
    assert "【2】 你的名字 特别收藏版" in sent_text
    assert "直接回复 1-2 中的序号确认作品，例如：1" in sent_text


def test_format_telegram_reply_keeps_unrelated_text() -> None:
    text = "普通回复，不需要 Telegram 特殊格式化。"

    assert format_telegram_reply(text) == text


def test_build_telegram_reply_func_formats_text_before_replying() -> None:
    reply_text = AsyncMock(return_value="sent")
    reply_func = build_telegram_reply_func(reply_text, formatter=format_telegram_reply)
    text = render_telegram_text(
        DeliveryItem(
            header=DeliveryHeader(kind="approval", title="待确认：下载"),
            sections=(DeliverySection(label="任务信息", lines=("片名：Frieren S01E01 1080p", "选择序号：hash-1")),),
            actions=(DeliveryAction(label="确认下载", hint="发送 confirm hash-1", kind="primary"),),
            status="pending",
        )
    )

    result = asyncio.run(reply_func(text))

    assert result == "sent"
    reply_text.assert_awaited_once()
    formatted_text = reply_text.await_args.args[0]
    assert formatted_text == text


def test_build_telegram_reply_func_sends_candidate_cards_as_photo_messages_when_poster_exists() -> None:
    reply_text = AsyncMock(return_value="text-sent")
    reply_photo = AsyncMock(return_value="photo-sent")
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        reply_photo_func=reply_photo,
    )
    text = (
        "候选作品：你的名字\n"
        "1. 你的名字。 (2016) | movie\n"
        "   海报: https://image.tmdb.org/t/p/w500/your-name.jpg\n"
        "   原名: 君の名は。\n"
        "   简介: Two teenagers share a mysterious connection.\n"
        "2. Your Name Special (2021) | tv\n"
        "   海报: https://image.tmdb.org/t/p/w500/your-name-special.jpg\n"
        "   简介: A lower relevance expanded-title result.\n"
        "直接回复对应序号确认作品，例如：1"
    )

    result = asyncio.run(reply_func(text))

    assert result == "text-sent"
    reply_photo.assert_any_await(
        photo="https://image.tmdb.org/t/p/w500/your-name.jpg",
        caption="【1】 你的名字。 (2016) | movie\n原名: 君の名は。\n简介: Two teenagers share a mysterious connection.",
    )
    reply_photo.assert_any_await(
        photo="https://image.tmdb.org/t/p/w500/your-name-special.jpg",
        caption="【2】 Your Name Special (2021) | tv\n简介: A lower relevance expanded-title result.",
    )
    reply_text.assert_any_await("【候选作品】 你的名字\n候选作品（2 条）")
    reply_text.assert_any_await("下一步\n直接回复 1-2 中的序号确认作品，例如：1")


def test_build_telegram_reply_func_falls_back_to_text_when_photo_send_fails(capsys) -> None:
    reply_text = AsyncMock(return_value="text-sent")
    reply_photo = AsyncMock(side_effect=RuntimeError("telegram photo failed"))
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        reply_photo_func=reply_photo,
    )
    text = (
        "候选作品：你的名字\n"
        "1. 你的名字。 (2016) | movie\n"
        "   海报: https://image.tmdb.org/t/p/w500/your-name.jpg\n"
        "   原名: 君の名は。\n"
        "   简介: Two teenagers share a mysterious connection.\n"
        "直接回复对应序号确认作品，例如：1"
    )

    result = asyncio.run(reply_func(text))

    assert result == "text-sent"
    reply_photo.assert_awaited_once()
    reply_text.assert_any_await("【1】 你的名字。 (2016) | movie\n原名: 君の名は。\n简介: Two teenagers share a mysterious connection.")
    output = capsys.readouterr().out
    assert "[Telegram 候选海报发送失败]" in output
    assert "telegram photo failed" in output
