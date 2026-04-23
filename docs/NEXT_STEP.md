# Next step (v320)

## Current goal

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段的 **services 层数据结构降本** 继续保持 Done 状态："三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
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
- 当前阶段第 35 条主线已完成：**`ImportApprovalState.record_pending_approval_with_copy_fallback_reset()` 已承接 pending approval write-through glue`**，`import_to_library.py` 已从 `656` 行降到 `654` 行，`tests/test_import_to_library.py` 新增 1 条 copy-fallback 清理直接断言。
- 当前阶段第 36 条主线已完成：**`app/services/import_pending_write_through_state.py` + `app/services/import_trace_logger.py` 已承接 `import_by_task_ref()` 的待确认写入 / trace wrapper**，`import_to_library.py` 已从 `654` 行降到 `585` 行，并新增 `tests/test_import_pending_write_through_state.py` focused gate。
- 当前阶段第 37 条主线已完成：**`app/services/add_execution_follow_up.py` 已新增独立 focused gate，`add_to_downloader.py` 删除 `job_event / download_monitor` thin wrapper，tests 改为直接钉 helper**，`add_to_downloader.py` 已从 `608` 行降到 `574` 行。
- 这一步证明 downloader 侧最后 `8` 行仍有真实结构收益：不是继续搬 wrapper，而是把 helper 失败日志测试从壳文件抽到真正负责事件落盘 / 监控登记的模块，顺手让三座大山全部过 `≤ 600`。
- 当前阶段第 38 条主线已完成：**`Makefile` 已新增 `test-downloader-focused`、`test-import-focused`、`verify-quality-gates`；Feishu / WeCom 本地 webhook smoke 已补最小起服重试**，质量入口不再依赖手写长命令。
- shared runtime / channel 解耦已累计完成 `57+` 条最小直连；`app/bot/private_chat_runtime.py` 当前 `468` 行、`app/bot/telegram_bot.py` 当前 `256` 行，更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- 当前三座大山现状：`app/services/add_to_downloader.py` `574` 行 / `import_to_library.py` `585` 行 / `search_media.py` `460` 行。
- 质量基线最新真相：`make quality` 为 `25 passed`；`make verify-quality-gates` 里的 focused 段已稳定，但全量阶段仍会偶发落到 `1723 passed, 2 skipped, 4 warnings`；单独 `.venv/bin/python -m pytest -q -rs` 复验可到 `1725 passed, 4 warnings`。
- 当前唯一最小主线切到 **`verify-quality-gates` 环境型 skip 收口`**：把 Feishu / WeCom 本地 webhook 监听 smoke 在 full gate 里的偶发 skip 收稳，恢复“固定质量入口不带黄灯”。

## User value

- `add_execution_follow_up.py` 现在自己承担 `job_event / download_monitor` fail-closed 中文日志 focused gate，后续回归会直接指到 helper，不再先穿过 `add_to_downloader.py` 壳文件。
- `add_to_downloader.py` 现在 `574` 行，`import_to_library.py` `585` 行，`search_media.py` `460` 行；三座大山已经全部过线。
- `Makefile` 现在把 downloader focused、import focused 和全量 `pytest` 固定成命令入口，后续回归不用再依赖施工者记忆长命令。
- 当前剩下的用户价值是把这条固定入口彻底收绿，避免 full gate 因本地端口监听波动留下 `skipped` 黄灯。
- 当前不再为了行数回头硬拆 `add_to_downloader.py` 或 `import_to_library.py` 的剩余薄 wrapper。

## Only do

- 只处理 `verify-quality-gates` 里的环境型 skip，不回头重磨已达标 services 壳文件。
- 若继续动代码，只允许围绕 Feishu / WeCom 本地 webhook 监听 smoke 的稳定性、执行顺序或隔离边界收口。
- 当前质量入口已固定到 `Makefile`；本轮不再新增更多 gate 名称，而是先把现有入口收稳。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一状态；下载链详细台账继续留在 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`，导入链详细台账继续看 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`。

## Do not do

- 不回退 `search_request_context.py`、`search_reply_formatter.py`、`search_clarification_state.py`、`search_candidate_state.py` 的已收口边界；不改 search 文本协议。
- 不回退 downloader dispatch、download_monitor、job_event、approval / jobs / lease/version 真相协议；下载链现在已过 `≤ 600`，不得再为了数字继续硬拆薄 wrapper。
- 不改 hardlink/copy-fallback 协议，不改 metadata / subtitle / refresh 行为，不改导入成功后 `job_event(import.succeeded)`、approval executed-version 和 completed job 回写边界。
- 不回到 `import_to_library.py` 继续拆纯 trace / pending write-through 之后剩下的薄委托，除非能证明有新的 focused gate 或失败边界收益。
- 不在当前稳定窗口里回到 `telegram_bot.py`、`private_chat_runtime.py` 或 BT 页面 proof。
- 不为了掩盖 `skipped` 去删掉 Feishu / WeCom 本地 webhook smoke；只允许把它们变稳定，不允许降级为不测。
- 不新增功能、不扩协议、不顺手重写搜索来源抽象。

## Done when

当前 **`verify-quality-gates` 环境型 skip 收口`** 主线视为 **完成**，需要同时满足：

1. `Makefile` 的 `test-downloader-focused` / `test-import-focused` / `verify-quality-gates` 已固定并有测试保护；
2. `make verify-quality-gates` 的全量阶段不再出现 Feishu / WeCom 本地 webhook 监听导致的偶发 `skipped`；
3. 当前真相已同步到 `docs/STATUS.md` / `docs/NEXT_STEP.md`；
4. `make quality`、focused tests 和全量 `pytest` 继续绿灯。

## After this step

1. 如果收稳 `verify-quality-gates`，下一条再评估真实 smoke 是否值得继续收成固定 target。
2. 如果默认分支重新出现红灯，优先回到真实失败测试或高风险持久化链路，不回头重磨已达标壳文件。
3. 如果后续出现新的 helper 失败边界，优先补独立 focused gate，而不是把测试继续钉回 orchestrator 壳文件。
