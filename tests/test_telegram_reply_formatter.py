import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram import InlineKeyboardMarkup

from app.bot import telegram_update_runtime
from app.clients.tmdb import TmdbMovie
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.sqlite import SqliteDatabase
from app.bot.telegram_update_runtime import build_telegram_reply_func
from app.bot.telegram_reply_formatter import format_telegram_reply
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_telegram_text
from app.services.search_query_parser import ParsedMovieQuery
from app.services.search_reply_formatter import (
    build_media_candidate_confirmation_delivery_item,
    format_adult_bt_resource_fallback_reply,
    render_media_candidate_confirmation_reply,
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
    assert "👤 <b>演员：</b> <code>Actor A, Actor B</code>" in formatted
    assert "📦 <b>分类：</b> 有码 (Censored)" in formatted
    assert "<b>【资源 1】 tokyotosho | 2.0 GB | 做种: 12</b>" in formatted
    assert "<code>magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12</code>" in formatted
    assert "&amp;dn=ssis-123" not in formatted
    assert "链接参考:" not in formatted
    assert "➡️ 下一步：发送 magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12" in formatted


def test_format_telegram_reply_formats_media_candidate_confirmation_with_primary_hero_block() -> None:
    text = (
        "候选作品：你的名字\n"
        "1. 你的名字。 (2016) | movie\n"
        "海报: https://image.tmdb.org/t/p/w500/your-name.jpg\n"
        "原名: 君の名は。\n"
        "年份: 2016\n"
        "类型: movie\n"
        "简介: Two teenagers share a supernatural connection.\n"
        "TMDB详情: https://www.themoviedb.org/movie/101\n"
        "2. 你的名字 特别收藏版 (2017) | movie\n"
        "海报: https://image.tmdb.org/t/p/w500/your-name-collection.jpg\n"
        "原名: 君の名は。4K Collection\n"
        "年份: 2017\n"
        "类型: movie\n"
        "简介: A longer noisy collection title that should stay behind the exact film.\n"
        "TMDB详情: https://www.themoviedb.org/movie/102\n"
        "3. 你的名字 剧场纪念版 (2018) | movie\n"
        "海报: https://image.tmdb.org/t/p/w500/your-name-memorial.jpg\n"
        "原名: 君の名は。 Memorial Edition\n"
        "年份: 2018\n"
        "类型: movie\n"
        "简介: A weaker commemorative release candidate.\n"
        "TMDB详情: https://www.themoviedb.org/movie/103"
    )

    formatted = format_telegram_reply(text)

    assert formatted.startswith("【你的名字】共找到 3 条相关信息，请选择操作")
    assert "候选作品（3 条）" not in formatted
    assert "【1】 <b>你的名字。 (2016) | movie</b>" not in formatted
    assert '1. <a href="https://www.themoviedb.org/movie/101">你的名字。 (2016) | movie</a>' in formatted
    assert '海报预览：<a href="https://image.tmdb.org/t/p/w500/your-name.jpg">打开海报</a>' in formatted
    assert formatted.count("海报预览：") == 1
    assert "<i>君の名は。</i>" in formatted
    assert "📅 <b>年份：</b> 2016" in formatted
    assert "🎞 <b>类型：</b> movie" in formatted
    assert "📝 <b>简介：</b> Two teenagers share a supernatural connection." in formatted
    assert "🌐 <b>TMDB详情：</b>" not in formatted
    assert '2. <a href="https://www.themoviedb.org/movie/102">你的名字 特别收藏版 (2017) | movie</a>' in formatted
    assert "海报: https://image.tmdb.org/t/p/w500/your-name-collection.jpg" not in formatted
    assert "<i>君の名は。4K Collection</i>" in formatted
    assert "📅 <b>年份：</b> 2017" in formatted
    assert "🎞 <b>类型：</b> movie" in formatted
    assert "📝 <b>简介：</b> A longer noisy collection title that should stay behind the exact film." in formatted
    assert '3. <a href="https://www.themoviedb.org/movie/103">你的名字 剧场纪念版 (2018) | movie</a>' in formatted
    assert "海报: https://image.tmdb.org/t/p/w500/your-name-memorial.jpg" not in formatted
    assert "<i>君の名は。 Memorial Edition</i>" in formatted
    assert "📅 <b>年份：</b> 2018" in formatted
    assert "🎞 <b>类型：</b> movie" in formatted
    assert "📝 <b>简介：</b> A weaker commemorative release candidate." in formatted
    assert formatted.count('<a href="https://www.themoviedb.org/movie/') == 3
    assert formatted.count("📝 <b>简介：</b>") == 3
    assert formatted.endswith(
        "下一步\n"
        "确认作品：直接回复序号，例如 1\n"
        "都不对：发送更详细的名称，或直接发送新的名字/关键词重新搜"
    )


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


def test_format_telegram_reply_formats_add_success_as_copy_friendly_card() -> None:
    text = (
        "已添加下载：Dune 2021 2160p WEB-DL\n"
        "任务 ID: 42\n"
        "任务 Hash: abc123\n"
        "下载器: pt-main · qbittorrent\n"
        "注意：下载已执行，但状态回写失败，请勿重复 confirm。\n"
        "请稍后用 status 查询任务状态，或检查 SQLite/approval_record 与 jobs 表。"
    )

    formatted = format_telegram_reply(text)

    assert formatted == (
        "✅ <b>任务已添加并开始下载</b>\n"
        "━━━━━━━━━━━━\n"
        "<i>Dune 2021 2160p WEB-DL</i>\n"
        "🧩 <b>下载器：</b> <code>pt-main · qbittorrent</code>\n"
        "<b>状态：</b> 等待下载器同步\n"
        "<b>下载进度：</b> 0%\n"
        "<code>[░░░░░░░░░░]</code>\n\n"
        "⚡ <b>速度：</b> --  |  <b>剩余：</b> --\n"
        "━━━━━━━━━━━━\n"
        "<b>后处理</b>\n"
        "- 导入：等待\n"
        "- 刮削：等待\n"
        "- 字幕：等待\n"
        "- 刷新：等待\n"
        "━━━━━━━━━━━━\n"
        "🆔 <b>任务 ID：</b> <code>42</code>\n"
        "🔑 <b>Hash：</b> <code>abc123</code>\n\n"
        "⏱️ <b>消息每 5 秒自动刷新一次</b>\n\n"
        "注意：下载已执行，但状态回写失败，请勿重复 confirm。\n"
        "请稍后用 status 查询任务状态，或检查 SQLite/approval_record 与 jobs 表。"
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
    assert "👤 <b>演员：</b> <code>Aki / Mei</code>" in formatted
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
    assert "🏭 <b>厂牌：</b> S1 Label" not in formatted
    assert "🏷 <b>系列：</b> Secret Mission" in formatted
    assert "👤 <b>演员：</b> <code>Aki / Mei</code>" in formatted
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
    assert "🎬 <b>[SSIS-483] 新·交融的体液、浓密性爱 完全未删减 5本番</b>" in formatted
    assert "<i>シン・交わる体液、濃密セックス 完全ノーカット5本番</i>" in formatted
    assert "👤 <b>演员：</b> <code>七森莉莉</code>" in formatted
    assert "原演员: 七ツ森りり" not in formatted
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


def test_format_telegram_reply_keeps_translated_adult_title_but_preserves_original_caption_template() -> None:
    text = format_adult_bt_resource_fallback_reply(
        "SSIS-842",
        (
            {
                "title": "SSIS-842 release title",
                "source": "magnet:?xt=urn:btih:9999999999999999999999999999999999999999&dn=SSIS-842",
                "infoHash": "9999999999999999999999999999999999999999",
                "seeders": 11,
                "size": 3 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
                "read_only_adult_source_site": "avmoo.shop",
                "read_only_adult_display_id": "SSIS-842",
                "read_only_adult_archive_category": "censored",
                "read_only_adult_title": "SSIS-842 彼女のリアルで生々しい姿をお見せします",
                "read_only_adult_poster_url": "https://img.example/ssis-842.jpg",
                "read_only_adult_series": "リアルSEXドキュメント",
                "read_only_adult_maker": "エスワン ナンバーワンスタイル",
                "read_only_adult_label": "S1 原厂牌",
                "read_only_adult_director": "苺原",
                "read_only_adult_actors": ("うんぱい",),
                "adult_translation_title_zh": "SSIS-842 让你看到她真实而鲜活的一面",
                "adult_translation_overview_zh": "这是一段翻译后的中文简介，详细描述了人物关系、欲望冲突与情绪变化。",
                "adult_translation_series_zh": "真实性爱纪录",
                "adult_translation_maker_zh": "S1 顶级风格",
                "adult_translation_label_zh": "S1 中文厂牌",
                "adult_translation_director_zh": "莓原",
            },
        ),
    )

    formatted = format_telegram_reply(text)

    assert formatted.startswith("【成人资源候选】 SSIS-842\n海报: https://img.example/ssis-842.jpg")
    assert "🎬 <b>[SSIS-842] 让你看到她真实而鲜活的一面</b>" in formatted
    assert "<i>SSIS-842 彼女のリアルで生々しい姿をお見せします</i>" in formatted
    assert "👤 <b>演员：</b> <code>うんぱい</code>" in formatted
    assert "中文名未确认" not in formatted
    assert "🏢 <b>片商：</b> S1 顶级风格" in formatted
    assert "🏷 <b>系列：</b> 真实性爱纪录" in formatted
    assert "📝 <b>简介：</b>" not in formatted
    assert "🏭 <b>厂牌：</b>" not in formatted
    assert "🎬 <b>导演：</b>" not in formatted


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
        "   简介: 这是一段本不该出现在 Telegram 成人 caption 里的简介。\n"
        "   制作信息: 制作商: S1 NO.1 STYLE | 厂牌: S1 Label | 系列: 交融的体液、浓密性爱 | 导演: 苺原 | 演员: 七ツ森りり\n"
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
    assert "📝 <b>简介：</b>" not in kwargs["caption"]
    assert "🏭 <b>厂牌：</b>" not in kwargs["caption"]
    assert "🎬 <b>导演：</b>" not in kwargs["caption"]
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
    reply_text = AsyncMock(return_value="fallback")
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        chat_id=1001,
        send_text_func=send_text,
    )
    text = render_media_candidate_confirmation_reply(
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
            TmdbMovie(
                title="你的名字 剧场纪念版",
                original_title="君の名は。 Memorial Edition",
                year="2018",
                tmdb_id="103",
                media_type="movie",
                poster_path="/your-name-memorial.jpg",
                overview="A weaker commemorative release candidate.",
            ),
        ),
        channel="telegram",
    )

    result = asyncio.run(reply_func(text))

    assert result == "text-ok"
    reply_text.assert_not_called()
    send_text.assert_awaited_once()
    kwargs = send_text.await_args.kwargs
    sent_text = kwargs["text"]
    assert kwargs["parse_mode"] == "HTML"
    assert sent_text.startswith("【你的名字】共找到 3 条相关信息，请选择操作")
    assert '海报预览：<a href="https://image.tmdb.org/t/p/w500/your-name.jpg">打开海报</a>' in sent_text
    assert '2. <a href="https://www.themoviedb.org/movie/102">你的名字 特别收藏版 (2017) | movie</a>' in sent_text
    assert '3. <a href="https://www.themoviedb.org/movie/103">你的名字 剧场纪念版 (2018) | movie</a>' in sent_text
    assert sent_text.count("海报预览：") == 1
    assert "确认作品：直接回复序号，例如 1" in sent_text
    assert "都不对：发送更详细的名称，或直接发送新的名字/关键词重新搜" in sent_text


