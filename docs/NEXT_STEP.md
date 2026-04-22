# Next step (v306)

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
- 当前唯一主线切到 **`app/services/add_to_downloader.py` 数据结构重设计 · 第 14 轮 · 评估 confirm finalization helper`**。
- 为什么现在切山：`import_to_library.py` 的 context / approval / jobs / file-transfer / cancel 五段都已经收口，再继续微拆很容易落进 AGENTS 的收益递减区；`add_to_downloader.py` 仍有 `927` 行，依旧是 services 层当前最大的单文件之一。
- shared runtime / channel 解耦已累计完成 `57+` 条最小直连；`app/bot/private_chat_runtime.py` 当前 `468` 行、`app/bot/telegram_bot.py` 当前 `256` 行，更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- 当前三座大山现状：`app/services/add_to_downloader.py` `927` 行 / `import_to_library.py` `1392` 行 / `search_media.py` `460` 行。
- 质量基线前置条件已满足：本轮 `tests/test_add_to_downloader.py` 为 `113 passed`，`make quality` 为 `24 passed`，非沙箱 `.venv/bin/python -m pytest -q` 继续 `1718 passed, 4 warnings`，真实 `add_to_downloader confirm` smoke 也已通过。

## User value

- `add_to_downloader.py` 里的 jobs 状态机、approval / lease 查询、confirm context / expiry、pending approval persistence 和 approval identity move 都已经离开主文件，但 finalization warning 汇总、job completion 尾部回写、pending context 清理和 trace logging 还挂在 confirm 成功分支里。
- 下一步优先评估 confirm finalization helper，目的是把“下载已成功后的尾部真相收口”和“主 confirm 编排顺序”拆开，继续降低 warning 拼装与状态回写的维护成本。
- 若 helper 抽离会牵动 jobs 完结真相、trace 日志或下载副作用边界，主线立即停住；不允许为了降行数改下载协议。

## Only do

- 只评估 `add_to_downloader.py` 里的 confirm finalization helper，优先看 finalization warning 汇总、`_mark_completed_job()`、pending context 清理和 confirm 成功后的最小 trace/logging 顺序。
- `add_to_downloader.py` 只继续负责用户入口、confirm 编排和 helper 顺序控制；不回退已完成的 `add_pending_context.py`、`add_execution_follow_up.py`、`add_cancel_state.py`、`add_confirm_job_state.py`、`add_confirm_approval_state.py`、`add_confirm_context_state.py` 边界。
- focused 验证优先跑 `tests/test_add_to_downloader.py`；只有在代码真的变更时才补 `make quality` 和全量 `pytest`。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；搜索链详细台账继续留在 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`，下载链详细台账继续看 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`。

## Do not do

- 不回退 `search_request_context.py`、`search_reply_formatter.py`、`search_clarification_state.py`、`search_candidate_state.py` 的已收口边界；不改 search 文本协议。
- 不改 downloader dispatch、download_monitor、job_event、approval / jobs / lease/version 真相协议；不回退 `add_execution_follow_up.py`、`add_cancel_state.py`、`add_confirm_job_state.py`、`add_confirm_approval_state.py` 和 `add_confirm_context_state.py`。
- 不在这一轮回到 `import_to_library.py`、`telegram_bot.py` 或 `private_chat_runtime.py`。
- 不新增功能、不扩协议、不顺手重写搜索来源抽象。

## Done when

当前 **`add_to_downloader.py` 数据结构重设计 · 第 14 轮 · 评估 confirm finalization helper`** 主线视为 **已收口**，需要同时满足：

1. helper 已承接 finalization warning 汇总 / job completion 尾部回写 / pending context 清理至少一整块边界，`add_to_downloader.py` 不再直接持有这组大块实现；
2. `app/services/add_to_downloader.py` 行数从 `927` 继续下降；
3. `tests/test_add_to_downloader.py` 继续绿灯；
4. 若本轮有代码改动，`make quality` 和全量 `pytest` 不被破坏；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` 已同步新的当前真相。

## After this step

1. 如果 confirm finalization helper 抽离成功，下一条继续评估这座山里剩余 pending context / trace wrapper 是否还有继续拆的价值。
2. 如果 confirm finalization helper 被证明会牵动 jobs / trace 真相，下一条改走更保守的 facade，不直接外提整组尾部回写。
3. 只有在 `add_to_downloader.py` 或 `import_to_library.py` 再拿下一座山后，当前阶段才可能逼近“三座大山各 ≤ 600” 的退出条件。
