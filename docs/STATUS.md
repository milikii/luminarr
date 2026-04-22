# Current status (v412)

## Current mainline

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 收工；当前阶段继续做 **services 层数据结构降本**，Done 仍锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- `import_to_library.py` 前 6 条主线保持完成态，文件已从 `2242` 行降到 `1392` 行。
- 当前阶段第 7 条主线已完成：`app/services/add_execution_follow_up.py` 已承接 confirm 执行 / 下载监控登记 / 事件落盘 helper，`add_to_downloader.py` 已从 `1669` 行降到 `1549` 行。
- 当前阶段第 8 条主线已完成：`app/services/add_cancel_state.py` 已承接 `cancel_pending_add()` 的 pending lookup / lease / approval+job cancel / fail-closed 中文日志，`add_to_downloader.py` 已从 `1549` 行降到 `1399` 行。
- 当前阶段第 9 条主线已完成：`app/services/search_reply_formatter.py` 已承接 movie reply / delivery item / BT 只读与批量预览回复拼装，`search_media.py` 已从 `1018` 行降到 `725` 行。
- 当前阶段第 10 条主线已完成：`app/services/search_clarification_state.py` 已承接 clarification pending / clear / persisted load 状态 helper，`search_media.py` 已从 `725` 行降到 `616` 行。
- 当前阶段第 11 条主线已完成：`app/services/search_candidate_state.py` 已承接 candidate save / load / rollback helper，`search_media.py` 已从 `616` 行降到 `460` 行，并率先达到 `≤ 600` 目标。
- 当前阶段第 12 条主线已完成：`app/services/add_confirm_job_state.py` 已承接 confirm jobs 抢占 / 回退 / 完结与 lease owner helper，`add_to_downloader.py` 已从 `1399` 行降到 `1315` 行。
- 当前阶段第 13 条主线已完成：`app/services/add_confirm_approval_state.py` 已承接 approval / lease 查询、stale-check 和 pending expiry helper，`add_to_downloader.py` 已从 `1315` 行降到 `1235` 行。
- 当前阶段第 14 条主线已完成：`app/services/add_confirm_context_state.py` 已承接 confirm context rebuild / expired confirm 收口，`add_to_downloader.py` 已从 `1235` 行降到 `1117` 行。
- 当前阶段第 15 条主线已完成：`app/services/add_confirm_approval_state.py` 已继续承接 pending approval 写入 / approve / restore / cancel / executed-version 回写，`add_to_downloader.py` 已从 `1117` 行降到 `937` 行。
- 当前阶段第 16 条主线已完成：`app/services/add_confirm_approval_state.py` 已继续承接 approval identity move，`tests/test_add_to_downloader.py` 新增 identity move warning guard，`add_to_downloader.py` 已从 `937` 行降到 `927` 行。
- 当前阶段第 17 条主线已完成：`app/services/add_confirm_finalization_state.py` 已承接 confirm 成功后的 warning 汇总 / job completion 尾部回写 / pending context 清理 / finalize trace，`add_to_downloader.py` 已从 `927` 行降到 `892` 行。
- 当前阶段第 18 条主线已完成：`app/services/add_pending_context.py` 已继续承接进程内 pending context 记录 / 查询 / 清理 / 缺失日志 helper，`add_to_downloader.py` 已从 `892` 行降到 `866` 行。
- 当前阶段第 19 条主线已完成：`app/services/add_trace_logger.py` 已承接下载链 pure trace wrapper，`add_to_downloader.py` 已从 `866` 行降到 `838` 行。
- 当前阶段第 20 条主线已完成：`app/services/add_pending_persistence.py` 已承接 pending job 落盘失败分流和待确认回复渲染，`add_to_downloader.py` 已从 `838` 行降到 `787` 行。
- 当前阶段第 21 条主线已完成：`app/services/add_request_facade.py` 已承接 add request 入口 facade，`add_to_downloader.py` 已从 `787` 行降到 `763` 行。
- 当前阶段第 22 条主线已完成：`app/services/add_confirm_preparation.py` 已承接 confirm 前置状态准备，`add_to_downloader.py` 已从 `763` 行降到 `698` 行。
- 当前阶段第 23 条主线已完成：`app/services/add_confirm_execution_tail.py` 已承接 confirm execution tail，`add_to_downloader.py` 已从 `698` 行降到 `674` 行。
- 当前阶段第 24 条主线已完成：`app/services/add_confirm_availability_state.py` 已承接 confirm availability 壳，`add_to_downloader.py` 已从 `674` 行降到 `644` 行。
- 当前阶段第 25 条主线已完成：`app/services/add_pending_presence_state.py` 已承接 `has_pending_add()` 的 pending presence lookup 壳，`add_to_downloader.py` 已从 `644` 行降到 `627` 行。
- 当前阶段第 26 条主线已完成：`app/services/add_pending_write_through_state.py` 已承接 `_persist_pending_add()` 的 pending write-through 壳，`add_to_downloader.py` 已从 `627` 行降到 `608` 行。
- 当前阶段第 27 条主线已完成：`app/services/import_prepare_state.py` 已承接 `_prepare_import()` 下载器查询、完成态判断、源/目标预检、命名真相与 `target exists` 收口，`import_to_library.py` 已从 `1392` 行降到 `1087` 行。
- 当前阶段第 28 条主线已完成：`app/services/import_confirm_execution_tail.py` 已承接 imported / pending_copy_approval / failed 三岔收尾，`import_to_library.py` 已从 `1087` 行降到 `958` 行。
- 当前阶段第 29 条主线已完成：`app/services/import_confirm_preparation.py` 已承接 confirm 前半段 context / stale / lease / approval gate，`import_to_library.py` 已从 `958` 行降到 `800` 行。
- 当前阶段第 30 条主线已完成：`app/services/import_confirm_expiry_state.py` 已承接 confirm 过期分支的 approval cancel / pending job cancel / cleanup / expired event，`import_to_library.py` 已从 `800` 行降到 `742` 行。
- 当前阶段第 31-35 条主线已完成：`import_event_recorder.py`、`import_raw_bt_guard.py`、`import_confirm_context_guard.py`、`import_metadata_title_year.py` 和 `ImportApprovalState.record_pending_approval_with_copy_fallback_reset()` 已承接最近 5 组导入 glue，`import_to_library.py` 已从 `742` 行降到 `654` 行。
- 主线：**`services 层数据结构降本 · 剩余 thin wrapper worth-it 复评估`**。
- 默认分支本轮全量回归继续绿灯：`.venv/bin/python -m pytest -q` 为 `1718 passed, 0 skipped`。