def test_build_telegram_reply_func_keeps_single_candidate_followup_minimal_after_local_poster_send() -> None:
    send_text = AsyncMock(return_value="text-ok")
    send_media = AsyncMock(return_value="media-ok")
    download_image = AsyncMock(return_value=b"fake-image")
    reply_text = AsyncMock(return_value="fallback")
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        chat_id=1001,
        send_text_func=send_text,
        send_media_func=send_media,
        download_image_func=download_image,
    )
    text = render_media_candidate_confirmation_reply(
        query="Dune 2021",
        parsed_query=ParsedMovieQuery(title="Dune", year="2021"),
        tmdb_candidates=(
            TmdbMovie(
                title="Dune",
                original_title="Dune",
                year="2021",
                tmdb_id="438631",
                media_type="movie",
                poster_path="/dune.jpg",
                overview="Paul Atreides leads nomadic tribes in a battle to control Arrakis.",
            ),
        ),
        channel="telegram",
    )

    result = asyncio.run(reply_func(text))

    assert result == "media-ok"
    reply_text.assert_not_called()
    download_image.assert_awaited_once_with("https://image.tmdb.org/t/p/w500/dune.jpg")
    send_media.assert_awaited_once()
    assert send_media.await_args.args[0] == 1001
    assert send_media.await_args.args[2] is not None
    assert send_media.await_args.args[3] == "HTML"
    send_text.assert_not_awaited()
    caption = send_media.await_args.args[2]
    assert caption.startswith("【Dune 2021】共找到 1 条相关信息，请选择操作")
    assert '1. <a href="https://www.themoviedb.org/movie/438631">Dune (2021) | movie</a>' in caption
    assert "海报预览：" not in caption
    assert "<i>Dune</i>" in caption
    assert "📅 <b>年份：</b> 2021" in caption
    assert "🎞 <b>类型：</b> movie" in caption
    assert "📝 <b>简介：</b> Paul Atreides leads nomadic tribes in a battle to control Arrakis." in caption
    assert caption.endswith(
        "下一步\n"
        "确认作品：直接回复序号，例如 1\n"
        "都不对：发送更详细的名称，或直接发送新的名字/关键词重新搜"
    )


