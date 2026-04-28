# Current status (v542)

## Current mainline
- **质量硬化** 已正式收工；当前唯一主线切到 **services 层数据结构降本**。
- 文档真相已对齐 D-039：后续优先收 services 层里稳定可复用的数据结构和解析逻辑，先从重复形状最明显、验证成本最低的地方下手。
- 本轮已把 watchlist 与 BT 订阅重复的 `movie/series/anime` alias、label 和前缀解析收口到 `app/services/media_kind.py`，保持两条路径原有默认行为不变。
- 本轮继续删除 BT 订阅侧单用途 `bt_subscription_media_kind_label()` 转发薄壳，扫描命中回复和列表格式化都直接复用 shared media kind helper。
- 本轮把 watchlist、BT 订阅列表、BT 订阅扫描回复里的 `title (year-or-dash)` 展示格式收口到 `app/services/media_item_display.py`。
- 本轮把 watchlist 与 BT 订阅重复的命令前缀 tail 解析收口到 `app/services/command_parsing.py`，后续 action 规则保持各自原样。
- 本轮继续把 watchlist 与 BT 订阅重复的“完整 tail 命中 action alias”判断收口到 `match_command_action()`，带参数 action 解析仍保留各自语义。
- 本轮继续把带参数 action 的首词 alias + 参数拆分收口到 `match_command_action_argument()`，删除两处手写 regex。
- 本轮把 `search_media.py` 里的 `parse_movie_query` 纯转发别名删掉，测试直接指向真正的 parser。
- 本轮把 `search_media.py` 里的 `load_bt_scoring_rules` 纯转发别名删掉，测试直接指向模块内真实绑定。
- 本轮把 `manage_bt_subscription.py` 的 `parse_bt_subscription_query` 再导出薄壳删掉，调用点直接指向 `bt_subscription_command.py`。
- 本轮把导入链单消费者 `ImportMetadataTitleYearResolver` 合并回 `import_to_library.py`，删除 `import_metadata_title_year.py` 小文件，metadata title/year 回退顺序保持不变。
- 本轮把导入链单消费者 `ImportRawBtGuard` 合并回 `import_to_library.py`，删除 `import_raw_bt_guard.py` 小文件，raw_bt 阻断判定与日志文案保持不变。
- 本轮把导入链单消费者 `ImportConfirmContextGuard` 合并回 `import_to_library.py`，删除 `import_confirm_context_guard.py` 小文件，confirm 上下文查询分流与日志保持不变。
- 当前继续保持不改协议、SQLite schema、调度语义或下载 / 导入 / 刷新真相边界。
- 当前质量 gate 仍保持可复验；后续每轮先做一个最小结构闭环，再补 focused tests 和文档同步。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 仍是可复验的；最近一次通过结果保持 `27 passed, 0 skipped`。
- 当前没有新的业务回归信号；这次切线来自文档决策，不是红灯修复。
- 下一轮优先挑 services 层里稳定可复用的数据结构或解析逻辑，做最小抽离并补 focused tests。

## Latest verification
- `tests/test_import_to_library.py -k "rebuild_confirm_context or context_lookup_failure or context_row_corruption"` 通过（`4 passed, 149 deselected`）。
- `tests/test_import_to_library.py -k "raw_bt"` 通过（`8 passed, 145 deselected`）。
- `tests/test_import_to_library.py -k "resolve_metadata_title_year or extract_title_year_for_scrape"` 通过（`5 passed, 148 deselected`）。
- `tests/test_manage_bt_subscription.py tests/test_private_chat_bt_subscription_runtime.py tests/test_telegram_bot.py -k "bt_subscription_query"` 通过（`6 passed, 237 deselected`）。
- `tests/test_search_media.py -k "parse_movie_query or load_bt_scoring_rules"` 通过（`32 passed, 153 deselected`）。
- `tests/test_search_media.py -k "parse_movie_query"` 通过（`32 passed, 153 deselected`）。
- `tests/test_command_parsing.py tests/test_manage_watchlist.py tests/test_manage_bt_subscription.py` 通过（`64 passed`）。
- `tests/test_command_parsing.py tests/test_manage_watchlist.py tests/test_manage_bt_subscription.py` 通过（`63 passed`）。
- `tests/test_command_parsing.py tests/test_manage_watchlist.py tests/test_manage_bt_subscription.py` 通过（`62 passed`）。
- `tests/test_media_item_display.py tests/test_manage_watchlist.py tests/test_manage_bt_subscription.py` 通过（`61 passed`）。
- `tests/test_media_kind.py tests/test_manage_bt_subscription.py` 通过（`42 passed`）。
- `tests/test_media_kind.py tests/test_manage_watchlist.py tests/test_manage_bt_subscription.py` 通过（`62 passed`）。
- 上一轮质量硬化 focused tests 与 `make quality` / `make verify-mainline` 都已通过，当前继续保持该已验证状态。

## Current biggest risk
- services 层里仍有重复的数据结构和解析 helper；切线后应先收最容易验证的共享部分，避免跨模块搬大块责任。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是 services 层数据结构降本。优先从重复数据结构、解析 helper 或共享 label/alias 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
