# Next step (v297)

## Current goal

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段继续做 **services 层数据结构降本**，Done 定义仍锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 当前阶段第 1 条主线已完成：**`app/services/import_to_library.py` 数据结构重设计 · 第 1 轮 · 路径与特殊分支清单** 已落到 `docs/IMPORT_PIPELINE_REDESIGN.md`。
- 当前阶段第 2 条主线已完成：**`app/services/import_post_processing.py` 已承接 `metadata / subtitle / refresh` 后置链**，`import_to_library.py` 已从 `2242` 行降到 `2094` 行。
- 当前阶段第 3 条主线已完成：**`app/services/import_approval_state.py` 已承接 approval lease/version、stale-check、expiry 和目标路径回查**，`import_to_library.py` 已从 `2094` 行降到 `1827` 行。
- 当前阶段第 4 条主线已完成：**`app/services/import_job_state.py` 已承接 `jobs` pending/claim/release/complete 状态迁移**，`import_to_library.py` 已从 `1827` 行降到 `1727` 行。
- 当前阶段第 5 条主线已完成：**`app/services/import_transfer_execution.py` 已承接 copy-fallback 判定 / payload 解析 / 文件系统导入执行**，`import_to_library.py` 已从 `1727` 行降到 `1494` 行。
- 当前阶段第 6 条主线已完成：**`app/services/import_cancel_state.py` 已承接 `cancel_pending_import()` 的 pending job 查询 / lease 读取 / approval+job 取消 / fail-closed 中文日志**，`import_to_library.py` 已从 `1494` 行降到 `1392` 行。
- 当前阶段第 7 条主线已完成：**`app/services/add_execution_follow_up.py` 已承接 confirm 执行 / 下载监控登记 / 事件落盘 helper`**，`add_to_downloader.py` 已从 `1669` 行降到 `1549` 行。
- 当前唯一主线切到 **`app/services/add_to_downloader.py` 数据结构重设计 · 第 3 轮 · 重评 `cancel_pending_add()` 是否值得继续拆`**。
- 为什么现在切山：`import_to_library.py` 的 context / approval / jobs / file-transfer / cancel 五段都已经收口，再继续微拆很容易落进 AGENTS 的收益递减区；`add_to_downloader.py` 现在 `1669` 行，是 services 层当前最大的单文件。
- shared runtime / channel 解耦已累计完成 `57+` 条最小直连；`app/bot/private_chat_runtime.py` 当前 `468` 行、`app/bot/telegram_bot.py` 当前 `256` 行，更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- 当前三座大山现状：`add_to_downloader.py` `1549` 行 / `import_to_library.py` `1392` 行 / `search_media.py` `1018` 行。
- 质量基线前置条件已满足：本轮 `make quality` 为 `24 passed`，`tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or register_download_monitor or record_event"` 为 `40 passed, 71 deselected`，`tests/test_add_to_downloader.py` 为 `111 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1716 passed, 4 warnings`。

## User value

- confirm 执行 / monitor / event 已经离开主文件，`add_to_downloader.py` 现在最厚、也最靠近高风险状态机的块，变成了 `cancel_pending_add()` 与超时取消分支。
- 再做一次 `cancel_pending_add()` 收益重评，可以尽快判断 downloader 链是继续收最后一个 helper，还是直接把主线切去 `search_media.py`。
- 若下一轮只能拆出同类诊断分流而没有明确结构降本，就应该直接停住，不允许为了降行数硬拆下载取消协议。

## Only do

- 只重评 `cancel_pending_add()` 是否还存在单一职责 helper；如果有，helper 只承接 approval cancel / pending job cancel / fail-closed 中文日志中的一整块，不得拆成多条零碎诊断支线。
- `app/services/add_to_downloader.py` 继续负责 selection / candidate 入口、pending 持久化、confirm 编排和 reply 顺序控制；不回退已经完成的 `add_pending_context.py` 与 `add_execution_follow_up.py` 边界。
- focused 验证优先跑 `tests/test_add_to_downloader.py -k "cancel_pending_add or cancel_pending_approval or handle_expired_pending_confirm"`；只有在代码真的变更时才补 `make quality` 和全量 `pytest`。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；下载链详细台账继续分发到 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`。

## Do not do

- 不回退 `add_pending_context.py` 或 `add_execution_follow_up.py`，不改 candidate/source 解析，不改 downloader role binding，不改 `download_monitor` / `job_event` / approval / jobs / lease/version / SQLite 真相边界。
- 不改 `confirm` / `select` / `cancel` 文本协议，不改 pending add payload 语义，不改 downloader 已投递后的 fail-closed 中文日志语义。
- 不在这一轮回到 `import_to_library.py`、`search_media.py`、`telegram_bot.py` 或 `private_chat_runtime.py`。
- 不新增功能、不扩协议、不顺手重写下载器平台抽象。

## Done when

当前 **`add_to_downloader.py` 数据结构重设计 · 第 3 轮 · 重评 `cancel_pending_add()` 是否值得继续拆`** 主线视为 **已收口**，需要同时满足：

1. 已明确给出结论：`cancel_pending_add()` 要么抽出一个真正有用户价值的 helper，要么被宣告进入收益递减区；
2. 若继续拆，`add_to_downloader.py` 行数继续下降且不改 cancel 协议、SQLite 真相和中文 fail-closed 日志；
3. cancel 相关 focused tests 继续绿灯；
4. 若本轮有代码改动，`make quality` 和全量 `pytest` 不被破坏；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` 已同步新的当前真相。

## After this step

1. 如果 `cancel_pending_add()` 仍有一个清晰 helper 可抽，就只做这一条最小闭环，然后停止继续在 `add_to_downloader.py` 微切分。
2. 如果下一轮证明这里只剩诊断分流，不再继续拆 `add_to_downloader.py`，直接把主线切到 `search_media.py`。
3. `search_media.py` 仍是 services 层下一座大山，不提前回到 `import_to_library.py`。
