# Next step (v311)

## Current goal

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段继续做 **services 层数据结构降本**，Done 定义仍锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 当前阶段第 1 条主线已完成：**`app/services/import_to_library.py` 数据结构重设计 · 第 1 轮 · 路径与特殊分支清单** 已落到 `docs/IMPORT_PIPELINE_REDESIGN.md`。
- 当前阶段第 2 条主线已完成：**`app/services/import_post_processing.py` 已承接 `metadata / subtitle / refresh` 后置链**，`import_to_library.py` 已从 `2242` 行降到 `2094` 行。
- 当前阶段第 3 条主线已完成：**`app/services/import_approval_state.py` 已承接 approval lease/version、stale-check、expiry 和目标路径回查**，`import_to_library.py` 已从 `2094` 行降到 `1827` 行。
- 当前阶段第 4 条主线已完成：**`app/services/import_job_state.py` 已承接 `jobs` pending/claim/release/complete 状态迁移**，`import_to_library.py` 已从 `1827` 行降到 `1727` 行。
- 当前阶段第 5 条主线已完成：**`app/services/import_transfer_execution.py` 已承接 copy-fallback 判定 / payload 解析 / 文件系统导入执行**，`import_to_library.py` 已从 `1727` 行降到 `1494` 行。
- 当前阶段第 6 条主线已完成：**`app/services/import_cancel_state.py` 已承接 `cancel_pending_import()` 的 pending job 查询 / lease 读取 / approval+job 取消 / fail-closed 中文日志**，`import_to_library.py` 已从 `1494` 行降到 `1392` 行。
- 当前阶段第 7 条主线已完成：**`app/services/add_execution_follow_up.py` 已承接 confirm 执行 / 下载监控登记 / 事件落盘 helper`**，`add_to_downloader.py` 已从 `1669` 行降到 `1549` 行。
- 当前阶段第 8 条主线已完成：**`app/services/add_cancel_state.py` 已承接 `cancel_pending_add()` 的 pending lookup / lease / approval+job cancel / fail-closed 中文日志**，`add_to_downloader.py` 已从 `1549` 行降到 `1399` 行。
- 当前阶段第 9 条主线已完成：**`app/services/search_reply_formatter.py` 已承接 movie reply / delivery item / BT 只读与批量预览回复拼装**，`search_media.py` 已从 `1018` 行降到 `725` 行。
- 当前阶段第 10 条主线已完成：**`app/services/search_clarification_state.py` 已承接 clarification pending / clear / persisted load 状态 helper**，`search_media.py` 已从 `725` 行降到 `616` 行。
- 当前阶段第 11 条主线已完成：**`app/services/search_candidate_state.py` 已承接 candidate save / load / rollback helper**，`search_media.py` 已从 `616` 行降到 `460` 行，率先满足三座大山里的 `≤ 600` 目标。
- 当前阶段第 12 条主线已完成：**`app/services/add_confirm_job_state.py` 已承接 confirm jobs 抢占 / 回退 / 完结与 lease owner helper**，`add_to_downloader.py` 已从 `1399` 行降到 `1315` 行。
- 当前阶段第 13 条主线已完成：**`app/services/add_confirm_approval_state.py` 已承接 approval / lease 查询、stale-check 和 pending expiry helper**，`add_to_downloader.py` 已从 `1315` 行降到 `1235` 行。
- 当前阶段第 14 条主线已完成：**`app/services/add_confirm_context_state.py` 已承接 confirm context rebuild / expired confirm 收口**，`add_to_downloader.py` 已从 `1235` 行降到 `1117` 行。
- 当前阶段第 15 条主线已完成：**`app/services/add_confirm_approval_state.py` 已继续承接 pending approval 写入 / approve / restore / cancel / executed-version 回写**，`add_to_downloader.py` 已从 `1117` 行降到 `937` 行。
- 当前阶段第 16 条主线已完成：**`app/services/add_confirm_approval_state.py` 已继续承接 approval identity move，`tests/test_add_to_downloader.py` 新增 identity move warning guard**，`add_to_downloader.py` 已从 `937` 行降到 `927` 行。
- 当前阶段第 17 条主线已完成：**`app/services/add_confirm_finalization_state.py` 已承接 confirm 成功后的 warning 汇总 / job completion 尾部回写 / pending context 清理 / finalize trace`**，`add_to_downloader.py` 已从 `927` 行降到 `892` 行。
- 当前阶段第 18 条主线已完成：**`app/services/add_pending_context.py` 已继续承接进程内 pending context 记录 / 查询 / 清理 / 缺失日志 helper**，`add_to_downloader.py` 已从 `892` 行降到 `866` 行。
- 当前阶段第 19 条主线已完成：**`app/services/add_trace_logger.py` 已承接下载链 pure trace wrapper**，`add_to_downloader.py` 已从 `866` 行降到 `838` 行。
- 当前阶段第 20 条主线已完成：**`app/services/add_pending_persistence.py` 已承接 pending job 落盘失败分流和待确认回复渲染**，`add_to_downloader.py` 已从 `838` 行降到 `787` 行。
- 当前阶段第 21 条主线已完成：**`app/services/add_request_facade.py` 已承接 add request 入口 facade**，`add_to_downloader.py` 已从 `787` 行降到 `763` 行。
- 当前阶段第 22 条主线已完成：**`app/services/add_confirm_preparation.py` 已承接 confirm 前置状态准备**，`add_to_downloader.py` 已从 `763` 行降到 `698` 行。
- 当前阶段第 23 条主线已完成：**`app/services/add_confirm_execution_tail.py` 已承接 confirm execution tail**，`add_to_downloader.py` 已从 `698` 行降到 `674` 行。
- 当前阶段第 24 条主线已完成：**`app/services/add_confirm_availability_state.py` 已承接 confirm availability 壳**，`add_to_downloader.py` 已从 `674` 行降到 `644` 行。
- 当前阶段第 25 条主线已完成：**`app/services/add_pending_presence_state.py` 已承接 `has_pending_add()` 的 pending presence lookup 壳**，`add_to_downloader.py` 已从 `644` 行降到 `627` 行。
- 当前阶段第 26 条主线已完成：**`app/services/add_pending_write_through_state.py` 已承接 `_persist_pending_add()` 的 pending write-through 壳**，`add_to_downloader.py` 已从 `627` 行降到 `608` 行。
- 当前阶段第 27 条主线已完成：**`app/services/import_prepare_state.py` 已承接 `_prepare_import()` 下载器查询 / 完成态判断 / 源目标预检 / 命名真相 / target exists helper`**，`import_to_library.py` 已从 `1392` 行降到 `1087` 行。
- 当前唯一主线切到 **`app/services/import_to_library.py` 数据结构重设计 · 第 8 轮 · 评估 confirm execution tail 壳`**。
- 为什么现在切山：`_prepare_import()` 整块 fail-closed 预检已经离开主文件，`import_to_library.py` 一次性降了 `305` 行；当前剩余最大块明显集中在 `confirm_import_by_task_ref()` 里 `_execute_import()` 之后的 imported / pending_copy_approval / failed 三段收尾。相比继续抠零散 wrapper，这一刀更能继续降低 confirm 编排耦合。
- shared runtime / channel 解耦已累计完成 `57+` 条最小直连；`app/bot/private_chat_runtime.py` 当前 `468` 行、`app/bot/telegram_bot.py` 当前 `256` 行，更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- 当前三座大山现状：`app/services/add_to_downloader.py` `608` 行 / `import_to_library.py` `1087` 行 / `search_media.py` `460` 行。
- 质量基线前置条件已满足：本轮 `tests/test_import_to_library.py` 为 `142 passed`、prepare focused 为 `48 passed, 94 deselected`，`make quality` 为 `24 passed`，非沙箱 `.venv/bin/python -m pytest -q` 继续 `1718 passed, 4 warnings`，真实 `/data/downloads/tr -> /data/library/movies` import smoke 也已通过。

