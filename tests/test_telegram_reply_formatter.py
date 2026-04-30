import asyncio
from unittest.mock import AsyncMock

from app.bot.telegram_update_runtime import build_telegram_reply_func
from app.bot.telegram_reply_formatter import format_telegram_reply
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, extract_telegram_actions, render_telegram_text


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
        "直接回复 confirm hash-87 执行导入"
    )


def test_format_telegram_reply_keeps_unrelated_text() -> None:
    text = "普通回复，不需要 Telegram 特殊格式化。"

    assert format_telegram_reply(text) == text


def test_build_telegram_reply_func_preserves_inline_action_metadata_after_formatting() -> None:
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
    assert extract_telegram_actions(formatted_text) == (
        DeliveryAction(
            label="确认下载",
            hint="发送 confirm hash-1",
            kind="primary",
            callback_query="confirm hash-1",
        ),
    )