def test_build_telegram_reply_func_sends_aggregate_candidate_confirmation_as_html_text() -> None:
    reply_text = AsyncMock(return_value="reply-sent")
    send_text = AsyncMock(return_value="text-sent")
    reply_photo = AsyncMock(return_value="photo-sent")
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        chat_id=1001,
        send_text_func=send_text,
        reply_photo_func=reply_photo,
    )
    text = (
        "候选作品：Dune 2021\n"
        "1. Dune (2021) | movie\n"
        "   海报: https://image.tmdb.org/t/p/w500/dune.jpg\n"
        "   原名: Dune\n"
        "   年份: 2021\n"
        "   类型: movie\n"
        "   简介: Paul Atreides leads nomadic tribes in a battle to control Arrakis.\n"
        "   TMDB详情: https://www.themoviedb.org/movie/438631"
    )

    result = asyncio.run(reply_func(text))

    assert result == "text-sent"
    reply_photo.assert_not_awaited()
    reply_text.assert_not_awaited()
    kwargs = send_text.await_args.kwargs
    assert kwargs["chat_id"] == 1001
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["text"] == (
        "【Dune 2021】共找到 1 条相关信息，请选择操作\n\n"
        '1. <a href="https://www.themoviedb.org/movie/438631">Dune (2021) | movie</a>\n'
        '海报预览：<a href="https://image.tmdb.org/t/p/w500/dune.jpg">打开海报</a>\n'
        "<i>Dune</i>\n"
        "📅 <b>年份：</b> 2021\n"
        "🎞 <b>类型：</b> movie\n"
        "📝 <b>简介：</b> Paul Atreides leads nomadic tribes in a battle to control Arrakis.\n\n"
        "下一步\n"
        "确认作品：直接回复序号，例如 1\n"
        "都不对：发送更详细的名称，或直接发送新的名字/关键词重新搜"
    )


