from __future__ import annotations

from pathlib import Path


STATUS_SNAPSHOT_LABELS = (
    "tests",
    "four-channel cleanup smoke tests",
    "cleanup service tests",
    "focused cleanup tests",
    "cleanup verification docs gate",
    "focused config truth tests",
    "make run env-file guard tests",
    "compile check",
    "docs consistency check",
    "env readiness snapshot",
    "telegram bot api snapshot",
    "local smoke evidence snapshot",
    "runtime process snapshot",
)


def test_docs_entrypoints_and_snapshot_roles_stay_in_sync() -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")
    index_text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    getting_started_text = Path("docs/GETTING_STARTED.md").read_text(encoding="utf-8")
    architecture_text = Path("docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    next_step_text = Path("docs/NEXT_STEP.md").read_text(encoding="utf-8")
    status_text = Path("docs/STATUS.md").read_text(encoding="utf-8")
    decisions_text = Path("docs/DECISIONS.md").read_text(encoding="utf-8")
    agents_text = Path("AGENTS.md").read_text(encoding="utf-8")
    telegram_bot_slimming_log_text = Path("docs/TELEGRAM_BOT_SLIMMING_LOG.md").read_text(encoding="utf-8")
    download_completion_log_text = Path("docs/DOWNLOAD_COMPLETION_POLLING_LOG.md").read_text(encoding="utf-8")
    feishu_parser_dedupe_log_text = Path("docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md").read_text(encoding="utf-8")
    feishu_risk_log_text = Path("docs/FEISHU_LONG_CONNECTION_RISK_LOG.md").read_text(encoding="utf-8")
    persistence_log_text = Path("docs/PERSISTENCE_CLOSURE_LOG.md").read_text(encoding="utf-8")
    cleanup_window_text = Path("docs/CLEANUP_VERIFICATION_WINDOW.md").read_text(encoding="utf-8")

    assert "docs/INDEX.md" in readme_text
    assert "docs/GETTING_STARTED.md" in readme_text
    assert "docs/ARCHITECTURE.md" in readme_text
    assert "docs/NEXT_STEP.md" in readme_text
    assert "docs/STATUS.md" in readme_text
    assert "docs/TELEGRAM_BOT_SLIMMING_LOG.md" in readme_text
    assert "docs/DOWNLOAD_COMPLETION_POLLING_LOG.md" in readme_text
    assert "docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md" in readme_text
    assert "docs/FEISHU_LONG_CONNECTION_RISK_LOG.md" in readme_text
    assert "docs/PERSISTENCE_CLOSURE_LOG.md" in readme_text
    assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in readme_text

    assert "docs/STATUS.md" in index_text
    assert "docs/TELEGRAM_BOT_SLIMMING_LOG.md" in index_text
    assert "docs/DOWNLOAD_COMPLETION_POLLING_LOG.md" in index_text
    assert "docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md" in index_text
    assert "docs/FEISHU_LONG_CONNECTION_RISK_LOG.md" in index_text
    assert "docs/PERSISTENCE_CLOSURE_LOG.md" in index_text
    assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in index_text
    assert "STATUS` 只写当前快照" in index_text or "STATUS` 只保留当前快照" in index_text

    assert "docs/STATUS.md" in getting_started_text
    assert "docs/PERSISTENCE_CLOSURE_LOG.md" in getting_started_text

    assert "docs/STATUS.md" in decisions_text
    assert "docs/PERSISTENCE_CLOSURE_LOG.md" in decisions_text
    assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in decisions_text

    assert "docs/INDEX.md" in agents_text
    assert "docs/ARCHITECTURE.md" in agents_text
    assert "docs/NEXT_STEP.md" in agents_text
    assert "docs/DECISIONS.md" in agents_text
    assert "docs/STATUS.md" in agents_text

    assert "telegram_bot.py" in next_step_text and "渠道层瘦身 / 模块化" in next_step_text
    assert "telegram_bot.py" in status_text and "渠道层瘦身 / 模块化" in status_text
    assert "telegram_bot.py" in telegram_bot_slimming_log_text and "渠道层瘦身 / 模块化" in telegram_bot_slimming_log_text
    assert "独立后台下载完成轮询剩余少量回归与验证收口" in download_completion_log_text
    assert "Feishu 私聊事件解析器去重" in feishu_parser_dedupe_log_text
    assert "Feishu 长连接私有 API 风险收口" in feishu_risk_log_text
    assert "持久化吞错收口" in persistence_log_text
    assert "shared private-chat runtime" in architecture_text
    assert "Cleanup verification window" in cleanup_window_text


def test_status_stays_short_snapshot_and_keeps_syncable_entries() -> None:
    status_text = Path("docs/STATUS.md").read_text(encoding="utf-8")

    assert len(status_text) < 20000
    assert "## Project position" in status_text
    assert "## Knowledge entrypoints" in status_text
    assert "## What is implemented now" in status_text
    assert "## Main risks and gaps" in status_text
    assert "## Latest verification" in status_text
    assert "docs/TELEGRAM_BOT_SLIMMING_LOG.md" in status_text
    assert "docs/DOWNLOAD_COMPLETION_POLLING_LOG.md" in status_text
    assert "docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md" in status_text
    assert "docs/FEISHU_LONG_CONNECTION_RISK_LOG.md" in status_text
    assert "docs/PERSISTENCE_CLOSURE_LOG.md" in status_text
    assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in status_text

    for label in STATUS_SNAPSHOT_LABELS:
        assert f"- {label}：" in status_text

    assert "cold-start consistency audit" not in status_text
    assert "bt subscription invalid-kind write guard tests" not in status_text
    assert "search clarification pending persist fail-closed tests" not in status_text
    assert "search candidate persist fail-closed tests" not in status_text
    assert "search clarification clear fail-closed tests" not in status_text


def test_persistence_closure_log_keeps_current_line_detail() -> None:
    log_text = Path("docs/PERSISTENCE_CLOSURE_LOG.md").read_text(encoding="utf-8")

    assert "## 1. Current line" in log_text
    assert "## 2. Recent closed loops" in log_text
    assert "## 3. Focused verification" in log_text
    assert "## 4. Maintenance rule" in log_text

    assert "Fail closed missing downloader approval row" in log_text
    assert "Fail closed missing import approval row" in log_text
    assert "Fail closed search clarification persistence" in log_text
    assert "Fail closed search candidate persistence" in log_text
    assert "Fail closed search clarification clear" in log_text

    assert "search clarification pending persist fail-closed tests" in log_text
    assert "search candidate persist fail-closed tests" in log_text
    assert "search clarification clear fail-closed tests" in log_text


def test_download_completion_polling_log_keeps_completed_line_detail() -> None:
    log_text = Path("docs/DOWNLOAD_COMPLETION_POLLING_LOG.md").read_text(encoding="utf-8")

    assert "## 1. Completed line" in log_text
    assert "## 2. Risk groups" in log_text
    assert "## 3. Focused verification" in log_text
    assert "## 4. Maintenance rule" in log_text

    assert "待轮询列表读取 / fail-closed 边界" in log_text
    assert "轮询启动 / 停机 / 状态查询边界" in log_text
    assert "downloader.completed_observed + auto_import boundary" in log_text
    assert 'tests/test_telegram_bot.py -k "pending_list"' in log_text
    assert 'tests/test_telegram_bot.py -k "download_completion_polling or post_download_auto_import_scheduler"' in log_text


def test_telegram_bot_slimming_log_keeps_current_line_detail() -> None:
    log_text = Path("docs/TELEGRAM_BOT_SLIMMING_LOG.md").read_text(encoding="utf-8")

    assert "## 1. Current line" in log_text
    assert "## 2. Risk groups" in log_text
    assert "## 3. Focused verification" in log_text
    assert "## 4. Maintenance rule" in log_text

    assert "收包回包 / shared runtime wrapper" in log_text
    assert "后台生命周期 / BT pending helper" in log_text
    assert 'tests/test_telegram_bot.py -k "handle_callback_query or build_application"' in log_text
    assert 'tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "post_download_auto_import_scheduler or bt_processing_path or bt_classification or bt_tmdb_association or raw_bt_destination"' in log_text
