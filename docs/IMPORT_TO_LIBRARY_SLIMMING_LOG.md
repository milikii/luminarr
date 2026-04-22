# Import to library slimming log (v7)

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
- `app/services/import_approval_state.py` 已承接 approval pending/approve/restore/executed、stale-check、pending-expired 和导入目标路径回查；`import_to_library.py` 只保留 wrapper 和 confirm 编排，不回退审批协议或 fail-closed 中文日志。
- 这一组收口只动导入前真相重建边界；confirm 协议、pending / expired / stale 边界和现有中文日志保持不变。
- 这一步把 `import_to_library.py` 从 `2094` 行降到 `1827` 行；`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 为 `142 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1714 passed, 2 skipped`。

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

剩余风险：
- context / approval / jobs / file-transfer / cancel / prepare / execution-tail 七段都已离开主文件；当前剩余最大块集中在 `confirm_import_by_task_ref()` 前半段的 context lookup、pending/stale gate、lease claim、lease version 和 approval confirm。
- 下一步优先评估 confirm approval gate 壳；只动 `_execute_import()` 之前的 context / stale / lease / approval gate，不回退 hardlink/copy-fallback、metadata、subtitle 或 refresh 协议。
- 这一组继续守住“导入成功是真相，metadata / subtitle / refresh 失败不回滚导入成功”的边界，并保持显式中文日志 + `[处理建议]`。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "copy_fallback or cross_filesystem or hardlink_failure or metadata_scrape or subtitle_translate or refresh"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "context_lookup or context_row_corruption or raw_bt"`
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "copy_fallback or cross_filesystem or hardlink_failure or metadata_scrape or subtitle_translate or refresh"`
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "cancel_pending_import or expired_pending_confirm"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前唯一主线已切到 confirm approval gate；本文件继续承接 import 微切分详细台账，不回到 dated 小节堆叠。
