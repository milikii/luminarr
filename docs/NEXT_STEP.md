# Next step (v437)

## Current goal

- `T19 Stage 1 聚合验证与运维真相同步` 已完成；当前唯一下一步切到收尾阶段，不再继续扩执行阶段功能。
- `make verify-stage1` 现在是 `T16 duplicate memory`、`T17 Telegram-first 高频链`、`T18 成人 BT 来源角色底座` 的单一 focused verification 入口；`make verify-adult-bt-wedge` 保留为成人 BT 专线补充验证。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态，不作为收尾阶段的新变更目标。
- `2026-05-07` 已有真实 Telegram 入站与 PT 后半段 smoke 证据；当前文档与 QA 应以这组实机真相为前提，不再沿用“只有等价证据”的旧口径。

## User value

- 操作者现在可以直接跑 `make verify-stage1`，一次确认 duplicate memory、Telegram-first 高频交付和来源角色真相没有回退，不需要重新翻 task 历史或手拼测试文件。
- Stage 1 的 operator truth 已经落到 `Makefile`、`docs/STATUS.md`、`docs/GETTING_STARTED.md`、`docs/OPERATOR_RUNBOOK.md`，不再只存在开发者上下文里。
- 这轮同时把当前审批、宿主和渠道能力口径同步到顶层文档：数字选资源 / `import` guarded auto-confirm、WeCom 主动发送 unsupported、Telegram-first callback 主链都不再只藏在代码和 `docs/flows/` 里。

## Only do

- 只做收尾阶段动作：QA、发布准备、文档漂移复查；若要追加新的真实 Telegram smoke，把它当成增量证据，而不是去补“第一条实机证据”。
- 继续保持当前审批边界：direct source / BT follow-up / duplicate override / copy-fallback 显式 `confirm`；数字选资源与 `import` guarded auto-confirm。
- 继续保持 adult-only BT 边界、`watchlist sync` fail-closed 边界和 `T16/T17/T18` 当前体验不回退。
- 继续保持 `make verify-stage1`、`make quality`、`make verify-mainline`、`make verify-adult-bt-wedge` 和 `make lint` 可复验。

## Do not do

- 不顺手开启新的功能主线，也不在收尾阶段重新拉起影视 BT、动漫 BT、`raw_bt subscription`、auto-confirm 或新的 `watchlist -> btsub` 桥接。
- 不顺手改 `ExecutionGate`、non-Telegram 后台通知主线，或把 duplicate memory 再扩成更重的全量证据账本。
- 不把当前运行依赖和验证真相重新分散回多个平级入口；继续让 `docs/GETTING_STARTED.md` 管启动与验证，`docs/STATUS.md` 管当前快照。

## Done when

1. `make verify-stage1` 继续通过。
2. `make quality` 继续通过。
3. `make verify-mainline` 继续通过。
4. `make verify-adult-bt-wedge` 继续通过。
5. `make lint` 继续通过。
6. 收尾阶段 QA / 发布准备已启动，或明确记录为何暂不发布。

## After this step

1. 若准备发布，先完成一轮 QA 复核，再按当前发布流程整理分支与发布动作。
2. 若要追加新的真实 Telegram smoke，先确认 `api.telegram.org` 可达与本地 `app.main` 运行，再把新的 trace/evidence 作为增量回写到 `docs/STATUS.md`。
