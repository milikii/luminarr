import asyncio
from unittest.mock import AsyncMock

from app.bot.telegram_update_runtime import build_telegram_reply_func
from app.bot.telegram_reply_formatter import format_telegram_reply
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_telegram_text
from app.services.search_reply_formatter import format_adult_bt_resource_fallback_reply


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

    assert formatted.startswith("【成人资源候选】 SSIS-123\n候选结果（1 条）")
    assert "【1】 SSIS-123 Sample Title" in formatted
    assert "海报: https://img.example/ssis-123.jpg" in formatted
    assert "标题: SSIS-123 Sample Title | 发行日: 2026-01-02 | 时长: 120 分钟" in formatted
    assert "Metadata: avmoo (primary)" in formatted
    assert "磁力: magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12&dn=ssis-123" in formatted
    assert "链接参考:" not in formatted
    assert "复制上面的磁力链接后发送，选择 BT 成人链。" in formatted


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
    assert "候选结果（1 条）" in formatted
    assert "【1】 SSIS-123 Secret Mission Nurse" in formatted
    assert "番号: SSIS-123 | 分类: censored" in formatted
    assert "海报: https://img.example/ssis-123.jpg" in formatted
    assert "发行日: 2026-04-01" in formatted
    assert "演员: Aki / Mei" in formatted
    assert "制作商: S1" in formatted
    assert "系列: Secret Mission" in formatted
    assert "Metadata: javlibrary (backup/cross-check)" in formatted
    assert f"磁力: {magnet}" in formatted
    assert "详情: https://www.javlibrary.com/tw/?v=javli0001" in formatted
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
    assert "【1】 SSIS-483 Detail Title" in formatted
    assert "只读补全: avmoo.shop | 番号: SSIS-483 | 分类: censored" in formatted
    assert "海报: https://jp.netcdn.space/digital/video/ssis00483/ssis00483pl.jpg" in formatted
    assert "发行日: 2023-05-01" in formatted
    assert "时长: 120分钟" in formatted
    assert "制作商: S1" in formatted
    assert "厂牌: S1 Label" in formatted
    assert "系列: Secret Mission" in formatted
    assert "演员: Aki / Mei" in formatted
    assert "Metadata: avmoo (primary)" in formatted
    assert f"磁力: {magnet}" in formatted
    assert "详情: https://avmoo.shop/cn/movie/4221ec1035fdf66f" in formatted
    assert "链接参考: magnet | infoHash" not in formatted


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
