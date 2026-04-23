# Import to library slimming log (v15)

> 目的：承接当前“`import_to_library.py` 导入编排层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Completed line

- 已完成主线：`import_to_library.py` 导入编排层瘦身 / 模块化（已在 2026-04-19 满足 `Done when` 第 1 条：`app/services/import_context_lookup.py` 已承接导入前 confirm 上下文重建 / `raw_bt` 判定边界，且 focused tests `27 passed, 112 deselected`）
- 上一条已完成主线“`telegram_bot.py` 渠道层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线“独立后台下载完成轮询剩余少量回归与验证收口”已完成；详细台账继续只看 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线“Feishu 私聊事件解析器去重”已完成；详细台账继续只看 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线“Feishu 长连接私有 API 风险收口”已完成；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 导入前上下文重建 / raw_bt 判定

本轮收口：
- `app/services/import_context_lookup.py` 现在承接导入前 confirm 上下文重建、approval 读取和 `raw_bt` 判定；`import_to_library.py` 只保留用户入口、fail-closed 中文日志和后续执行编排，不回退 approval、`jobs`、`job_event` 和导入成功真相。
- `app/services/import_raw_bt_guard.py` 已承接 raw_bt lookup / payload fail-closed guard 和中文日志；`import_to_library.py` 现在只保留 `_is_raw_bt_task()` wrapper，不回退 raw_bt 拦截文本、SQLite/jobs 真相或导入协议。
- `app/services/import_confirm_context_guard.py` 已承接 confirm context lookup / approval fail-closed guard 和中文日志；`import_to_library.py` 现在只保留 `_rebuild_confirm_context()` wrapper，不回退 confirm 拦截文本、approval/jobs 真相或导入协议。
- `app/services/import_metadata_title_year.py` 已承接 metadata title/year fallback glue；`import_to_library.py` 现在只保留 `_resolve_metadata_title_year()` wrapper，不回退 metadata 刮削入参、命名真相 fallback 或导入协议。
- `ImportApprovalState.record_pending_approval_with_copy_fallback_reset()` 已承接 pending approval write-through glue；`import_to_library.py` 现在只保留 `_record_pending_approval()` wrapper，不回退 approval、copy-fallback 清理时机或导入协议。
- `app/services/import_pending_write_through_state.py` 已承接 `import_by_task_ref()` 里的 `approval_pending -> pending job -> job_event -> trace -> reply` 顺序控制；`import_to_library.py` 不再直接持有这段待确认写入编排，不回退审批、jobs、`job_event` 或中文日志协议。
- `app/services/import_trace_logger.py` 已承接导入链 pure trace wrapper；`import_to_library.py` 不再直接拼 trace 落盘字段，只保留 helper 调度，不回退 trace 协议。
- `app/services/import_approval_state.py` 已承接 approval pending/approve/restore/executed、stale-check、pending-expired 和导入目标路径回查；`import_to_library.py` 只保留 wrapper 和 confirm 编排，不回退审批协议或 fail-closed 中文日志。
- 这一组收口只动导入前真相重建边界；confirm 协议、pending / expired / stale 边界和现有中文日志保持不变。
- 这一步把 `import_to_library.py` 从 `2094` 行降到 `1827` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 为 `142 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1714 passed, 2 skipped`。
- raw_bt guard 这一步把 `import_to_library.py` 从 `729` 行降到 `684` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "raw_bt or context_lookup or payload_corrupted or query_failed"` 为 `10 passed, 132 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 继续 `142 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1718 passed, 4 warnings`。
- confirm context guard 这一步把 `import_to_library.py` 从 `684` 行降到 `665` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "rebuild_confirm_context or context_lookup or context_row_corruption"` 为 `4 passed, 138 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 继续 `142 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1718 passed, 4 warnings`。
- metadata title-year 这一步把 `import_to_library.py` 从 `665` 行降到 `656` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "resolve_normalized_naming_truth or extract_title_year or metadata_scrape"` 为 `8 passed, 136 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 为 `144 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1720 passed, 4 warnings`。
- pending approval write-through 这一步把 `import_to_library.py` 从 `656` 行降到 `654` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "record_pending_approval or pending_state_unavailable or copy_fallback_pending"` 为 `7 passed, 138 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 为 `145 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1721 passed, 4 warnings`。
- import pending write-through + trace 这一步把 `import_to_library.py` 从 `654` 行降到 `585` 行；`.venv/bin/python -m pytest -q tests/test_import_pending_write_through_state.py tests/test_import_to_library.py -k "import_by_task_ref or record_pending_approval or pending_state_unavailable or copy_fallback_pending"` 为 `48 passed, 100 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 继续 `145 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1724 passed, 4 warnings`，真实 `.venv/bin/python tmp_tests/verify_import_prepare_real_smoke.py` 也已复验 `19091 Transmission -> approval_pending -> pending_approval job -> import.approval_pending`。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "context_lookup or context_row_corruption or raw_bt"`

