# Next step (v318)

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
- 当前阶段第 28 条主线已完成：**`app/services/import_confirm_execution_tail.py` 已承接 imported / pending_copy_approval / failed 三岔收尾`**，`import_to_library.py` 已从 `1087` 行降到 `958` 行。
- 当前阶段第 29 条主线已完成：**`app/services/import_confirm_preparation.py` 已承接 confirm 前半段 context / stale / lease / approval gate`**，`import_to_library.py` 已从 `958` 行降到 `800` 行。
- 当前阶段第 30 条主线已完成：**`app/services/import_confirm_expiry_state.py` 已承接 confirm 过期分支的 approval cancel / pending job cancel / cleanup / expired event`**，`import_to_library.py` 已从 `800` 行降到 `742` 行。
- 当前阶段第 31 条主线已完成：**`app/services/import_event_recorder.py` 已承接导入链 `job_event` append / 回读异常 / 中文失败日志`**，`import_to_library.py` 已从 `742` 行降到 `729` 行。
- 当前阶段第 32 条主线已完成：**`app/services/import_raw_bt_guard.py` 已承接 raw_bt lookup / payload fail-closed guard 和中文日志`**，`import_to_library.py` 已从 `729` 行降到 `684` 行。
- 当前阶段第 33 条主线已完成：**`app/services/import_confirm_context_guard.py` 已承接 confirm context lookup / approval fail-closed guard 和中文日志`**，`import_to_library.py` 已从 `684` 行降到 `665` 行。
- 当前阶段第 34 条主线已完成：**`app/services/import_metadata_title_year.py` 已承接 metadata title/year fallback glue`**，`import_to_library.py` 已从 `665` 行降到 `656` 行，`tests/test_import_to_library.py` 新增 2 条 metadata title/year 直接断言。
- 当前唯一主线切到 **`app/services/import_to_library.py` 数据结构重设计 · 第 15 轮 · 评估 pending approval write-through helper`**。
- 为什么现在切山：metadata title/year 已经离开主文件；当前剩余更值钱、也更适合继续收口的一块，是 `_record_pending_approval()` 里“clear pending copy-fallback + approval write-through” 这组 glue。这一组继续围绕 approval / copy-fallback 真相，不会碰导入协议。
- shared runtime / channel 解耦已累计完成 `57+` 条最小直连；`app/bot/private_chat_runtime.py` 当前 `468` 行、`app/bot/telegram_bot.py` 当前 `256` 行，更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- 当前三座大山现状：`app/services/add_to_downloader.py` `608` 行 / `import_to_library.py` `656` 行 / `search_media.py` `460` 行。
- 质量基线前置条件已满足：本轮 metadata focused 为 `8 passed, 136 deselected`，`tests/test_import_to_library.py` 为 `144 passed`，`make quality` 为 `24 passed`，非沙箱 `.venv/bin/python -m pytest -q` 继续 `1720 passed, 4 warnings`。

## User value

- `app/services/import_metadata_title_year.py` 已经把 metadata title/year 组装拿走；`import_to_library.py` 当前 `656` 行，剩余最大结构债已经切到 pending approval write-through glue。
- 下一步优先评估 `_record_pending_approval()` 和对应 copy-fallback 清理，目标是把 pending approval write-through 收口成 helper，不改 approval 或 copy-fallback 真相边界。
- 若 helper 抽离会牵动 approval lease/version、copy-fallback 清理时机或 pending 文本协议，主线立即停住；不允许为了降行数改导入协议。

## Only do

- 只评估 `import_to_library.py` 里的 pending approval write-through helper，优先看 `_record_pending_approval()` 和 copy-fallback 清理 glue。
- `import_to_library.py` 只继续负责用户入口、confirm 主顺序和 helper 编排；不回退已完成的 `import_prepare_state.py`、`import_event_recorder.py`、`import_raw_bt_guard.py`、`import_confirm_context_guard.py`、`import_metadata_title_year.py`、`import_confirm_preparation.py`、`import_confirm_execution_tail.py`、`import_confirm_expiry_state.py`、`import_post_processing.py`、`import_approval_state.py`、`import_job_state.py`、`import_transfer_execution.py`、`import_cancel_state.py` 和 `import_context_lookup.py` 边界。
- focused 验证优先跑 `tests/test_import_to_library.py -k \"record_pending_approval or pending_state_unavailable or copy_fallback_pending\"`；只有在代码真的变更时才补 `make quality` 和全量 `pytest`。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；下载链详细台账继续留在 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`，导入链详细台账继续看 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`。

## Do not do

- 不回退 `search_request_context.py`、`search_reply_formatter.py`、`search_clarification_state.py`、`search_candidate_state.py` 的已收口边界；不改 search 文本协议。
- 不回退 downloader dispatch、download_monitor、job_event、approval / jobs / lease/version 真相协议；下载链本轮不再继续为了 `8` 行差距去硬拆薄 wrapper。
- 不改 hardlink/copy-fallback 协议，不改 metadata / subtitle / refresh 行为，不改导入成功后 `job_event(import.succeeded)`、approval executed-version 和 completed job 回写边界。
- 不在这一轮回到 `telegram_bot.py`、`private_chat_runtime.py` 或 BT 页面 proof。
- 不新增功能、不扩协议、不顺手重写搜索来源抽象。

## Done when

当前 **`import_to_library.py` 数据结构重设计 · 第 15 轮 · 评估 pending approval write-through helper`** 主线视为 **已收口**，需要同时满足：

1. helper 已承接 `_record_pending_approval()` 至少一整块 copy-fallback 清理 + approval write-through glue，`import_to_library.py` 不再直接持有这组 pending approval glue；
2. `app/services/import_to_library.py` 行数从 `656` 继续下降；
3. `tests/test_import_to_library.py -k \"record_pending_approval or pending_state_unavailable or copy_fallback_pending\"` 继续绿灯；
4. 若本轮有代码改动，`make quality` 和全量 `pytest` 不被破坏；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` 已同步新的当前真相。

## After this step

1. 如果 pending approval write-through helper 抽离成功，下一条继续判断 `import_to_library.py` 里剩余的 event glue / pending job wrapper 哪一段最适合再拆。
2. 如果 pending approval write-through helper 被证明会牵动 approval 或 copy-fallback 真相，下一条改走更保守的 facade，不在导入链硬拆执行协议。
3. 只有在 `add_to_downloader.py` 或 `import_to_library.py` 再拿下一座山后，当前阶段才可能逼近“三座大山各 ≤ 600” 的退出条件。
