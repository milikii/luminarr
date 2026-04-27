# Next step (v388)

## Current goal

- 当前唯一主线继续是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮已完成 10 个最小代码闭环并通过总 gate：auto-import 终态/skip/completed list、候选读取、cleanup correlation、frustration pending job，以及 BT pending 四段状态链路都已从 broad `Exception` 收窄到明确 repo/SQLite 异常边界。
- 已完成态保持，不回退：
  - README 不承载当前施工热点，当前真相看 STATUS/NEXT_STEP。
  - docs gate 不再锁死 `telegram_bot.py` 这类易漂移文件行数。
  - **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口**继续保持完成态。
  - 5 个小单消费者 support 文件已合并回消费方，并由测试守卫防止回退。
  - import transfer、TMDB fallback、WeCom base64 解码、search/web/BT 展示、candidate/clarification、Telegram delivery/update、import pending/approval/event 等异常边界已持续收口。
  - BT pending 的 `processing_path`、`classification`、`tmdb_association`、`raw_bt_destination` 持久化边界已收窄。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。
- 剩余 `*_support.py` 都是较大边界，不再因为文件名机械强拆。

## User value

- 减少持久化异常被吞掉后只能靠猜的场景，同时保持现有用户行为、协议和持久化真相不变。
- 默认分支继续可用；质量 gate 和 mainline gate 已覆盖本轮触及路径。
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

1. 这一轮选中的质量债闭环有明确 diff、focused tests 和文档同步。
2. `make quality` 通过。
3. `make verify-mainline` 通过。
4. 已收掉的小 support 文件不回归。
5. 下一候选仍能从 STATUS/NEXT_STEP 直接判断，不需要回读历史台账。

## After this step

1. 若继续质量债，优先评估剩余 broad `except Exception` 中的 repo/SQLite 边界，或日志打印边界 / `main()` DI。
2. 若候选属于外部网络、LLM、TMDB/search、webhook 或后台 loop 隔离边界，先判断是否应保留宽捕获，不要机械替换。
3. 若用户明确切成人 BT，则先写成人 BT 缺口清单和 focused gate，再动功能代码。
