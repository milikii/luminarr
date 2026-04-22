# Current status (v403)

## Current mainline

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段切到 **services 层数据结构降本**，Done 定义锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- `import_to_library.py` 前 6 条主线（pipeline 盘点、post_processing、approval_state、job_state、transfer_execution、cancel_state）保持完成态，文件已从 `2242` 行降到 `1392` 行。
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
- 当前唯一主线切回 **`app/services/import_to_library.py` 数据结构重设计 · 第 7 轮 · 评估 prepare import 预检壳`**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1718 passed, 0 skipped`。
- shared runtime / channel 解耦累计 `57+` 条最小直连。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库级 CI：GitHub Actions `Quality` workflow 在 `push` / `pull_request` / `workflow_dispatch` 上运行 `make quality` + `make verify-mainline`，最近一次推送绿灯。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 为 `24 passed`。
- 当前下载链 focused 验证：`tests/test_add_to_downloader.py` 为 `113 passed`。
- 当前真实 downloader confirm smoke：绿灯；本轮真实 Transmission confirm 闭环继续通过。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1718 passed, 0 skipped, 4 warnings`。

## Latest verification

- `quality`：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- add_to_downloader focused：`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py` 为 `113 passed`。
- real add confirm smoke：本轮临时 SQLite + 真实 `19091 Transmission` confirm 闭环继续通过，并显式复验 `add_by_selection -> pending approval/job/event -> has_pending_add -> confirm`。
- real import smoke：`/data/downloads/tr -> /data/library/movies` 真实硬链接 smoke 通过。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1718 passed, 0 skipped, 4 warnings`；补修的 WeCom 真 HTTP 断言已对齐当前 shared runtime 回复协议。
- 当前真实端点探针：`19091 Transmission` 与 `19092 BT Transmission` 都返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`18098 qBittorrent` 当前连接失败。

## Current biggest risk

- shared runtime 层微切分已进入边际递减区：`app/bot/telegram_bot.py` 当前 `256` 行（纯 wrapper 已清空），`app/bot/private_chat_runtime.py` 当前 `468` 行（bootstrap / route block / follow-up / preparation 都已收口），继续在这一层拆分收益有限——这也是 **质量硬化** 阶段 D-039 收工的直接依据。
- 最大结构债仍在 services 两座大山：`app/services/add_to_downloader.py` `608` 行 / `app/services/import_to_library.py` `1392` 行；`app/services/search_media.py` 已降到 `460` 行。
- 风险消除路径：`search_media.py` 已先达标；`add_to_downloader.py` 现在只比 `≤ 600` 多 `8` 行，剩余主要是薄 bridge / wrapper；继续在这座山上硬拆的收益开始下降。当前更值钱也更稳定的下一刀，是把 `import_to_library.py` 里 `_prepare_import()` 那段“下载器查询 -> 完成态判断 -> 源/目标预检 -> 命名真相 -> target exists”预检壳拿走。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的"默认 3 轮施工"执行。
```
