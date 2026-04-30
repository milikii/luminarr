# Next step (v436)

## Current goal

- 当前 Stage 1 的三条实现子线已经推进到：`T16 成人 BT 下载前防重记忆层`、`T17 Telegram-first 高频主链交付层`、`T18 成人 BT 来源角色底座` 均已完成。
- 当前唯一下一条执行入口切到 `T19 Stage 1 聚合验证与运维真相同步`。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态，不作为本轮变更目标。

## User value

- 操作者现在能在创建成人下载待确认前收到“这个番号以前试过”的明确提醒，减少重复下载和重复清理。
- duplicate memory 已经走 `AddToDownloaderService` shared path，direct BT、批量选择和 `btsub` 命中会复用同一套判断，不再各写一套旧记录逻辑。
- Telegram 高频主链现在已经具备 inline actions、duplicate warning 主体验、关键 BT follow-up 提示交付和导入审批交付，不再只停在长文本手输命令。
- 成人 BT 来源现在已有明确的 `primary / supporting / helper_only` 角色真相；`javlibrary` 保持 helper-only，不会再混进主动下载来源。

## Only do

- 只做 `T19`：补 Stage 1 focused verification 入口、补新的实机 smoke 或等价证据，并把 operator-facing 真相页同步到当前实现。
- 当前 `T16` duplicate memory、`T17` Telegram-first 高频链和 `T18` 来源角色底座都已经是既有边界；`T19` 只能做验证与文档同步，不回退既有语义。
- 继续保持 adult-only BT 边界、显式 `confirm` 边界、`watchlist sync` fail-closed 边界和 `T16/T17/T18` 当前体验不回退。
- 继续保持 `make quality`、`make verify-mainline`、`make verify-adult-bt-wedge` 和 `make lint` 可复验。

## Do not do

- 不在 `T19` 之外顺手开启新的功能主线，也不把 Feishu / WeCom / personal WeChat 功能升级拖进这一轮。
- 不回切影视 BT、动漫 BT、`raw_bt subscription`、auto-confirm 或新的 `watchlist -> btsub` 桥接。
- 不顺手改 `ExecutionGate`、non-Telegram 后台通知主线，或把 duplicate memory 再扩成更重的全量证据账本。
- 不把运行时外部依赖清单重新分散回 `README.md`、`docs/STATUS.md` 或 `docs/OPERATOR_RUNBOOK.md`，同步文档时仍保持单一真相入口。

## Done when

1. Stage 1 focused verification 入口可重复运行，并覆盖 duplicate memory、Telegram-first 高频链和来源角色底座。
2. `docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/GETTING_STARTED.md` 与实现状态一致，不再保留冻结态或 `T17` 口径。
3. 真实 Telegram 操作路径至少补一轮新的实机 smoke 或等价证据。
4. `make quality` 通过。
5. `make verify-mainline` 通过。
6. `make verify-adult-bt-wedge` 通过。
7. `make lint` 通过。

## After this step

1. 若 `T19` 顺利完成，再进入收尾阶段，按 QA / ship 流程收口。
2. 若 `T19` 暴露新的来源边界、交付回退或 operator 文档漂移，先修复再考虑收尾。
