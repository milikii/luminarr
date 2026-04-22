# Next step (v296)

## Current goal

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段继续做 **services 层数据结构降本**，Done 定义仍锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 当前阶段第 1 条主线已完成：**`app/services/import_to_library.py` 数据结构重设计 · 第 1 轮 · 路径与特殊分支清单** 已落到 `docs/IMPORT_PIPELINE_REDESIGN.md`。
- 当前阶段第 2 条主线已完成：**`app/services/import_post_processing.py` 已承接 `metadata / subtitle / refresh` 后置链**，`import_to_library.py` 已从 `2242` 行降到 `2094` 行。
- 当前阶段第 3 条主线已完成：**`app/services/import_approval_state.py` 已承接 approval lease/version、stale-check、expiry 和目标路径回查**，`import_to_library.py` 已从 `2094` 行降到 `1827` 行。
- 当前阶段第 4 条主线已完成：**`app/services/import_job_state.py` 已承接 `jobs` pending/claim/release/complete 状态迁移**，`import_to_library.py` 已从 `1827` 行降到 `1727` 行。
- 当前阶段第 5 条主线已完成：**`app/services/import_transfer_execution.py` 已承接 copy-fallback 判定 / payload 解析 / 文件系统导入执行**，`import_to_library.py` 已从 `1727` 行降到 `1494` 行。
- 当前阶段第 6 条主线已完成：**`app/services/import_cancel_state.py` 已承接 `cancel_pending_import()` 的 pending job 查询 / lease 读取 / approval+job 取消 / fail-closed 中文日志**，`import_to_library.py` 已从 `1494` 行降到 `1392` 行。
- 当前唯一主线切到 **`app/services/add_to_downloader.py` 数据结构重设计 · 第 2 轮 · 抽 confirm 执行 / 下载监控 / 事件落盘 helper`**。
- 为什么现在切山：`import_to_library.py` 的 context / approval / jobs / file-transfer / cancel 五段都已经收口，再继续微拆很容易落进 AGENTS 的收益递减区；`add_to_downloader.py` 现在 `1669` 行，是 services 层当前最大的单文件。
- shared runtime / channel 解耦已累计完成 `57+` 条最小直连；`app/bot/private_chat_runtime.py` 当前 `468` 行、`app/bot/telegram_bot.py` 当前 `256` 行，更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- 当前三座大山现状：`add_to_downloader.py` `1669` 行 / `import_to_library.py` `1392` 行 / `search_media.py` `1018` 行。
- 质量基线前置条件已满足：本轮 `make quality` 为 `24 passed`，`tests/test_import_to_library.py -k "cancel_pending_import or expired_pending_confirm"` 为 `15 passed, 127 deselected`，`tests/test_import_to_library.py` 为 `142 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1716 passed, 4 warnings`。

## User value

- `add_to_downloader.py` 当前最重的一段不再是“候选选择 / 来源解析 / 待确认写入”，而是 `confirm_add_by_task_ref()` 周围那组 confirm 上下文重建、lease 抢占、下载器投递、下载监控登记和事件落盘。
- 先把 confirm 执行 / monitor / event 这一组拿出主文件，可以把“待确认准备”和“确认后副作用”彻底拆开，后面再看是否值得继续碰 cancel 或 approval 余量。
- 若 helper 抽离会牵动 `confirm` 文本协议、下载器已投递真相、审批 / `jobs` / `download_monitor` / `job_event` 边界，主线立即停住；不允许为了降行数改下载副作用协议。

## Only do

- 只抽 confirm 执行 / 下载监控 / 事件落盘 helper，例如 `app/services/add_execution_follow_up.py`，优先覆盖 `confirm_add_by_task_ref()` 里“投递下载器 -> 记录 `download_monitor` -> 追加 `job_event` -> 组装成功/警告回复”这块。
- `app/services/add_to_downloader.py` 只继续负责 selection / candidate 入口、pending 持久化、confirm 编排和 reply 顺序控制；不回退已完成的 `add_pending_context.py` 边界。
- focused 验证优先跑 `tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or register_download_monitor or record_event"`；只有在代码真的变更时才补 `make quality` 和全量 `pytest`。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；下载链详细台账继续分发到 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`。

## Do not do

- 不回退 `add_pending_context.py`，不改 candidate/source 解析，不改 downloader role binding，不改 `download_monitor` / `job_event` / approval / jobs / lease/version / SQLite 真相边界。
- 不改 `confirm` / `select` 文本协议，不改 pending add payload 语义，不改 downloader 已投递后的 fail-closed 中文日志语义。
- 不在这一轮回到 `import_to_library.py`、`search_media.py`、`telegram_bot.py` 或 `private_chat_runtime.py`。
- 不新增功能、不扩协议、不顺手重写下载器平台抽象。

## Done when

当前 **`add_to_downloader.py` 数据结构重设计 · 第 2 轮 · 抽 confirm 执行 / 下载监控 / 事件落盘 helper`** 主线视为 **已收口**，需要同时满足：

1. helper 已承接上述 confirm 执行 / `download_monitor` / `job_event` 组合边界，`add_to_downloader.py` 不再直接持有这组大块实现；
2. `app/services/add_to_downloader.py` 行数从 `1669` 继续下降；
3. `tests/test_add_to_downloader.py` 对应 focused tests 继续绿灯，且默认分支全量 `pytest` 不被本轮破坏；
4. `make quality` 继续通过；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` 已同步新的当前真相。

## After this step

1. 如果 confirm 执行 / monitor / event helper 抽离成功，下一条再评估 `add_to_downloader.py` 里 cancel / approval / completed-warning 哪一段还有继续拆的价值。
2. 如果这段 helper 被证明会牵动下载副作用真相或 confirm 文本协议，下一条改走更保守的 confirm facade，不直接外提整组执行函数。
3. 只有在 `add_to_downloader.py` 的 pending prepare 和 confirm follow-up 两段都收口后，才考虑触及 `search_media.py`。
