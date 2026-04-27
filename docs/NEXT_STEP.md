# Next step (v384)

## Current goal

- 当前唯一主线切到 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮已继续收口 `search_candidate_state`、`search_clarification_state`、`telegram_update_runtime` 和 `telegram_delivery_runtime` 的异常边界；下一步继续从更小的 broad `except Exception`、日志打印边界或 `main()` DI 里挑一个最小闭环。
- 已完成态保持，不回退：
  - README 不再承载当前施工热点，当前真相看 STATUS/NEXT_STEP。
  - docs gate 不再锁死 `telegram_bot.py` 这类易漂移文件行数。
  - 5 个小单消费者 support 文件已合并回消费方，并由测试守卫防止回退。
  - import transfer、TMDB fallback、WeCom base64 解码的异常边界已收窄。
  - import 持久化边界这轮继续收口，`ImportApprovalState` / `ImportEventRecorder` / `ImportPendingWriteThroughState` 的回读和写回边界已改成只兜明确仓库异常。
  - **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口**继续保持完成态。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不再作为长期文档真相。
- 剩余 `*_support.py` 都是较大边界，不再因为文件名机械强拆；下一步优先从更小的 broad `except Exception` 或日志打印点继续收。

## User value

- 继续降低“代码说一套、文档说一套、测试又锁旧事实”的维护成本。
- 减少异常被吞掉后只能靠猜的场景，同时保持现有用户行为、协议和持久化真相不变。
- 成人 BT 后续可以切，但默认先把质量债继续压低，避免在不稳的边界上扩功能。

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
3. 已收掉的小 support 文件不回归。
4. 下一候选仍能从 STATUS/NEXT_STEP 直接判断，不需要回读历史台账。

## After this step

1. 若继续质量债，优先评估 `search_request_context`、`web_source`、`import_confirmed_media_identity`、`add_confirm_*` 一带剩余 broad `except` 和日志边界。
2. 若用户明确切成人 BT，则先写成人 BT 缺口清单和 focused gate，再动功能代码。