def test_candidate_placeholder_font_prefers_cjk_fonts(monkeypatch) -> None:
    attempts: list[str] = []
    fallback_font = object()

    def fake_truetype(path: str, size: int) -> object:
        attempts.append(path)
        if path.endswith("DejaVuSans.ttf"):
            return fallback_font
        raise OSError("missing")

    monkeypatch.setattr(telegram_update_runtime.ImageFont, "truetype", fake_truetype)
    monkeypatch.setattr(telegram_update_runtime.ImageFont, "load_default", lambda: object())

    font = telegram_update_runtime._load_placeholder_font(24)

    assert font is fallback_font
    assert attempts == [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]


def test_build_telegram_reply_func_splits_aggregate_candidate_confirmation_at_telegram_limit() -> None:
    reply_text = AsyncMock(return_value="reply-sent")
    send_text = AsyncMock(side_effect=("part-1", "part-2"))
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        chat_id=1001,
        send_text_func=send_text,
    )
    raw_lines = ["候选作品：长查询"]
    for index in range(1, 19):
        raw_lines.extend(
            (
                f"{index}. 候选作品 {index} (202{index % 10}) | movie",
                f"海报: https://image.tmdb.org/t/p/w500/candidate-{index}.jpg",
                f"原名: Candidate {index}",
                f"年份: 202{index % 10}",
                "类型: movie",
                f"简介: {'非常长的候选简介，用来逼近 Telegram 文本上限。' * 10}",
                f"TMDB详情: https://www.themoviedb.org/movie/{1000 + index}",
            )
        )
    text = "\n".join(raw_lines)

    result = asyncio.run(reply_func(text))

    assert result == "part-2"
    assert reply_text.assert_not_awaited() is None
    assert send_text.await_count == 2
    first_chunk = send_text.await_args_list[0].kwargs["text"]
    second_chunk = send_text.await_args_list[1].kwargs["text"]
    assert len(first_chunk) <= 4096
    assert len(second_chunk) <= 4096
    assert first_chunk.startswith("【长查询】共找到 18 条相关信息，请选择操作")
    assert '1. <a href="https://www.themoviedb.org/movie/1001">候选作品 1 (2021) | movie</a>' in first_chunk
    assert '18. <a href="https://www.themoviedb.org/movie/1018">候选作品 18 (2028) | movie</a>' in second_chunk
    assert second_chunk.endswith(
        "下一步\n"
        "确认作品：直接回复序号，例如 1\n"
        "都不对：发送更详细的名称，或直接发送新的名字/关键词重新搜"
    )


