# Next step (v298)

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
- 当前唯一主线切到 **`app/services/search_media.py` 数据结构重设计 · 第 2 轮 · 抽歧义澄清 / 候选持久化 / 回复格式化 helper`**。
- 为什么现在切山：`import_to_library.py` 的 context / approval / jobs / file-transfer / cancel 五段都已经收口，再继续微拆很容易落进 AGENTS 的收益递减区；`add_to_downloader.py` 现在 `1669` 行，是 services 层当前最大的单文件。
- shared runtime / channel 解耦已累计完成 `57+` 条最小直连；`app/bot/private_chat_runtime.py` 当前 `468` 行、`app/bot/telegram_bot.py` 当前 `256` 行，更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- 当前三座大山现状：`app/services/add_to_downloader.py` `1399` 行 / `import_to_library.py` `1392` 行 / `search_media.py` `1018` 行。
- 质量基线前置条件已满足：本轮 `make quality` 为 `24 passed`，`tests/test_add_to_downloader.py -k "cancel_pending_add or cancel_pending_approval or handle_expired_pending_confirm"` 为 `19 passed, 92 deselected`，`tests/test_add_to_downloader.py` 继续 `111 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1716 passed, 4 warnings`。

## User value

- `search_media.py` 现在仍把歧义澄清、candidate 持久化和回复格式化压在同一个文件里，这是 shared runtime 每次搜索都会经过的高频热路径。
- 先把 clarification / candidate / reply 这一组从主文件拿出来，可以把“查询编排”和“状态写入 + 用户回复”分开，也能让后续 search 质量回归更聚焦。
- 若 helper 抽离会牵动 clarification、candidate 或 SQLite 真相边界，主线立即停住；不允许为了降行数改搜索协议。

## Only do

- 只抽 `search_media.py` 里歧义澄清 / candidate 持久化 / 回复格式化这组连贯 helper，优先看 `format_movie_query_reply()`、`format_bt_read_only_reply()`、clarification pending/clear、candidate 持久化与回滚。
- `search_media.py` 只继续负责 search request orchestration、shared runtime 入口和 helper 顺序控制；不回退已完成的 `search_request_context.py` 边界。
- focused 验证优先跑 `tests/test_search_media.py -k "clarification or candidate or quality_from_title"`；只有在代码真的变更时才补 `make quality` 和全量 `pytest`。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；搜索链详细台账继续分发到 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`。

## Do not do

- 不回退 `search_request_context.py`，不改 query 解析、TMDB 命中策略、clarification / candidate / SQLite 真相边界，不改 search 文本协议。
- 不在这一轮回到 `add_to_downloader.py`、`import_to_library.py`、`telegram_bot.py` 或 `private_chat_runtime.py`。
- 不新增功能、不扩协议、不顺手重写搜索来源抽象。

## Done when

当前 **`search_media.py` 数据结构重设计 · 第 2 轮 · 抽歧义澄清 / 候选持久化 / 回复格式化 helper`** 主线视为 **已收口**，需要同时满足：

1. helper 已承接歧义澄清 / candidate 持久化 / reply 相关的至少一整块边界，`search_media.py` 不再直接持有这组大块实现；
2. `app/services/search_media.py` 行数从 `1018` 继续下降；
3. `tests/test_search_media.py -k "clarification or candidate or quality_from_title"` 继续绿灯；
4. 若本轮有代码改动，`make quality` 和全量 `pytest` 不被破坏；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/SEARCH_MEDIA_SLIMMING_LOG.md` 已同步新的当前真相。

## After this step

1. 如果 clarification / candidate / reply helper 抽离成功，下一条再评估 `search_media.py` 里剩余 clarification clear / delivery 余量是否还有继续拆的价值。
2. 如果这一组 helper 被证明会牵动 clarification 或 candidate 真相，下一条改走更保守的 facade，不直接外提整组状态写入。
3. 只有在 `search_media.py` 的前半段和 clarification/candidate/reply 两段都收口后，才回头重评 `add_to_downloader.py` / `import_to_library.py` 是否还值得继续微切分。
