# Current status (v397)

## Current mainline

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段切到 **services 层数据结构降本**，Done 定义锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 当前阶段第 1 条主线已完成：`docs/IMPORT_PIPELINE_REDESIGN.md` 已固化 `import_to_library.py` 的入口路径、`if/elif/except` 分支密度和候选 pipeline 草图。
- 当前阶段第 2 条主线已完成：`app/services/import_post_processing.py` 已承接 `metadata / subtitle / refresh` 后置链，`import_to_library.py` 已从 `2242` 行降到 `2094` 行。
- 当前阶段第 3 条主线已完成：`app/services/import_approval_state.py` 已承接 approval lease/version、stale-check、expiry 和目标路径回查，`import_to_library.py` 已从 `2094` 行降到 `1827` 行。
- 当前阶段第 4 条主线已完成：`app/services/import_job_state.py` 已承接 `jobs` pending/claim/release/complete 状态迁移，`import_to_library.py` 已从 `1827` 行降到 `1727` 行。
- 当前阶段第 5 条主线已完成：`app/services/import_transfer_execution.py` 已承接 copy-fallback 判定 / payload 解析 / 文件系统导入执行，`import_to_library.py` 已从 `1727` 行降到 `1494` 行。
- 当前阶段第 6 条主线已完成：`app/services/import_cancel_state.py` 已承接 `cancel_pending_import()` 的 pending job 查询 / lease 读取 / approval+job 取消 / fail-closed 中文日志，`import_to_library.py` 已从 `1494` 行降到 `1392` 行。
- 当前阶段第 7 条主线已完成：`app/services/add_execution_follow_up.py` 已承接 confirm 执行 / 下载监控登记 / 事件落盘 helper，`add_to_downloader.py` 已从 `1669` 行降到 `1549` 行。
- 当前阶段第 8 条主线已完成：`app/services/add_cancel_state.py` 已承接 `cancel_pending_add()` 的 pending lookup / lease / approval+job cancel / fail-closed 中文日志，`add_to_downloader.py` 已从 `1549` 行降到 `1399` 行。
- 当前阶段第 9 条主线已完成：`app/services/search_reply_formatter.py` 已承接 movie reply / delivery item / BT 只读与批量预览回复拼装，`search_media.py` 已从 `1018` 行降到 `725` 行。
- 当前阶段第 10 条主线已完成：`app/services/search_clarification_state.py` 已承接 clarification pending / clear / persisted load 状态 helper，`search_media.py` 已从 `725` 行降到 `616` 行。
- 当前阶段第 11 条主线已完成：`app/services/search_candidate_state.py` 已承接 candidate save / load / rollback helper，`search_media.py` 已从 `616` 行降到 `460` 行，并率先达到 `≤ 600` 目标。
- 当前阶段第 12 条主线已完成：`app/services/add_confirm_job_state.py` 已承接 confirm jobs 抢占 / 回退 / 完结与 lease owner helper，`add_to_downloader.py` 已从 `1399` 行降到 `1315` 行。
- 当前阶段第 13 条主线已完成：`app/services/add_confirm_approval_state.py` 已承接 approval / lease 查询、stale-check 和 pending expiry helper，`add_to_downloader.py` 已从 `1315` 行降到 `1235` 行。
- 当前阶段第 14 条主线已完成：`app/services/add_confirm_context_state.py` 已承接 confirm context rebuild / expired confirm 收口，`add_to_downloader.py` 已从 `1235` 行降到 `1117` 行。
- 当前唯一主线切到 **`app/services/add_to_downloader.py` 数据结构重设计 · 第 12 轮 · 评估 pending approval persistence helper`**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1716 passed, 0 skipped`。
- shared runtime / channel 解耦已累计完成 `57+` 条最小直连；刚完成的上一条主线是 `private_chat_runtime.py` execution gate preparation 收口。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库级 CI：GitHub Actions `Quality` workflow 在 `push` / `pull_request` / `workflow_dispatch` 上运行 `make quality` + `make verify-mainline`，最近一次推送绿灯。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 为 `24 passed`。
- 当前 downloader approval / lease helper focused 验证：`tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or handle_expired_pending_confirm or resolve_pending_lease_version or stale_rejection or pending_approval_expired"` 为 `46 passed, 65 deselected`。
- 当前真实 downloader confirm smoke：绿灯；本轮临时脚本已用本机 `19091 Transmission` 跑通“待确认 -> confirm -> Transmission RPC -> SQLite 真相 -> 删除测试任务”闭环。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1716 passed, 0 skipped, 4 warnings`。

## Latest verification

- `quality`：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- downloader approval / lease helper focused：`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or handle_expired_pending_confirm or resolve_pending_lease_version or stale_rejection or pending_approval_expired"` 为 `46 passed, 65 deselected`。
- real add confirm smoke：本轮临时脚本直连 `http://127.0.0.1:19091/transmission/rpc`，完成“待确认 -> confirm -> `job_event` / `download_monitor` / `approval_record` / `jobs` 真相校验 -> 删除测试任务”闭环。
- real import smoke：`/data/downloads/tr -> /data/library/movies` 真实硬链接 smoke 通过。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1716 passed, 0 skipped, 4 warnings`；补修的 WeCom 真 HTTP 断言已对齐当前 shared runtime 回复协议。
- 当前真实端点探针：`19091 Transmission` 与 `19092 BT Transmission` 都返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`18098 qBittorrent` 当前连接失败。

## Current biggest risk

- shared runtime 层微切分已进入边际递减区：`app/bot/telegram_bot.py` 当前 `256` 行（纯 wrapper 已清空），`app/bot/private_chat_runtime.py` 当前 `468` 行（bootstrap / route block / follow-up / preparation 都已收口），继续在这一层拆分收益有限——这也是 **质量硬化** 阶段 D-039 收工的直接依据。
- 当前最大结构债仍在 services 层两座大山：`app/services/add_to_downloader.py` `1117` 行 / `app/services/import_to_library.py` `1392` 行；`app/services/search_media.py` 已降到 `460` 行。
- 风险消除路径：`search_media.py` 已先达标；`add_to_downloader.py` 的 jobs 状态机、approval / lease 查询和 confirm context / expiry 收口都已拆出，当前最厚也最危险的是 pending approval persistence 编排和 `import_to_library.py` 的剩余执行编排壳。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的"默认 3 轮施工"执行。
```