def test_render_telegram_text_prefers_localized_title_for_non_chinese_tmdb_candidate() -> None:
    text = render_telegram_text(
        build_media_candidate_confirmation_delivery_item(
            query="丧尸",
            parsed_query=ParsedMovieQuery(title="丧尸", year=""),
            tmdb_candidates=(
                TmdbMovie(
                    title="Zombie Detective",
                    original_title="좀비탐정",
                    year="2020",
                    tmdb_id="111",
                    media_type="tv",
                    poster_path="/zombie-detective.jpg",
                    overview="A detective story with a zombie lead.",
                ),
            ),
        )
    )

    assert "候选作品：丧尸" in text
    assert "先确认最可能的作品：" not in text
    assert "1. Zombie Detective (2020) | tv" in text
    assert "海报：https://image.tmdb.org/t/p/w500/zombie-detective.jpg" in text
    assert "原名：좀비탐정" in text
    assert "年份：2020" in text
    assert "类型：tv" in text
    assert "简介：A detective story with a zombie lead." in text
    assert "TMDB详情：https://www.themoviedb.org/tv/111" in text
    assert "原名：Zombie Detective" not in text


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


def test_build_telegram_reply_func_replies_add_success_card_as_html() -> None:
    reply_text = AsyncMock(return_value="sent")
    reply_func = build_telegram_reply_func(reply_text, formatter=format_telegram_reply)
    text = "已添加下载：Dune 2021 2160p WEB-DL\n任务 ID: 42\n任务 Hash: abc123\n下载器: pt-main · qbittorrent"

    result = asyncio.run(reply_func(text))

    assert result == "sent"
    reply_text.assert_awaited_once()
    assert reply_text.await_args.args[0] == (
        "✅ <b>任务已添加并开始下载</b>\n"
        "━━━━━━━━━━━━\n"
        "<i>Dune 2021 2160p WEB-DL</i>\n"
        "🧩 <b>下载器：</b> <code>pt-main · qbittorrent</code>\n"
        "<b>状态：</b> 等待下载器同步\n"
        "<b>下载进度：</b> 0%\n"
        "<code>[░░░░░░░░░░]</code>\n\n"
        "⚡ <b>速度：</b> --  |  <b>剩余：</b> --\n"
        "━━━━━━━━━━━━\n"
        "<b>后处理</b>\n"
        "- 导入：等待\n"
        "- 刮削：等待\n"
        "- 字幕：等待\n"
        "- 刷新：等待\n"
        "━━━━━━━━━━━━\n"
        "🆔 <b>任务 ID：</b> <code>42</code>\n"
        "🔑 <b>Hash：</b> <code>abc123</code>\n\n"
        "⏱️ <b>消息每 5 秒自动刷新一次</b>"
    )
    assert reply_text.await_args.kwargs["parse_mode"] == "HTML"
    reply_markup = reply_text.await_args.kwargs["reply_markup"]
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert tuple(tuple(button.text for button in row) for row in reply_markup.inline_keyboard) == (("查看状态",),)