## Current health

- 仓库级 CI：`make quality` / `make verify-mainline` 绿灯。
- 快速质量入口：绿灯；本次 `quality` 为 `24 passed`。
- 导入链 focused：pending-approval focused 为 `7 passed, 138 deselected`；`tests/test_import_to_library.py` 为 `145 passed`。
- 真实 import smoke：最新已知绿灯。
- 全量回归：绿灯；`.venv/bin/python -m pytest -q` 为 `1718 passed, 0 skipped, 4 warnings`。

## Latest verification

- `quality`：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- import_to_library focused：`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "record_pending_approval or pending_state_unavailable or copy_fallback_pending"` 为 `7 passed, 138 deselected`；`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 为 `145 passed`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1721 passed, 0 skipped, 4 warnings`。

## Current biggest risk

- shared runtime 层微切分已进入边际递减区：`app/bot/telegram_bot.py` `256` 行，`app/bot/private_chat_runtime.py` `468` 行，继续在这一层拆分收益有限。
- 最大结构债仍在 services 两座大山：`app/services/add_to_downloader.py` `608` 行 / `app/services/import_to_library.py` `654` 行；`app/services/search_media.py` 已降到 `460` 行。
- 风险消除路径：`search_media.py` 已先达标；`add_to_downloader.py` 现在只比 `≤ 600` 多 `8` 行；`import_to_library.py` 剩余块已接近 thin wrapper 边界，下一轮先做 worth-it 复评估。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的"默认 3 轮施工"执行。
```
