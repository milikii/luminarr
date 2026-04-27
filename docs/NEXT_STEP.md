# Next step (v381)

## Current goal

- 当前唯一主线切到 **文档入口收口 / 当前真相对齐**。
- 本轮只修 README、`docs/STATUS.md`、`docs/NEXT_STEP.md`、入口 runbook 和 docs gate 的漂移；不改业务代码、不改协议、不改 SQLite 真相边界。
- 需要立刻收掉的文档问题：
  - README 不再声明具体施工热点，当前施工真相只看 `docs/STATUS.md` 和 `docs/NEXT_STEP.md`。
  - `docs/STATUS.md` 保持短快照，不再展开大段 helper 清扫流水。
  - `docs/NEXT_STEP.md` 只写当前唯一主线、边界和退出条件，不继续复制旧热点台账。
  - docs gate 不再锁死 `telegram_bot.py` 这类易漂移文件的精确行数；长期决策只记录边界，不记录瞬时行数。
- 已完成态保持，不回退：cleanup 支持文件收口、workflow trace 收口、`_COMPAT_REEXPORTS` 清理、`config.py` 重复解析收口、downloader route helper 收口、以及 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口**。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不再作为长期文档真相。

## User value

- 用户不用在 README、STATUS、NEXT_STEP、runbook 之间判断哪个才是当前主线。
- 后续是否切成人 BT 能基于干净文档判断，而不是被旧的 route/helper 收口描述误导。
- 文档测试继续保护入口结构，但不再把过期行数当成必须维护的“真相”。

## Only do

- 只做文档入口与 docs gate 对齐；允许更新 `tests/test_cleanup_docs_consistency.py` 这类文档守卫测试。
- 保留四渠道和 `codex.md` 会话落盘的既定边界，不把它们写成待删除项。
- 成人 BT 只写当前完成态和后续候选，不新增功能、不改 `.env.example` 配置语义。

## Do not do

- 不切成人 BT 新功能，不扩 BT 协议，不改下载/导入/审批/清理行为。
- 不继续顺手拆 `main.py`、`config.py`、`*_support.py` 或日志系统；这些是后续代码质量主线，不混进本轮文档收口。
- 不把历史台账重新搬回 `docs/STATUS.md` 或 `docs/NEXT_STEP.md`。

## Done when

1. README 不再携带过时施工主线，当前主线只从 STATUS/NEXT_STEP 读取。
2. STATUS 能明确回答“先文档，成人 BT 后续再切”，同时保留最近验证快照。
3. NEXT_STEP 足够短，且只描述本轮文档收口边界。
4. docs gate 不再锁死易漂移行数，并且 `make quality` 通过。

## After this step

1. 文档收口通过后，再评估成人 BT 后续缺口；如果用户明确切成人 BT，先写一个最小缺口清单和 focused gate，再动代码。
2. 如果用户没有明确切功能，下一条默认仍走质量债：日志、`except Exception`、`main()` DI 或 support 文件收口，按最小闭环推进。