def test_build_telegram_reply_func_sends_add_success_card_via_send_text_when_available() -> None:
    reply_text = AsyncMock(return_value="reply-sent")
    send_text = AsyncMock(return_value="send-sent")
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        chat_id=1001,
        send_text_func=send_text,
    )
    text = "已添加下载：Dune 2021 2160p WEB-DL\n任务 ID: 42\n任务 Hash: abc123"

    result = asyncio.run(reply_func(text))

    assert result == "send-sent"
    reply_text.assert_not_awaited()
    send_text.assert_awaited_once()
    assert send_text.await_args.kwargs["chat_id"] == 1001
    assert send_text.await_args.kwargs["parse_mode"] == "HTML"
    assert send_text.await_args.kwargs["text"] == (
        "✅ <b>任务已添加并开始下载</b>\n"
        "━━━━━━━━━━━━\n"
        "<i>Dune 2021 2160p WEB-DL</i>\n"
        "<b>状态：</b> 等待下载器同步\n"
        "<b>下载进度：</b> 0%\n"
        "<code>[░░░░░░░░░░]</code>\n\n"
        "⚡ <b>速度：</b> --  |  <b>剩余：</b> --\n"
        "━━━━━━━━━━━━\n"
        "<b>后处理</b>\n"
        "- 导入：等待\n"
        "- 刮削：等待\n"
        "- 字幕：等待\n"
        "- 刷新：等待\n"
        "━━━━━━━━━━━━\n"
        "🆔 <b>任务 ID：</b> <code>42</code>\n"
        "🔑 <b>Hash：</b> <code>abc123</code>\n\n"
        "⏱️ <b>消息每 5 秒自动刷新一次</b>"
    )
    reply_markup = send_text.await_args.kwargs["reply_markup"]
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert tuple(tuple(button.text for button in row) for row in reply_markup.inline_keyboard) == (("查看状态",),)


def test_build_telegram_reply_func_tracks_add_success_message_id_in_download_monitor(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="42",
        task_hash="abc123",
        name="Dune 2021 2160p WEB-DL",
        chat_id=1001,
        user_id=2001,
    )
    reply_text = AsyncMock(return_value="reply-sent")
    send_text = AsyncMock(return_value=SimpleNamespace(message_id=654))
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        chat_id=1001,
        send_text_func=send_text,
        download_monitor_repo=monitor_repo,
    )
    text = "已添加下载：Dune 2021 2160p WEB-DL\n任务 ID: 42\n任务 Hash: abc123"

    result = asyncio.run(reply_func(text))

    assert result.message_id == 654
    reply_text.assert_not_awaited()
    send_text.assert_awaited_once()
    record = monitor_repo.get_record(task_id="42", task_hash="abc123")
    assert record is not None
    assert record.telegram_message_id == 654


def test_build_telegram_reply_func_sends_candidate_cards_as_photo_messages_when_poster_exists() -> None:
    reply_text = AsyncMock(return_value="text-sent")
    send_text = AsyncMock(return_value="text-sent")
    reply_photo = AsyncMock(return_value="photo-sent")
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        chat_id=1001,
        send_text_func=send_text,
        reply_photo_func=reply_photo,
    )
    text = (
        "候选作品：你的名字\n"
        "1. 你的名字。 (2016) | movie\n"
        "   海报: https://image.tmdb.org/t/p/w500/your-name.jpg\n"
        "   原名: 君の名は。\n"
        "   年份: 2016\n"
        "   类型: movie\n"
        "   简介: Two teenagers share a mysterious connection.\n"
        "   TMDB详情: https://www.themoviedb.org/movie/101\n"
        "2. Your Name Special (2021) | tv\n"
        "   海报: https://image.tmdb.org/t/p/w500/your-name-special.jpg\n"
        "   原名: Your Name Special\n"
        "   年份: 2021\n"
        "   类型: tv\n"
        "   简介: A lower relevance expanded-title result.\n"
        "   TMDB详情: https://www.themoviedb.org/tv/202"
    )

    result = asyncio.run(reply_func(text))

    assert result == "text-sent"
    reply_photo.assert_not_awaited()
    reply_text.assert_not_awaited()
    sent_text = send_text.await_args.kwargs["text"]
    assert sent_text.startswith("【你的名字】共找到 2 条相关信息，请选择操作")
    assert '1. <a href="https://www.themoviedb.org/movie/101">你的名字。 (2016) | movie</a>' in sent_text
    assert '海报预览：<a href="https://image.tmdb.org/t/p/w500/your-name.jpg">打开海报</a>' in sent_text
    assert '2. <a href="https://www.themoviedb.org/tv/202">Your Name Special (2021) | tv</a>' in sent_text
    assert "确认作品 1" not in sent_text
    assert "确认作品 2" not in sent_text


