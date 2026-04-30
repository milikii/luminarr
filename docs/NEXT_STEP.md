# Next step (v433)

## Current goal

- 当前已从“完成态冻结”切到新的 Stage 1 主线：`Telegram-first 主操作者控制面 + 成人 BT 来源底座`。
- 当前唯一执行入口先锁到 `T16 成人 BT 下载前防重记忆层`；执行计划以 `docs/plans/2026-04-30-adult-duplicate-memory-execution.md` 为准。
- `T17 Telegram-first 高频主链交付层`、`T18 成人 BT 来源角色底座` 继续保留为后续顺位，不与 `T16` 并行启动。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态，不作为本轮变更目标。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 操作者在创建成人下载待确认前，就能收到“这个番号以前试过”的明确提醒，减少重复下载和重复清理。
- duplicate memory 走 `AddToDownloaderService` shared path，direct BT、批量选择和 `btsub` 命中都会复用同一套判断，不再各写一套旧记录逻辑。
- Stage 1 重新开工后，仓库会先交付最有感知、最不容易回退 adult-only 边界的第一刀，而不是同时把 Telegram 按钮、来源扩站和防重逻辑混在一轮里。

## Only do

- 只做 `T16`：新增 sibling snapshot 真相、shared duplicate memory service、`AddToDownloaderService` 下载前 gate、`duplicate_override` follow-up 和 focused tests。
- 只认现有 `extract_exact_adult_content_match` 的 exact 番号命中；第一轮不做标题相似度猜测，不扫任意手工目录。
- 继续保持 adult-only BT 边界、显式 `confirm` 边界、`watchlist sync` fail-closed 边界不回退。
- 继续保持 `make quality`、`make verify-mainline`、`make verify-adult-bt-wedge` 和 `make lint` 可复验。

## Do not do

- 不提前启动 `T17` 的 Telegram buttons / richer delivery，也不提前启动 `T18` 的更大范围来源扩站。
- 不回切影视 BT、动漫 BT、`raw_bt subscription`、auto-confirm 或新的 `watchlist -> btsub` 桥接。
- 不顺手改 `ExecutionGate`、`app/bot/private_chat_runtime.py` 对 `app/bot/telegram_bot.py` 的残余 helper 耦合，或 non-Telegram 后台通知主线。
- 不把运行时外部依赖清单重新分散回 `README.md`、`docs/STATUS.md` 或 `docs/OPERATOR_RUNBOOK.md`。

## Done when

1. `adult_duplicate_memory_snapshot` sibling 真相层已落地，且 repo 能稳定 round-trip。
2. `AddToDownloaderService` 在成人下载待确认创建前会统一检查 duplicate memory。
3. duplicate 命中时不会直接创建待确认，而是进入显式 `duplicate_override` 继续下载 follow-up。
4. direct BT、批量选择、`btsub` 命中都复用同一套 gate，异常时显式降级而不是静默跳过。
5. `make quality` 通过。
6. `make verify-mainline` 通过。
7. `make verify-adult-bt-wedge` 通过。
8. `make lint` 通过。

## After this step

1. 进入 `T17 Telegram-first 高频主链交付层`，先收口搜索 / 下载确认 / 状态反馈的 Telegram-first 交付体验。
2. 再进入 `T18 成人 BT 来源角色底座`，把主力 BT / 辅助 PT / helper-only 语义固定下来。
3. 若 `T16` 在实现中暴露更大的 schema、交互或来源边界分歧，先回写计划与任务，再继续编码。