## User value

- `app/services/import_prepare_state.py` 已经把 `_prepare_import()` 那段 fail-closed 预检拿走；`import_to_library.py` 当前 `1087` 行，剩余最大结构债已经从“导入前预检”切到“confirm 后执行收尾”。
- 下一步优先评估 `confirm_import_by_task_ref()` 里 `_execute_import()` 之后的 execution tail，目标是把 imported / pending_copy_approval / failed 三段里的 approval restore、pending job restore、copy-fallback 标记和 finalize trace 收口成 helper，不改 confirm 对外协议。
- 若 helper 抽离会牵动 hardlink/copy-fallback 审批真相、`job_event(import.succeeded)`、completed job 回写或 refresh 失败不回滚边界，主线立即停住；不允许为了降行数改导入协议。

## Only do

- 只评估 `import_to_library.py` 里的 confirm execution tail 壳，优先看 `_execute_import()` 之后 imported / pending_copy_approval / failed 三段收尾。
- `import_to_library.py` 只继续负责用户入口、confirm 主顺序和 helper 编排；不回退已完成的 `import_prepare_state.py`、`import_post_processing.py`、`import_approval_state.py`、`import_job_state.py`、`import_transfer_execution.py`、`import_cancel_state.py` 和 `import_context_lookup.py` 边界。
- focused 验证优先跑 `tests/test_import_to_library.py -k "confirm_import_by_task_ref or copy_fallback or hardlink_failure or target_exists_during_execute or refresh_exception"`；只有在代码真的变更时才补 `make quality` 和全量 `pytest`。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；下载链详细台账继续留在 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`，导入链详细台账继续看 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`。