def test_build_telegram_reply_func_falls_back_to_text_when_photo_send_fails(capsys) -> None:
    reply_text = AsyncMock(return_value="text-sent")
    send_text = AsyncMock(return_value="text-sent")
    reply_photo = AsyncMock(side_effect=RuntimeError("telegram photo failed"))
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        chat_id=1001,
        send_text_func=send_text,
        reply_photo_func=reply_photo,
    )
    text = (
        "候选作品：你的名字\n"
        "1. 你的名字。 (2016) | movie\n"
        "   海报: https://image.tmdb.org/t/p/w500/your-name.jpg\n"
        "   原名: 君の名は。\n"
        "   年份: 2016\n"
        "   类型: movie\n"
        "   简介: Two teenagers share a mysterious connection.\n"
        "   TMDB详情: https://www.themoviedb.org/movie/101"
    )

    result = asyncio.run(reply_func(text))

    assert result == "text-sent"
    reply_photo.assert_not_awaited()
    reply_text.assert_not_awaited()
    sent_text = send_text.await_args.kwargs["text"]
    assert sent_text.startswith("【你的名字】共找到 1 条相关信息，请选择操作")
    assert '海报预览：<a href="https://image.tmdb.org/t/p/w500/your-name.jpg">打开海报</a>' in sent_text
    output = capsys.readouterr().out
    assert "[Telegram 候选海报发送失败]" not in output


def test_build_telegram_reply_func_keeps_poster_url_in_adult_text_fallback_when_photo_send_fails(capsys) -> None:
    reply_text = AsyncMock(return_value="text-sent")
    reply_photo = AsyncMock(side_effect=RuntimeError("telegram adult photo failed"))
    reply_func = build_telegram_reply_func(
        reply_text,
        formatter=format_telegram_reply,
        reply_photo_func=reply_photo,
    )
    text = (
        "成人资源候选：SSIS-842\n"
        "1. SSIS-842 release title\n"
        "   站点: sukebei | 来源入口: sukebei | 做种: 1 | 大小: 6.1 GB\n"
        "   只读补全: avmoo.shop | 番号: SSIS-842 | 分类: censored\n"
        "   只读详情: https://avmoo.shop/cn/movie/842\n"
        "   海报: https://img.example/ssis-842.jpg\n"
        "   标准信息: 标题: SSIS-842 中文标题 | 原名: SSIS-842 日本語タイトル | 发行日: 2023-08-18 | 时长: 120分钟\n"
        "   制作信息: 制作商: S1 NO.1 STYLE | 系列: 真实性爱纪录 | 演员: うんぱい\n"
        "   磁力链接: magnet:?xt=urn:btih:1efe7c9ceeaf1441c25c8684d0d60c77e7050c99&dn=SSIS-842\n"
        "只读说明：以上为当前已配置成人源返回的资源候选，不会创建审批或下载任务。"
    )

    result = asyncio.run(reply_func(text))

    assert result == "text-sent"
    reply_photo.assert_awaited_once()
    reply_text.assert_awaited_once()
    fallback_text = reply_text.await_args.args[0]
    assert fallback_text.startswith("海报: https://img.example/ssis-842.jpg\n\n🎬 <b>[SSIS-842] 中文标题</b>")
    assert "👤 <b>演员：</b> <code>うんぱい</code>" in fallback_text
    assert "中文名未确认" not in fallback_text
    output = capsys.readouterr().out
    assert "[Telegram 成人资源海报发送失败]" in output
    assert "telegram adult photo failed" in output
