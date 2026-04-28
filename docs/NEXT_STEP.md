# Next step (v423)

## Current goal

- 当前唯一主线切到 **services 层数据结构降本**。
- 当前优先目标是收 services 层里稳定可复用的数据结构和解析逻辑，先从重复形状最明显、验证成本最低的地方下手。
- 本轮已把 `add_confirm_approval_state.py` 合并回 `app/services/add_to_downloader.py`，下一轮继续收 `add_confirm_context_state.py`。
- 本轮已把 watchlist 与 BT 订阅重复的 media kind alias / label / prefix parse 结构收口到 `app/services/media_kind.py`，focused tests 覆盖两条调用路径。
- 本轮继续删除 BT 订阅侧单用途 label 转发薄壳；后续不要再给 shared helper 包一层只改名字的单消费者函数。
- 本轮把 watchlist / BT 订阅共享的 `title (year-or-dash)` 展示格式收口到 `app/services/media_item_display.py`。
- 本轮把 watchlist / BT 订阅共享的命令前缀 tail 解析收口到 `app/services/command_parsing.py`，没有合并两条命令各自的 action 语义。
- 本轮继续把完整 tail 的 action alias 判断收口到 `match_command_action()`；带参数的 action parse 仍未合并。
- 本轮把带参数 action 的首词 alias + 参数拆分收口到 `match_command_action_argument()`，两条命令的默认 fallback 仍保持原样。
- 本轮删掉 `search_media.py` 里 `parse_movie_query` 的纯转发别名，测试改为直接引用真正的 parser。
- 本轮删掉 `search_media.py` 里 `load_bt_scoring_rules` 的纯转发别名，测试改为直接引用模块内真实绑定。
- 本轮删掉 `manage_bt_subscription.py` 的 `parse_bt_subscription_query` 再导出薄壳，调用点直接指向 `bt_subscription_command.py`。
- 本轮把导入链单消费者 `ImportMetadataTitleYearResolver` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_metadata_title_year.py`。
- 本轮把导入链单消费者 `ImportRawBtGuard` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_raw_bt_guard.py`。
- 本轮把导入链单消费者 `ImportConfirmContextGuard` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_confirm_context_guard.py`。
- 本轮把导入链单消费者 `ImportEventRecorder` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_event_recorder.py`。
- 本轮把导入链单消费者 `ImportPendingWriteThroughState` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_pending_write_through_state.py`。
- 本轮把导入链单消费者 `ImportConfirmedMediaIdentityResolver` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_confirmed_media_identity.py`。
- 本轮把导入链单消费者 `ImportJobState` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_job_state.py`。
- 本轮把导入链单消费者 `ImportCancelState` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_cancel_state.py`。
- 本轮把导入链单消费者 `ImportConfirmExpiryState` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_confirm_expiry_state.py`。
- 本轮把导入链单消费者 `ImportConfirmPreparation` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_confirm_preparation.py`。
- 本轮把导入链单消费者 `ImportConfirmExecutionTail` 合并回 `import_to_library.py`，删掉只被一处消费的 `import_confirm_execution_tail.py`。
- 本轮把 add 链单消费者 `AddPendingPresenceState` 合并回 `add_to_downloader.py`，删掉只被一处消费的 `add_pending_presence_state.py`。
- 本轮把 add 链单消费者 `AddPendingWriteThroughState` 合并回 `add_to_downloader.py`，删掉只被一处消费的 `add_pending_write_through_state.py`。
- 本轮把 add 链单消费者 `AddConfirmExecutionTail` 合并回 `add_to_downloader.py`，删掉只被一处消费的 `add_confirm_execution_tail.py`。
- 这轮开始不再以质量债为施工主线，但仍保持不改协议、SQLite schema、调度语义或下载 / 导入 / 刷新真相边界。
- 已完成态保持，不回退：
  - README 不承载当前施工热点，当前真相看 STATUS/NEXT_STEP。
  - docs gate 不再锁死 `telegram_bot.py` 这类易漂移文件行数。
  - **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口**继续保持完成态。
  - 5 个小单消费者 support 文件已合并回消费方，并由测试守卫防止回退。
  - import transfer、TMDB fallback、WeCom base64 解码、search/web/BT 展示、candidate/clarification、Telegram delivery/update、import pending/approval/event 等异常边界已持续收口。
  - downloader route lookup、confirm / cleanup / frustration / BT read-only / raw BT / BT TMDB / BT pending、Feishu client、web source、main startup、Telegram update/delivery、channel identity、download follow-up、metadata/subtitle、watchlist/BT subscription、cleanup correlation、auto-import/search/naming/scoring/import/cleanup、WeCom callback、cleanup smoke、trace、cleanup docs sync 的日志出口已统一到 shared operational logging。
  - Feishu 入站已切到 SDK 长连接 only；webhook server / webhook 装配 / webhook 专属测试与配置入口已经移除。
  - `cleanup_smoke_logging` 不再保留不可能成立的空路径兜底。
  - `feishu_long_connection` 的停止请求与 stop 失败只收 `RuntimeError`，避免机械吞掉不相关异常。
  - WeCom webhook HTTP 入口把超时单独判成 504，并取消悬挂 future，不再和一般异常混成一类。
  - BT pending 的 `processing_path`、`classification`、`tmdb_association`、`raw_bt_destination` 持久化边界已收窄。
  - downloader route / import prepare / cleanup seed window / adult archive 持久化失败现在都进入明确状态不可用或明确查询失败边界。
  - adult archive 操作失败现在由 `AdultArchiveOperationError` 承接，上层不再用泛 `Exception` 判断归档/清理失败。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。
- `app/downloader_route_lookup.py` 的共享路由日志 helper 已收口为 `_emit_downloader_issue_log`，不再用 “print” 命名误导维护者。
- 本轮“连续推进十轮”已到退出点；收尾先重新跑 `make quality` 与 `make verify-mainline`，确认默认分支质量仍可复验，再从更小、更保守的结构候选继续选下一轮。

## User value

- 减少 services 层重复结构和解析歧义，同时保持现有用户行为、协议和持久化真相不变。
- 默认分支继续可用；后续每轮都要可验证、可回滚、文档同步。
- 成人 BT 后续仍可以切，但这轮先把 services 层结构债压低，不在不稳边界上扩功能。

## Only do

- 每轮只挑一个最小闭环：收掉重复 alias / label / parse helper，或把重复数据结构收成现有共享边界。
- 只改有 focused tests 能覆盖的路径；没有测试先补最小测试。
- 更新 STATUS/NEXT_STEP/codex.md，保持当前真相和验证结果一致。

## Do not do

- 不切成人 BT 新功能，不扩 BT 协议，不改下载/导入/审批/清理语义。
- 不强拆 `approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py` 这类较大文件。
- 不把 `config.py` 改成 YAML，不改部署配置格式，不动 SQLite schema。

## Done when

1. 下一轮选中的 services 结构闭环有明确 diff、focused tests 和文档同步。
2. `make quality` 通过。
3. `make verify-mainline` 通过。
4. 已收掉的小 support 文件不回归。
5. 下一候选仍能从 STATUS/NEXT_STEP 直接判断，不需要回读历史台账。

## After this step

1. 若继续 services 结构降本，优先评估重复 alias / label / parse helper、共享展示模型或稳定数据结构收口点。
2. 若候选会影响协议、SQLite 真相边界或下载 / 导入 / 刷新语义，先停下确认边界。
3. 若用户明确切成人 BT，则先写成人 BT 缺口清单和 focused gate，再动功能代码。