## Do not do

- 不回退 `search_request_context.py`、`search_reply_formatter.py`、`search_clarification_state.py`、`search_candidate_state.py` 的已收口边界；不改 search 文本协议。
- 不回退 downloader dispatch、download_monitor、job_event、approval / jobs / lease/version 真相协议；下载链本轮不再继续为了 `8` 行差距去硬拆薄 wrapper。
- 不改 hardlink/copy-fallback 协议，不改 metadata / subtitle / refresh 行为，不改导入成功后 `job_event(import.succeeded)`、approval executed-version 和 completed job 回写边界。
- 不在这一轮回到 `telegram_bot.py`、`private_chat_runtime.py` 或 BT 页面 proof。
- 不新增功能、不扩协议、不顺手重写搜索来源抽象。

## Done when

当前 **`import_to_library.py` 数据结构重设计 · 第 8 轮 · 评估 confirm execution tail 壳`** 主线视为 **已收口**，需要同时满足：

1. helper 已承接 `_execute_import()` 之后至少一整块 imported / pending_copy_approval / failed 收尾分支，`import_to_library.py` 不再直接持有这组三岔执行结果收尾大块实现；
2. `app/services/import_to_library.py` 行数从 `1087` 继续下降；
3. `tests/test_import_to_library.py -k "confirm_import_by_task_ref or copy_fallback or hardlink_failure or target_exists_during_execute or refresh_exception"` 继续绿灯；
4. 若本轮有代码改动，`make quality` 和全量 `pytest` 不被破坏；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` 已同步新的当前真相。

## After this step

1. 如果 confirm execution tail 抽离成功，下一条继续判断 `confirm_import_by_task_ref()` 前半段 claim / stale / approval gate 哪一段最适合再拆。
2. 如果 confirm execution tail 被证明会牵动 approval executed-version、completed job 或 copy-fallback 真相，下一条改走更保守的 facade，不在导入链硬拆执行协议。
3. 只有在 `add_to_downloader.py` 或 `import_to_library.py` 再拿下一座山后，当前阶段才可能逼近“三座大山各 ≤ 600” 的退出条件。
