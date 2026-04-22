# Next step (v307)

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
- 当前唯一主线切到 **`app/services/add_to_downloader.py` 数据结构重设计 · 第 21 轮 · 评估 confirm availability 壳`**。
- 为什么现在切山：confirm execution tail 已经离开主文件，剩下最厚的一整块是开头那段 confirm availability 判定；继续顺着这段 fail-closed 拒绝路径做 facade，切口仍然最小。
- shared runtime / channel 解耦已累计完成 `57+` 条最小直连；`app/bot/private_chat_runtime.py` 当前 `468` 行、`app/bot/telegram_bot.py` 当前 `256` 行，更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- 当前三座大山现状：`app/services/add_to_downloader.py` `674` 行 / `import_to_library.py` `1392` 行 / `search_media.py` `460` 行。
- 质量基线前置条件已满足：本轮 `tests/test_add_to_downloader.py` 为 `113 passed`，`make quality` 为 `24 passed`，非沙箱 `.venv/bin/python -m pytest -q` 继续 `1718 passed, 4 warnings`，真实 `add_to_downloader confirm` smoke 也已通过。

## User value

- `add_to_downloader.py` 里的 add request facade、confirm 前置状态准备、confirm execution tail、jobs 状态机、approval / lease 查询、confirm context / expiry、pending approval persistence、approval identity move、confirm finalization、pending runtime state、pure trace wrapper 和 pending reply/persistence helper 都已经离开主文件，但 confirm availability 壳还集中挂在主文件开头。
- 下一步优先评估 confirm availability 壳，目的是继续把“上下文可用性判定 + fail-closed 拒绝”拆开，先判断 `confirm_add_by_task_ref()` 开头那段 confirm_context / in-memory pending / approval pending 校验是否还能共用一层 facade。
- 若 helper 抽离会牵动 shared runtime、trace 协议或下载副作用边界，主线立即停住；不允许为了降行数改下载协议。

## Only do

- 只评估 `add_to_downloader.py` 里的 confirm availability 壳，优先看 `confirm_add_by_task_ref()` 开头那段 confirm_context 重建、approval pending 校验、in-memory pending 兜底和 fail-closed 拒绝路径。
- `add_to_downloader.py` 只继续负责用户入口、confirm 编排和 helper 顺序控制；不回退已完成的 `add_confirm_execution_tail.py`、`add_confirm_preparation.py`、`add_request_facade.py`、`add_pending_context.py`、`add_pending_persistence.py`、`add_trace_logger.py`、`add_execution_follow_up.py`、`add_cancel_state.py`、`add_confirm_job_state.py`、`add_confirm_approval_state.py` 和 `add_confirm_context_state.py` 边界。
- focused 验证优先跑 `tests/test_add_to_downloader.py`；只有在代码真的变更时才补 `make quality` 和全量 `pytest`。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；搜索链详细台账继续留在 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`，下载链详细台账继续看 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`。

## Do not do

- 不回退 `search_request_context.py`、`search_reply_formatter.py`、`search_clarification_state.py`、`search_candidate_state.py` 的已收口边界；不改 search 文本协议。
- 不改 downloader dispatch、download_monitor、job_event、approval / jobs / lease/version 真相协议；不回退 `add_execution_follow_up.py`、`add_cancel_state.py`、`add_confirm_job_state.py`、`add_confirm_approval_state.py` 和 `add_confirm_context_state.py`。
- 不在这一轮回到 `import_to_library.py`、`telegram_bot.py` 或 `private_chat_runtime.py`。
- 不新增功能、不扩协议、不顺手重写搜索来源抽象。

## Done when

当前 **`add_to_downloader.py` 数据结构重设计 · 第 21 轮 · 评估 confirm availability 壳`** 主线视为 **已收口**，需要同时满足：

1. helper 已承接 confirm availability 壳至少一整块边界，`add_to_downloader.py` 不再直接持有这组 fail-closed 拒绝路径的大块实现；
2. `app/services/add_to_downloader.py` 行数从 `674` 继续下降；
3. `tests/test_add_to_downloader.py` 继续绿灯；
4. 若本轮有代码改动，`make quality` 和全量 `pytest` 不被破坏；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` 已同步新的当前真相。

## After this step

1. 如果 confirm availability 壳抽离成功，下一条继续评估这座山是否已经逼近收益递减，还是还能再收一块最小顺序控制辅助。
2. 如果 confirm availability 壳被证明会牵动 approval / jobs / in-memory pending 真相，下一条改走更保守的 facade，不直接外提整组 confirm 顺序控制。
3. 只有在 `add_to_downloader.py` 或 `import_to_library.py` 再拿下一座山后，当前阶段才可能逼近“三座大山各 ≤ 600” 的退出条件。
