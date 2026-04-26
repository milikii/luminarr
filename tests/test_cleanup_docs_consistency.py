from __future__ import annotations

import re
from pathlib import Path


STATUS_SECTION_HEADINGS = (
    "## Current mainline",
    "## Current health",
    "## Latest verification",
    "## Current biggest risk",
    "## Recommended Next Operator Command",
)


def test_docs_entrypoints_are_split_by_reader_role() -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")
    human_start_text = Path("docs/HUMAN_START_HERE.md").read_text(encoding="utf-8")
    runbook_text = Path("docs/OPERATOR_RUNBOOK.md").read_text(encoding="utf-8")
    index_text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    getting_started_text = Path("docs/GETTING_STARTED.md").read_text(encoding="utf-8")
    architecture_text = Path("docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    next_step_text = Path("docs/NEXT_STEP.md").read_text(encoding="utf-8")
    status_text = Path("docs/STATUS.md").read_text(encoding="utf-8")
    decisions_text = Path("docs/DECISIONS.md").read_text(encoding="utf-8")
    slimming_rules_text = Path("docs/SLIMMING_RULES.md").read_text(encoding="utf-8")
    agents_text = Path("AGENTS.md").read_text(encoding="utf-8")

    assert "docs/HUMAN_START_HERE.md" in readme_text
    assert "docs/OPERATOR_RUNBOOK.md" in readme_text
    assert "docs/INDEX.md" in readme_text
    assert "docs/GETTING_STARTED.md" in readme_text
    assert "docs/ARCHITECTURE.md" in readme_text
    assert "docs/STATUS.md" in readme_text
    assert "docs/NEXT_STEP.md" in readme_text
    assert "docs/DECISIONS.md" in readme_text
    assert "docs/SLIMMING_RULES.md" not in readme_text
    assert "再去 `docs/OPERATOR_RUNBOOK.md` 按场景复制一条模板" in readme_text
    assert "直接复制 `docs/STATUS.md` 末尾的 `Recommended Next Operator Command`" in readme_text
    assert "docs/POST_DOWNLOAD_AUTO_IMPORT_SLIMMING_LOG.md" not in readme_text
    assert "docs/BT_REAL_DISPATCH_SMOKE_PLAN.md" not in readme_text

    assert "docs/STATUS.md" in human_start_text
    assert "docs/OPERATOR_RUNBOOK.md" in human_start_text
    assert "docs/GETTING_STARTED.md" in human_start_text
    assert "AGENTS.md" in human_start_text
    assert "不确定文档、最近提交、当前状态有没有漂移" in human_start_text
    assert "这一轮只改文档与 docs gate" in human_start_text
    assert "如果你只想最快继续推进" in human_start_text

    assert "## 0. 怎么选模板" in runbook_text
    assert "只想最快继续当前主线" in runbook_text
    assert "默认 3 轮施工" in runbook_text
    assert "只做冷启动一致性检查" in runbook_text
    assert "只做文档收口，不改业务代码" in runbook_text

    assert "## 1. 如果你是操作者" in index_text
    assert "## 2. 如果你是 AI / 施工代理" in index_text
    assert "## 3. 如果你是开发者 / fork 维护者" in index_text
    assert "## 4. 文档分层" in index_text
    assert "## 5. 文档维护规则" in index_text
    assert "docs/HUMAN_START_HERE.md" in index_text
    assert "docs/OPERATOR_RUNBOOK.md" in index_text
    assert "docs/PERSISTENCE_CLOSURE_LOG.md" in index_text
    assert "先看 `docs/STATUS.md`" in index_text
    assert "Recommended Next Operator Command" in index_text

    assert "docs/HUMAN_START_HERE.md" in getting_started_text
    assert "docs/STATUS.md" in getting_started_text
    assert "docs/OPERATOR_RUNBOOK.md" in getting_started_text

    assert "shared private-chat runtime" in architecture_text
    assert "docs/STATUS.md" in decisions_text
    assert "docs/NEXT_STEP.md" in decisions_text
    assert "docs/INDEX.md" in agents_text
    assert "docs/ARCHITECTURE.md" in agents_text
    assert "docs/NEXT_STEP.md" in agents_text
    assert "docs/DECISIONS.md" in agents_text
    assert "docs/STATUS.md" in agents_text
    assert "Emby / Jellyfin / Plex" in readme_text
    assert "Emby / Jellyfin / Plex" in decisions_text
    assert "保守版减法政策" in slimming_rules_text
    assert "`CODEX_*_PROMPT.md` 视为工具配置" in slimming_rules_text
    assert "60` 行以下的 support/helper 文件" in slimming_rules_text
    assert not Path("docs/CODEX_3_ROUND_PROMPT.md").exists()
    assert not Path("docs/CODEX_LOW_TOKEN_10_ROUND_PROMPT.md").exists()

    assert "shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口" in next_step_text
    assert "质量硬化" in status_text


def test_next_step_stays_compact_and_decision_complete() -> None:
    next_step_text = Path("docs/NEXT_STEP.md").read_text(encoding="utf-8")

    assert len(next_step_text) < 12000
    assert "## Current goal" in next_step_text
    assert "## User value" in next_step_text
    assert "## Only do" in next_step_text
    assert "## Do not do" in next_step_text
    assert "## Done when" in next_step_text
    assert "## After this step" in next_step_text
    assert "app/bot/private_chat_runtime.py" in next_step_text
    assert "telegram_bot.py" in next_step_text
    assert "StatusFollowUpRecorder.record()" not in next_step_text
    assert "当前主线入口继续看" not in next_step_text
    assert "当前快照：" not in next_step_text


def test_status_stays_short_snapshot_and_points_to_operator_flow() -> None:
    status_text = Path("docs/STATUS.md").read_text(encoding="utf-8")

    assert len(status_text) < 6000
    for heading in STATUS_SECTION_HEADINGS:
        assert heading in status_text

    assert re.search(r"\b\d+ passed, \d+ skipped\b", status_text)
    assert "make quality" in status_text
    assert "make verify-mainline" in status_text
    assert "默认继续施工时，直接复制下面这句给 AI：" in status_text
    assert "按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。" in status_text
    assert "docs/CLEANUP_SLIMMING_LOG.md" not in status_text
    assert "docs/BT_REAL_DISPATCH_SMOKE_PLAN.md" not in status_text
    assert "cold-start consistency audit" not in status_text
    assert "git log --oneline -20" not in status_text
    assert "git grep -n 'except Exception" not in status_text
    assert re.search(r"`app/services/search_media\.py` `\d+` 行", status_text)


def test_current_doc_truth_keeps_runtime_lines_and_channel_scope_aligned() -> None:
    next_step_text = Path("docs/NEXT_STEP.md").read_text(encoding="utf-8")
    decisions_text = Path("docs/DECISIONS.md").read_text(encoding="utf-8")
    history_text = Path("docs/HISTORY.md").read_text(encoding="utf-8")

    assert "`app/bot/private_chat_runtime.py` 当前 `476` 行" in next_step_text
    assert "`app/bot/telegram_bot.py` 当前 `276` 行" in next_step_text
    assert "`app/bot/telegram_bot.py` 当前维持在 `276` 行" in decisions_text
    assert "`app/bot/private_chat_runtime.py` 当前维持在 `476` 行" in decisions_text
    assert "代码里已经有 Telegram / personal WeChat / Feishu / WeCom 四个私聊入口" in history_text
    assert "当前仍然只有 Telegram。" not in history_text


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


def test_search_media_slimming_log_keeps_current_line_detail() -> None:
    log_text = Path("docs/SEARCH_MEDIA_SLIMMING_LOG.md").read_text(encoding="utf-8")

    assert "## 1. Completed line" in log_text
    assert "## 2. Risk groups" in log_text
    assert "## 3. Focused verification" in log_text
    assert "## 4. Maintenance rule" in log_text

    assert "query 解析 / TMDB 查询 / 搜索请求编排" in log_text
    assert "歧义澄清 / 候选持久化 / 回复格式化" in log_text
    assert 'tests/test_search_media.py -k "parse_movie_query or tmdb or search_and_format_with_results or search_backend_failure"' in log_text
    assert 'tests/test_search_media.py -k "clarification or candidate or quality_from_title"' in log_text


def test_cleanup_slimming_log_keeps_current_line_detail() -> None:
    log_text = Path("docs/CLEANUP_SLIMMING_LOG.md").read_text(encoding="utf-8")

    assert "## 1. Current line" in log_text
    assert "## 2. Risk groups" in log_text
    assert "## 3. Focused verification" in log_text
    assert "## 4. Maintenance rule" in log_text

    assert "身份解析 / import 关联" in log_text
    assert "inspect / execution 主路径" in log_text
    assert "路径校验 / source 删除 / follow-up / 事件落盘与中文日志" in log_text
    assert 'tests/test_cleanup_downloaded_source.py -k "parse_cleanup_query or parse_cleanup_inspect_query or inspect_by_task_ref or resolves_chat_scoped_task_ref"' in log_text
    assert 'tests/test_cleanup_downloaded_source.py -k "cleanup_by_task_ref or inspect_by_task_ref"' in log_text
    assert 'tests/test_cleanup_downloaded_source.py -k "delete_failure or source_type_unsupported or event_append_failure or missing_appended_event_result"' in log_text


def test_manage_bt_subscription_slimming_log_keeps_completed_line_detail() -> None:
    log_text = Path("docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md").read_text(encoding="utf-8")

    assert "## 1. Completed line" in log_text
    assert "## 2. Risk groups" in log_text
    assert "## 3. Focused verification" in log_text
    assert "## 4. Maintenance rule" in log_text

    assert "清单增删 / 标题解析 / 回复文本" in log_text
    assert "扫描候选筛选 / `last_seen` 更新 / scheduler tick" in log_text
    assert 'tests/test_manage_bt_subscription.py -k "parse_bt_subscription_query or add or list or remove or clear"' in log_text
    assert 'tests/test_manage_bt_subscription.py -k "run_once or scheduler_tick or last_seen"' in log_text


def test_add_to_downloader_slimming_log_keeps_completed_line_detail() -> None:
    log_text = Path("docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md").read_text(encoding="utf-8")

    assert "## 1. Completed line" in log_text
    assert "## 2. Risk groups" in log_text
    assert "## 3. Focused verification" in log_text
    assert "## 4. Maintenance rule" in log_text

    assert "app/services/add_pending_context.py" in log_text
    assert "候选选择 / 来源解析 / 待确认写入" in log_text
    assert "confirm 执行 / 下载监控登记 / 事件落盘" in log_text
    assert 'tests/test_add_to_downloader.py -k "add_by_selection or add_candidate_source or record_pending_approval or record_pending_job"' in log_text
    assert 'tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or register_download_monitor or record_event"' in log_text


def test_import_to_library_slimming_log_keeps_current_line_detail() -> None:
    log_text = Path("docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md").read_text(encoding="utf-8")

    assert "## 1. Completed line" in log_text
    assert "## 2. Risk groups" in log_text
    assert "## 3. Focused verification" in log_text
    assert "## 4. Maintenance rule" in log_text
    assert "app/services/import_context_lookup.py" in log_text
    assert "导入前上下文重建 / raw_bt 判定" in log_text
    assert "执行模式 / copy-fallback / 文件系统导入执行 / metadata / subtitle / refresh 收尾" in log_text
    assert 'tests/test_import_to_library.py -k "context_lookup or context_row_corruption or raw_bt"' in log_text
    assert 'tests/test_import_to_library.py -k "copy_fallback or cross_filesystem or hardlink_failure or metadata_scrape or subtitle_translate or refresh"' in log_text


def test_telegram_bot_slimming_log_keeps_completed_line_detail() -> None:
    log_text = Path("docs/TELEGRAM_BOT_SLIMMING_LOG.md").read_text(encoding="utf-8")

    assert "## 1. Completed line" in log_text
    assert "## 2. Risk groups" in log_text
    assert "## 3. Focused verification" in log_text
    assert "## 4. Maintenance rule" in log_text

    assert "app/bot/telegram_runtime_adapter.py" in log_text
    assert "收包回包 / shared runtime wrapper" in log_text
    assert 'tests/test_telegram_bot.py -k "handle_callback_query or build_application"' in log_text