### 2.2 执行模式 / copy-fallback / 文件系统导入执行 / metadata / subtitle / refresh 收尾

本轮收口：
- `app/services/import_post_processing.py` 已承接 `metadata / subtitle / refresh` 后置链；`import_to_library.py` 现在只保留 `import.succeeded` 事件落盘、reply 文本拼接和 helper 调用，不回退后置动作协议、中文日志或 `job_event` 真相。
- 这一步把 `import_to_library.py` 从 `2242` 行降到 `2094` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 为 `142 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1714 passed, 2 skipped`。
- `app/services/import_job_state.py` 已承接 `jobs` pending/claim/release/complete 状态迁移；`import_to_library.py` 只保留 wrapper 和 confirm 编排，不回退 `jobs` 状态机的中文 fail-closed 日志。
- 这一步把 `import_to_library.py` 从 `1827` 行降到 `1727` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 继续 `142 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1714 passed, 2 skipped`。
- `app/services/import_transfer_execution.py` 已承接 copy-fallback 判定、payload 解析、硬链接 / 复制导入执行和对应中文 fail-closed 日志；`import_to_library.py` 只保留 confirm 编排、approval / jobs 顺序控制和后续 helper 调度，不回退 copy-fallback 协议或导入成功真相。
- 这一步把 `import_to_library.py` 从 `1727` 行降到 `1494` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 为 `142 passed`，`.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py -k "copy_fallback_pending_survives_restart_and_second_confirm_copies"` 为 `1 passed, 110 deselected`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1716 passed, 4 warnings`，真实 `/data/downloads/tr -> /data/library/movies` 硬链接 smoke 也已通过。
- `app/services/import_cancel_state.py` 已承接 `cancel_pending_import()` 的 pending job 查询、lease 读取、approval+job 取消和对应中文 fail-closed 日志；`import_to_library.py` 只保留 public cancel 入口 wrapper，不回退取消协议、SQLite 真相或 `job_event(import.cancelled)` 边界。
- 这一步把 `import_to_library.py` 从 `1494` 行降到 `1392` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "cancel_pending_import or expired_pending_confirm"` 为 `15 passed, 127 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 继续 `142 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1716 passed, 4 warnings`。
- `app/services/import_prepare_state.py` 已承接 `_prepare_import()` 下载器查询、完成态判断、源/目标预检、命名真相与 `target exists` 收口；`import_to_library.py` 现在只保留 `_prepare_import()` / `_resolve_normalized_naming_truth()` wrapper、metadata title/year 解析和 confirm 编排，不回退 hardlink/copy-fallback、metadata、subtitle、refresh 或 `job_event(import.succeeded)` 边界。
- 这一步把 `import_to_library.py` 从 `1392` 行降到 `1087` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "prepare_import or import_by_task_ref or not_found or not_completed or source_missing or target_exists"` 为 `48 passed, 94 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 继续 `142 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1718 passed, 4 warnings`，真实 `/data/downloads/tr -> /data/library/movies` 硬链接 smoke 继续通过。
- `app/services/import_confirm_execution_tail.py` 已承接 `_execute_import()` 之后 imported / pending_copy_approval / failed 三岔收尾；`import_to_library.py` 现在只保留 confirm 前半段 gate、dispatch 调用和 tail helper 编排，不回退 approval executed-version、completed job、copy-fallback 或 `job_event(import.succeeded)` 边界。
- 这一步把 `import_to_library.py` 从 `1087` 行降到 `958` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "confirm_import_by_task_ref or copy_fallback or hardlink_failure or target_exists_during_execute or refresh_exception"` 为 `36 passed, 106 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 继续 `142 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1718 passed, 4 warnings`，真实 `/data/downloads/tr -> /data/library/movies` confirm tail smoke 继续通过。
- `app/services/import_confirm_preparation.py` 已承接 confirm 前半段 context lookup、pending/stale gate、lease claim、lease version 和 approval confirm；`import_to_library.py` 现在只保留 approval_confirmed 事件、dispatch 调用和 tail helper 编排，不回退 approval / jobs / lease/version、copy-fallback 或 `job_event(import.succeeded)` 边界。
- 这一步把 `import_to_library.py` 从 `958` 行降到 `800` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "confirm_import_by_task_ref or state_unavailable or stale or claim_lease or approval_update"` 为 `46 passed, 96 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 继续 `142 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1718 passed, 4 warnings`，真实 `/data/downloads/tr -> /data/library/movies` confirm preparation smoke 继续通过。
- `app/services/import_confirm_expiry_state.py` 已承接 `_handle_expired_pending_confirm()` 里的 approval cancel、pending job cancel、copy-fallback cleanup 和 `import.approval_expired` 事件；`import_to_library.py` 现在只保留 expiry helper 调用，不回退 approval / jobs 超时真相、cleanup 或 expired 文本边界。
- 这一步把 `import_to_library.py` 从 `800` 行降到 `742` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "expired_pending_confirm or expiry_lookup or cancel_pending_import or confirm_import_by_task_ref_rejects_expired_pending"` 为 `17 passed, 125 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 继续 `142 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1718 passed, 4 warnings`，真实 `/data/downloads/tr` confirm expiry smoke 继续通过。
- `app/services/import_event_recorder.py` 已承接导入链 `job_event` append、回读异常和中文失败日志；`import_to_library.py` 现在只保留 `_record_event()` wrapper，不回退 `job_event` 真相、事件类型或失败日志边界。
- 这一步把 `import_to_library.py` 从 `742` 行降到 `729` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "record_event or confirm_import_by_task_ref or approval_expired or raw_bt"` 为 `45 passed, 97 deselected`，`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 继续 `142 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1718 passed, 4 warnings`，真实 `/data/downloads/tr -> /data/library/movies` event recorder smoke 继续通过。

剩余风险：
- context / approval / jobs / file-transfer / cancel / prepare / execution-tail / confirm-gate / confirm-expiry / event-recorder / raw_bt-guard / confirm-context-guard / metadata-title-year / pending-approval-write-through / trace wrapper 十五段都已离开主文件；`import_to_library.py` 已到 `585` 行并满足 `≤ 600`。
- 导入链当前不再为了行数继续硬拆；只有出现新的 focused gate 价值或新的失败边界，才允许再动 `import_to_library.py`。当前唯一主线已切去 `add_to_downloader.py` 最后 `8` 行 worth-it 复评估。
- 这一组继续守住“导入成功是真相，metadata / subtitle / refresh 失败不回滚导入成功”的边界，并保持显式中文日志 + `[处理建议]`。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "copy_fallback or cross_filesystem or hardlink_failure or metadata_scrape or subtitle_translate or refresh"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "context_lookup or context_row_corruption or raw_bt"`
- `.venv/bin/python -m pytest -q tests/test_import_pending_write_through_state.py tests/test_import_to_library.py -k "import_by_task_ref or record_pending_approval or pending_state_unavailable or copy_fallback_pending"`
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "copy_fallback or cross_filesystem or hardlink_failure or metadata_scrape or subtitle_translate or refresh"`
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "cancel_pending_import or expired_pending_confirm"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- `import_to_library.py` 已满足 `≤ 600`；本文件继续承接 import 已完成闭环的详细台账，当前唯一主线已切去 downloader 侧最后 `8` 行 worth-it 复评估。
