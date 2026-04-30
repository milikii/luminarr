# Next step (v434)

## Current goal

- 当前已从“完成态冻结”切到新的 Stage 1 主线：`Telegram-first 主操作者控制面 + 成人 BT 来源底座`。
- `T16 成人 BT 下载前防重记忆层` 已完成；当前下一条执行入口切到 `T17 Telegram-first 高频主链交付层`。
- `T18 成人 BT 来源角色底座` 继续保留为后续顺位，不与 `T17` 并行启动。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态，不作为本轮变更目标。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 操作者现在能在创建成人下载待确认前收到“这个番号以前试过”的明确提醒，减少重复下载和重复清理。
- duplicate memory 已经走 `AddToDownloaderService` shared path，direct BT、批量选择和 `btsub` 命中会复用同一套判断，不再各写一套旧记录逻辑。
- Stage 1 的第一刀已经交付，下一步可以把 Telegram 高频主链交付层做成更直接的 Telegram-first 体验，而不是继续停在长文本手输命令。

## Only do

- 只做 `T17`：围绕 Telegram 高频主链收口更直接的交付层，优先覆盖搜索结果、下载确认、导入确认、状态反馈和关键 BT follow-up。
- duplicate memory 的提醒与显式继续语义现在已经是既有边界；`T17` 只能在这条边界上做 Telegram-first 交付，不得回退回长文本埋命令。
- 继续保持 adult-only BT 边界、显式 `confirm` 边界、`watchlist sync` fail-closed 边界和 `T16` 的 duplicate gate 不回退。
- 继续保持 `make quality`、`make verify-mainline`、`make verify-adult-bt-wedge` 和 `make lint` 可复验。

## Do not do

- 不提前启动 `T18` 的更大范围来源扩站，也不把 Feishu / WeCom / personal WeChat 一起拖进 Telegram-first 这轮。
- 不回切影视 BT、动漫 BT、`raw_bt subscription`、auto-confirm 或新的 `watchlist -> btsub` 桥接。
- 不顺手改 `ExecutionGate`、non-Telegram 后台通知主线，或把 duplicate memory 再扩成更重的全量证据账本。
- 不把运行时外部依赖清单重新分散回 `README.md`、`docs/STATUS.md` 或 `docs/OPERATOR_RUNBOOK.md`。

## Done when

1. Telegram 高频主链消息不再只依赖长文本手输命令。
2. duplicate memory 的提醒和显式继续语义会直接并入 Telegram 主体验，不形成平行支线。
3. shared delivery intent 继续可被其他渠道稳定降级成文本 fallback，不分叉业务真相。
4. `make quality` 通过。
5. `make verify-mainline` 通过。
6. `make verify-adult-bt-wedge` 通过。
7. `make lint` 通过。

## After this step

1. 进入 `T18 成人 BT 来源角色底座`，把主力 BT / 辅助 PT / helper-only 语义固定下来。
2. 再进入 `T19 Stage 1 聚合验证与运维真相同步`，补 focused verification 和新的实机证据。
3. 若 `T17` 在实现中暴露更大的交互或多渠道边界分歧，先回写计划与任务，再继续编码。
