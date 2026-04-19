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
    cleanup_slimming_log_text = Path("docs/CLEANUP_SLIMMING_LOG.md").read_text(encoding="utf-8")
    manage_bt_subscription_slimming_log_text = Path("docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md").read_text(
        encoding="utf-8"
    )
    search_media_slimming_log_text = Path("docs/SEARCH_MEDIA_SLIMMING_LOG.md").read_text(encoding="utf-8")
    add_to_downloader_slimming_log_text = Path("docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md").read_text(encoding="utf-8")
    import_to_library_slimming_log_text = Path("docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md").read_text(encoding="utf-8")
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
    assert "docs/CLEANUP_SLIMMING_LOG.md" in readme_text
    assert "docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md" in readme_text
    assert "docs/SEARCH_MEDIA_SLIMMING_LOG.md" in readme_text
    assert "docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md" in readme_text
    assert "docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md" in readme_text
    assert "docs/TELEGRAM_BOT_SLIMMING_LOG.md" in readme_text
    assert "docs/DOWNLOAD_COMPLETION_POLLING_LOG.md" in readme_text
    assert "docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md" in readme_text
    assert "docs/FEISHU_LONG_CONNECTION_RISK_LOG.md" in readme_text
    assert "docs/PERSISTENCE_CLOSURE_LOG.md" in readme_text
    assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in readme_text

    assert "docs/STATUS.md" in index_text
    assert "docs/CLEANUP_SLIMMING_LOG.md" in index_text
    assert "docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md" in index_text
    assert "docs/SEARCH_MEDIA_SLIMMING_LOG.md" in index_text
    assert "docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md" in index_text
    assert "docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md" in index_text
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

    assert "docs/CLEANUP_SLIMMING_LOG.md" in next_step_text
    assert "docs/CLEANUP_SLIMMING_LOG.md" in status_text
    assert "cleanup_downloaded_source.py" in cleanup_slimming_log_text and "cleanup 编排层瘦身 / 模块化" in cleanup_slimming_log_text
    assert "manage_bt_subscription.py" in manage_bt_subscription_slimming_log_text and "订阅编排层瘦身 / 模块化" in manage_bt_subscription_slimming_log_text
    assert "search_media.py" in search_media_slimming_log_text and "搜索编排层瘦身 / 模块化" in search_media_slimming_log_text
    assert "add_to_downloader.py" in add_to_downloader_slimming_log_text and "下载编排层瘦身 / 模块化" in add_to_downloader_slimming_log_text
    assert "import_to_library.py" in import_to_library_slimming_log_text and "导入编排层瘦身 / 模块化" in import_to_library_slimming_log_text
    assert "telegram_bot.py" in telegram_bot_slimming_log_text and "渠道层瘦身 / 模块化" in telegram_bot_slimming_log_text
    assert "独立后台下载完成轮询剩余少量回归与验证收口" in download_completion_log_text
    assert "Feishu 私聊事件解析器去重" in feishu_parser_dedupe_log_text
    assert "Feishu 长连接私有 API 风险收口" in feishu_risk_log_text
    assert "持久化吞错收口" in persistence_log_text
    assert "shared private-chat runtime" in architecture_text
    assert "Cleanup verification window" in cleanup_window_text


