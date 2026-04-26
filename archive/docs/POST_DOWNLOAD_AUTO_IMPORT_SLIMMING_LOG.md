# docs/POST_DOWNLOAD_AUTO_IMPORT_SLIMMING_LOG.md (v1)

> 目的：承接当前“`post_download_auto_import.py` 自动导入编排层瘦身 / 模块化”主线的详细台账。

## 1. Current line

- 当前主线状态：`post_download_auto_import.py` 自动导入编排层瘦身 / 模块化已完成。
- 上一条已完成主线 **`get_download_status.py` 状态编排层瘦身 / 模块化** 已在 2026-04-20 满足 `Done when` 第 1、2 条：状态展示 helper 已独立到 `app/services/status_delivery.py`，观察落盘 / 完成事件 / 自动导入 follow-up 已独立到 `app/services/status_follow_up.py`，相关 focused tests 已全绿。
- 2026-04-20 当前批次已满足 `docs/NEXT_STEP.md` `Done when` 第 1 条：`run_once()` 只保留候选扫描与计数编排，候选读取 / 逐条任务推进 helper 已独立到 `app/services/auto_import_batch.py`，focused tests `8 passed, 34 deselected`，扩展自动导入 / 状态 follow-up focused tests `21 passed, 21 deselected`。

## 2. Risk groups

### 2.1 候选读取 / 逐条任务编排

- `run_once()` 现在只保留扫描数量、`progressed` 统计和 `state_unavailable` 汇总；批量候选读取 / 逐条推进已收口到 `app/services/auto_import_batch.py`。
- 已完成候选读取失败 / 结果缺失 / 记录损坏时的显式中文日志边界保持不变。

### 2.2 终态判断 / skip-event / 自动导入 dispatch

- 保持 `_has_terminal_activity()`、`_record_skip_event()`、`run_for_record()` 的调用顺序和 fail-closed 边界不回退。
- 保持低质量规则跳过、`AUTO_IMPORT_SKIPPED_BY_RULE_EVENT`、`AutoImportStateUnavailableError` 语义不变。

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_get_download_status.py -k "download_monitor or completion_event or auto_import_terminal or skip_event"`
- `.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py tests/test_telegram_bot.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py -k "status"`

## 4. Maintenance rule

- 新闭环优先并到这份台账的现有风险分组，不新开按日期拆的小节。
- 当前主线已完成；下一次施工按 `docs/NEXT_STEP.md` 的 `After this step` 第 1 项切到 `download_monitor_repo.py` / `job_event` 共享状态 helper 值得性评估。
- 若某次施工只是在同一个 helper 上补一条 `< 20 行` 的 `if/elif/log` 诊断分支，且上一轮也是同类微闭环，就按 `AGENTS.md §11` 触发诊断分流递减停机。
