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
    assert "docs/TEST_ENV.md" not in human_start_text
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
    assert "archive/docs/" in index_text
    assert "docs/TEST_ENV.md" not in index_text
    assert "先看 `docs/STATUS.md`" in index_text
    assert "Recommended Next Operator Command" in index_text

    assert "docs/HUMAN_START_HERE.md" in getting_started_text
    assert "docs/STATUS.md" in getting_started_text
    assert "docs/OPERATOR_RUNBOOK.md" in getting_started_text
    assert "docs/TEST_ENV.md" not in getting_started_text

    assert "shared private-chat runtime" in architecture_text
    assert "docs/STATUS.md" in decisions_text
    assert "docs/NEXT_STEP.md" in decisions_text
    assert "docs/INDEX.md" in agents_text
    assert "docs/ARCHITECTURE.md" in agents_text
    assert "docs/NEXT_STEP.md" in agents_text
    assert "docs/DECISIONS.md" in agents_text
    assert "docs/STATUS.md" in agents_text
    assert "docs/TEST_ENV.md" not in decisions_text
    assert "Emby / Jellyfin / Plex" in readme_text
    assert "Emby / Jellyfin / Plex" in decisions_text
    assert "保守版减法政策" in slimming_rules_text
    assert "`CODEX_*_PROMPT.md`、`*_PROMPTS.md` 这类纯工具提示词文件视为工具配置" in slimming_rules_text
    assert "60` 行以下的 support/helper 文件" in slimming_rules_text
    assert not Path("docs/CODEX_3_ROUND_PROMPT.md").exists()
    assert not Path("docs/CODEX_LOW_TOKEN_10_ROUND_PROMPT.md").exists()
    assert not Path("docs/RELEASE_PREP_PROMPTS.md").exists()

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
    assert re.search(r"`cleanup_\*_support\.py` .*6", status_text)


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


def test_archived_history_docs_are_moved_out_of_active_docs_root() -> None:
    archived = (
        "ADD_TO_DOWNLOADER_SLIMMING_LOG.md",
        "APP_MAIN_SLIMMING_LOG.md",
        "BT_BATCH_PLAN.md",
        "BT_PAGE_RANGE_PLAN.md",
        "BT_REAL_DISPATCH_SMOKE_PLAN.md",
        "BT_SCORING_LOG.md",
        "BT_SCORING_PLAN.md",
        "CLEANUP_SLIMMING_LOG.md",
        "DOWNLOAD_COMPLETION_POLLING_LOG.md",
        "FEISHU_EVENT_PARSER_DEDUPE_LOG.md",
        "FEISHU_LONG_CONNECTION_RISK_LOG.md",
        "GET_DOWNLOAD_STATUS_SLIMMING_LOG.md",
        "IMPORT_TO_LIBRARY_SLIMMING_LOG.md",
        "IMPORT_PIPELINE_REDESIGN.md",
        "JELLYFIN_PLEX_PLAN.md",
        "JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md",
        "JELLYFIN_REAL_VERIFICATION_PLAN.md",
        "MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md",
        "POST_DOWNLOAD_AUTO_IMPORT_SLIMMING_LOG.md",
        "PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md",
        "PT_LIVE_SEEDING_PLAN.md",
        "QUICK_START_PLAN.md",
        "RELEASE_PREP_PLAN.md",
        "SEARCH_MEDIA_SLIMMING_LOG.md",
        "SCRAPING_SYSTEM_PLAN.md",
        "SERIES_ANIME_NAMING_LOG.md",
        "SERIES_ANIME_NAMING_PLAN.md",
        "SHARED_DELIVERY_UX_LOG.md",
        "SHARED_DELIVERY_UX_PLAN.md",
        "TELEGRAM_BOT_SLIMMING_LOG.md",
        "VERIFICATION_ENTRYPOINTS_PLAN.md",
    )

    for name in archived:
        assert not Path("docs", name).exists()
        assert Path("archive", "docs", name).exists()


def test_active_docs_root_stays_small_and_current() -> None:
    active_docs = sorted(path.name for path in Path("docs").glob("*.md"))

    assert len(active_docs) <= 15
    assert not any(name.endswith("_SLIMMING_LOG.md") for name in active_docs)
    assert "SEARCH_REPLY_PRESENTATION_PLAN.md" in active_docs
    assert "STATUS.md" in active_docs
    assert "NEXT_STEP.md" in active_docs
    assert "TEST_ENV.md" not in active_docs