def test_current_completion_state_docs_do_not_regress() -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")
    index_text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    getting_started_text = Path("docs/GETTING_STARTED.md").read_text(encoding="utf-8")
    architecture_text = Path("docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    bt_batch_plan_text = Path("docs/BT_BATCH_PLAN.md").read_text(encoding="utf-8")
    jellyfin_plex_plan_text = Path("docs/JELLYFIN_PLEX_PLAN.md").read_text(encoding="utf-8")
    next_step_text = Path("docs/NEXT_STEP.md").read_text(encoding="utf-8")
    status_text = Path("docs/STATUS.md").read_text(encoding="utf-8")
    decisions_text = Path("docs/DECISIONS.md").read_text(encoding="utf-8")
    agents_text = Path("AGENTS.md").read_text(encoding="utf-8")

    for text in (readme_text, status_text, decisions_text, agents_text):
        assert "Emby / Jellyfin / Plex" in text

    assert "Emby / Jellyfin / Plex" in architecture_text
    assert "Jellyfin / Plex" in next_step_text
    assert "BT 批量任务最小预览" in readme_text
    assert "BT 批量任务最小预览" in status_text
    assert "BT 批量任务最小预览" in next_step_text
    assert "BT 批量任务最小预览" in agents_text
    assert "当前没有进行中的 promoted 主线" not in readme_text
    assert "当前没有进行中的 promoted 主线" not in status_text
    assert "当前没有进行中的 promoted 主线" not in next_step_text
    assert "当前切线规则与下一条主线入口" in readme_text
    assert "详细目标与可测量退出条件" not in readme_text
    assert "docs/BT_BATCH_PLAN.md" in readme_text
    assert "docs/BT_BATCH_PLAN.md" in index_text
    assert "docs/BT_BATCH_PLAN.md" in agents_text
    assert "docs/PT_LIVE_SEEDING_PLAN.md" in readme_text
    assert "docs/PT_LIVE_SEEDING_PLAN.md" in next_step_text
    assert "只读，不会 dispatch 下载器" in bt_batch_plan_text
    assert "不做批量 approval / 批量 `confirm`" in bt_batch_plan_text
    assert "范围非法、为空或越界" in bt_batch_plan_text
    assert "当前主线已满足 `Done when` 第 1 条" in jellyfin_plex_plan_text
    assert "plugin 体系后置" in jellyfin_plex_plan_text
    assert "进入 Phase 3 前的最后一个最小闭环是 **Plex refresh baseline**" in jellyfin_plex_plan_text
    assert "当前这份蓝图只保留完成态入口和阶段轨迹，不再作为新的进行中施工计划" in jellyfin_plex_plan_text
    assert "当前最小下一步切到 Phase 3" not in jellyfin_plex_plan_text
    assert "docs/JELLYFIN_PLEX_PLAN.md" in agents_text
    assert "docs/JELLYFIN_PLEX_PLAN.md" in index_text
    assert "docs/JELLYFIN_PLEX_PLAN.md" in getting_started_text
    assert "当前完成态主线说明优先收口到 `docs/JELLYFIN_PLEX_PLAN.md`" in index_text
    assert "当前主线蓝图" in readme_text
    assert "Jellyfin / Plex 并行主线支持（当前不做，后续再补）" not in readme_text
    assert "`docs/BT_SCORING_PLAN.md`：当前主线蓝图" not in readme_text
    assert "最小人类可用入口继续补齐**" not in agents_text


def test_status_stays_short_snapshot_and_keeps_syncable_entries() -> None:
    status_text = Path("docs/STATUS.md").read_text(encoding="utf-8")

    assert len(status_text) < 20000
    assert "## Project position" in status_text
    assert "## Knowledge entrypoints" in status_text
    assert "## What is implemented now" in status_text
    assert "## Main risks and gaps" in status_text
    assert "## Latest verification" in status_text
    assert "docs/CLEANUP_SLIMMING_LOG.md" in status_text
    assert "docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md" in status_text
    assert "docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md" in status_text
    assert "docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md" in status_text
    assert "docs/TELEGRAM_BOT_SLIMMING_LOG.md" in status_text
    assert "docs/DOWNLOAD_COMPLETION_POLLING_LOG.md" in status_text
    assert "docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md" in status_text
    assert "docs/FEISHU_LONG_CONNECTION_RISK_LOG.md" in status_text
    assert "docs/SEARCH_MEDIA_SLIMMING_LOG.md" in status_text
    assert "docs/PERSISTENCE_CLOSURE_LOG.md" in status_text
    assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in status_text

    for label in STATUS_SNAPSHOT_LABELS:
        assert f"- {label}：" in status_text

    assert "cold-start consistency audit" not in status_text
    assert "git log --oneline -20" not in status_text
    assert "git grep -n 'except Exception" not in status_text
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


def test_import_to_library_slimming_log_keeps_completed_line_detail() -> None:
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
