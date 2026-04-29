# Next step (v432)

## Current goal

- `T13`、`T14`、`T15` 已全部完成；当前没有新的编码主线，默认进入完成态冻结。
- Telegram 成人 BT 真机 smoke 已补齐证据；运行时外部依赖真相页已收口到 `docs/GETTING_STARTED.md`；`search_media.py` 的候选/澄清状态 helper 已抽到独立模块。
- direct `BT` / `magnet:?` 入口继续保留 `观影 PT 链 / BT 成人链` 问询；`watchlist sync` 继续 fail-closed；`btsub add` 继续只接受成人 BT 精确番号追踪。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 非技术操作者现在只需要看一处就能确认运行前置依赖，不必在多个入口文档里交叉核对。
- 当前 adult-only BT 边界、shared runtime 边界和配置能力边界都保持绿灯，没有因为文档或结构收口而回退。
- `search_media.py` 的状态存储职责更清楚，后续维护时更容易定位“搜索流程”和“搜索状态真相”各自的边界。

## Only do

- 当前只做完成态冻结：保持文档、测试和代码边界一致，不主动重开新功能或新重构。
- 若用户要求继续推进，先做冷启动一致性检查，再决定是否开启新主线。
- 继续保持 `make quality`、`make verify-mainline`、`make verify-adult-bt-wedge` 和 `make lint` 可复验。
- 继续保持 `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 完成态，以及 `app/bot/private_chat_runtime.py` / `app/bot/telegram_bot.py` 当前边界不回退。

## Do not do

- 不因为“还有余量”就自行重开 BT subscription 扩边、non-Telegram 后台通知、多渠道交互形态或更大范围结构降本。
- 不改 SQLite schema，不改 BT/PT 主链语义，不改 `ExecutionGate`。
- 不把运行时外部依赖清单重新分散回 `README.md`、`docs/STATUS.md` 或 `docs/OPERATOR_RUNBOOK.md`。
- 不顺手收口 `app/bot/private_chat_runtime.py` 对 `app/bot/telegram_bot.py` 的残余 helper 依赖；没有新主线时保持当前边界冻结。

## Done when

1. `docs/TASKS.md` 中全部任务保持勾选完成。
2. `docs/GETTING_STARTED.md` 继续作为运行时外部依赖唯一真相页。
3. `make quality` 通过。
4. `make verify-mainline` 通过。
5. `make verify-adult-bt-wedge` 通过。
6. `make lint` 通过。

## After this step

1. 若只是确认当前仓库仍然稳定，下一轮先执行冷启动一致性检查。
2. 若用户要开新主线，先补 `docs/NEXT_STEP.md` 与 `docs/TASKS.md`，再进入新的执行循环。
3. 若 Telegram 成人 BT、运行时依赖或 `search_media` 结构切口在后续回归中出现漂移，先按最小修复闭环处理，不顺手扩 scope。
