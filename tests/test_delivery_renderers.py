from __future__ import annotations

from app.runtime.delivery import (
    DeliveryAction,
    DeliveryHeader,
    DeliveryItem,
    DeliverySection,
    extract_telegram_actions,
    render_feishu_text,
    render_personal_wechat_text,
    render_telegram_text,
    render_wecom_text,
)


def test_render_telegram_text_formats_search_results_fallback() -> None:
    item = DeliveryItem(
        header=DeliveryHeader(kind="search_results", title="搜索：Dune 2021", subtitle="候选结果（2 条）"),
        sections=(
            DeliverySection(label="候选结果", lines=("1. Dune 2021", "2. Dune Part Two")),
        ),
        actions=(
            DeliveryAction(label="选择 1", hint="发送 select 1", kind="primary"),
        ),
        footer="如需重搜，请发送 search 沙丘 2021",
        status="success",
    )

    text = render_telegram_text(item)

    assert text.startswith("搜索：Dune 2021 ✓")
    assert "候选结果" in text
    assert "1. Dune 2021" in text
    assert "下一步" in text
    assert "选择 1：发送 select 1" in text
    assert text.endswith("如需重搜，请发送 search 沙丘 2021")


def test_render_telegram_text_preserves_action_queries_for_inline_buttons() -> None:
    item = DeliveryItem(
        header=DeliveryHeader(kind="approval", title="待确认：下载"),
        sections=(
            DeliverySection(label="任务信息", lines=("片名：Dune 2021", "选择序号：hash-87")),
        ),
        actions=(
            DeliveryAction(label="确认下载", hint="发送 confirm hash-87", kind="primary"),
            DeliveryAction(label="取消下载", hint="发送 cancel hash-87", kind="secondary"),
            DeliveryAction(label="刷新状态", hint="发送 status hash-87", kind="secondary"),
        ),
        status="pending",
    )

    text = render_telegram_text(item)
    actions = extract_telegram_actions(text)

    assert text.startswith("待确认：下载 ⏳")
    assert tuple((action.label, action.hint, action.kind) for action in actions) == tuple(
        (action.label, action.hint, action.kind) for action in item.actions
    )
    assert tuple(action.callback_query for action in actions) == (
        "confirm hash-87",
        "cancel hash-87",
        "status hash-87",
    )


def test_render_feishu_text_formats_error_fallback() -> None:
    item = DeliveryItem(
        header=DeliveryHeader(kind="error", title="搜索候选状态写入失败"),
        sections=(
            DeliverySection(label="原因", lines=("SQLite candidate_mapping 回读不到刚写入候选",)),
            DeliverySection(label="建议", lines=("稍后重试一次搜索",)),
        ),
        actions=(),
        footer=None,
        status="failure",
    )

    text = render_feishu_text(item)

    assert text.startswith("搜索候选状态写入失败 ❌")
    assert "原因" in text
    assert "建议" in text


def test_render_personal_wechat_text_formats_approval_text() -> None:
    item = DeliveryItem(
        header=DeliveryHeader(kind="approval", title="待确认：下载"),
        sections=(
            DeliverySection(label="任务信息", lines=("片名：Dune 2021", "画质：2160p UHD BluRay")),
        ),
        actions=(
            DeliveryAction(label="确认下载", hint="发送 confirm 1", kind="primary"),
            DeliveryAction(label="取消下载", hint="发送 cancel 1", kind="secondary"),
        ),
        footer="过期时间：10 分钟后",
        status="pending",
    )

    text = render_personal_wechat_text(item)

    assert text.startswith("【待确认：下载】 ⏳")
    assert "▸ 任务信息" in text
    assert "确认下载：发送 confirm 1" in text
    assert "取消下载：发送 cancel 1" in text
    assert text.endswith("过期时间：10 分钟后")


def test_render_wecom_text_formats_compact_status_text() -> None:
    item = DeliveryItem(
        header=DeliveryHeader(kind="status", title="下载状态"),
        sections=(
            DeliverySection(label="当前进度", lines=("任务：hash-87", "进度：100%")),
            DeliverySection(label="后续", lines=("已进入自动导入边界",)),
        ),
        actions=(
            DeliveryAction(label="查看详情", hint="发送 status hash-87", kind="secondary"),
        ),
        footer=None,
        status="warning",
    )

    text = render_wecom_text(item)

    assert text.startswith("下载状态 ⚠️")
    assert "- 当前进度" in text
    assert "- 后续" in text
    assert "- 查看详情：发送 status hash-87" in text
