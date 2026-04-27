# Next step (v395)

## Current goal

- 当前唯一主线继续是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮已完成 10 个最小闭环：把 `downloader_route_lookup`、`private_chat_confirm_runtime`、`private_chat_cleanup_runtime`、`private_chat_frustration_runtime`、`private_chat_bt_read_only_runtime`、`raw_bt_destination_runtime`、`bt_tmdb_association_runtime`、`bt_pending_runtime`、`clients/feishu.py`、`clients/web_source.py` 的手写 ANSI 日志统一到 shared `emit_operational_log` 边界。
- 本轮还修复了 `confirm add` 的下载器投递失败边界：`add_torrent_func` 的运行时 / HTTP 错误现在返回既有失败文本，并走既有审批回退，不再泄出异常。
- focused tests 已覆盖本轮触及的日志路径和 downloader dispatch 失败路径；`tests/test_downloader_route_lookup.py`、`tests/test_private_chat_confirm_runtime.py`、`tests/test_private_chat_cleanup_runtime.py`、`tests/test_private_chat_frustration_runtime.py`、`tests/test_private_chat_bt_read_only_runtime.py`、`tests/test_private_chat_raw_bt_destination_runtime.py`、`tests/test_private_chat_bt_tmdb_runtime.py`、`tests/test_private_chat_bt_processing_runtime.py`、`tests/test_feishu_client.py`、`tests/test_bt_sources.py`、`make quality` / `make verify-mainline` 已通过，协议、SQLite schema、下载/导入/BT 主线语义不变。
- 已完成态保持，不回退：
  - README 不承载当前施工热点，当前真相看 STATUS/NEXT_STEP。
  - docs gate 不再锁死 `telegram_bot.py` 这类易漂移文件行数。
  - **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口**继续保持完成态。
  - 5 个小单消费者 support 文件已合并回消费方，并由测试守卫防止回退。
  - import transfer、TMDB fallback、WeCom base64 解码、search/web/BT 展示、candidate/clarification、Telegram delivery/update、import pending/approval/event 等异常边界已持续收口。
  - downloader route lookup、confirm / cleanup / frustration / BT read-only / raw BT / BT TMDB / BT pending、Feishu client、web source 的日志出口已统一到 shared operational logging。
  - BT pending 的 `processing_path`、`classification`、`tmdb_association`、`raw_bt_destination` 持久化边界已收窄。
  - downloader route / import prepare / cleanup seed window / adult archive 持久化失败现在都进入明确状态不可用或明确查询失败边界。
  - adult archive 操作失败现在由 `AdultArchiveOperationError` 承接，上层不再用泛 `Exception` 判断归档/清理失败。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。
- 剩余 `*_support.py` 都是较大边界，不再因为文件名机械强拆。

## User value

- 减少持久化异常和操作失败只能靠猜的场景，同时保持现有用户行为、协议和持久化真相不变。
- 默认分支继续可用；focused gate 已覆盖本轮触及路径，质量 gate 和 mainline gate 继续作为退出条件。
- 成人 BT 后续可以切，但默认先把质量债继续压低，避免在不稳边界上扩功能。

## Only do

- 每轮只挑一个最小闭环：明确异常类型、收掉单消费者薄壳、或把重复打印收成现有共享边界。
- 只改有 focused tests 能覆盖的路径；没有测试先补最小测试。
- 更新 STATUS/NEXT_STEP/codex.md，保持当前真相和验证结果一致。

## Do not do

- 不切成人 BT 新功能，不扩 BT 协议，不改下载/导入/审批/清理语义。
- 不强拆 `approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py` 这类较大文件。
- 不把 `config.py` 改成 YAML，不改部署配置格式，不动 SQLite schema。

## Done when

1. 下一轮选中的质量债闭环有明确 diff、focused tests 和文档同步。
2. `make quality` 通过。
3. `make verify-mainline` 通过。
4. 已收掉的小 support 文件不回归。
5. 下一候选仍能从 STATUS/NEXT_STEP 直接判断，不需要回读历史台账。

## After this step

1. 若继续质量债，优先评估剩余 broad `except Exception` 中的 repo/SQLite 边界，或继续收口剩余日志打印边界 / `main()` DI。
2. 若候选属于外部网络、LLM、TMDB/search、webhook 或后台 loop 隔离边界，先判断是否应保留宽捕获，不要机械替换。
3. 若用户明确切成人 BT，则先写成人 BT 缺口清单和 focused gate，再动功能代码。
