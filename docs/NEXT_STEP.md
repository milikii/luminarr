# Next step (v387)

## Current goal

- 当前唯一主线切到 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮已完成 10 个最小闭环：9 个代码闭环收口 add/import confirm/cancel、private confirm routing、download follow-up、watchlist、BT subscription repo support、import job 和 import naming truth 的 repo/SQLite 异常边界；第 10 个闭环同步 STATUS/NEXT_STEP/codex.md。下一步继续从更小的 broad `except Exception`、日志打印边界或 `main()` DI 里挑一个最小闭环。
- 本轮已继续收口 `status_follow_up`、`post_download_auto_import`、`get_download_status` 和 `download_follow_up_runtime` 的 5 处状态/下载 follow-up 异常边界；下一步继续从更小的 broad `except Exception`、日志打印边界或 `main()` DI 里挑一个最小闭环。
- 本轮已继续收口 `search_request_context`、`web_source`、`bt_read_only_display`、`import_confirmed_media_identity`、`add_adult_registry_state` 和 `import_context_lookup` 的 12 处异常边界；下一步继续从更小的 broad `except Exception`、日志打印边界或 `main()` DI 里挑一个最小闭环。
- 已完成态保持，不回退：
  - README 不再承载当前施工热点，当前真相看 STATUS/NEXT_STEP。
  - docs gate 不再锁死 `telegram_bot.py` 这类易漂移文件行数。
  - 5 个小单消费者 support 文件已合并回消费方，并由测试守卫防止回退。
  - import transfer、TMDB fallback、WeCom base64 解码的异常边界已收窄。
  - add/import confirm/cancel、watchlist、BT subscription repo support 和 shared confirm 路由的 repo/SQLite 异常边界已继续收窄。
  - import 持久化边界继续收口，`ImportApprovalState` / `ImportEventRecorder` / `ImportPendingWriteThroughState`、`ImportConfirmedMediaIdentityResolver` 和 `ImportContextLookup` 的回读和写回边界已改成只兜明确仓库异常。
  - 搜索与 BT 展示边界继续收口，`search_request_context`、`web_source`、`bt_read_only_display` 和 `add_adult_registry_state` 不再吞泛 `Exception`。
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

1. 若继续质量债，优先评估 `post_download_auto_import` 剩余成人归档/终态/skip event 边界、`status_follow_up` 剩余终态事件边界、日志边界或 `main()` DI。
2. 若用户明确切成人 BT，则先写成人 BT 缺口清单和 focused gate，再动功能代码。
