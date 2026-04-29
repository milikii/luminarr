# Next step (v429)

## Current goal

- 当前唯一主线切回成人 BT 专线边界；后续若继续扩 `BT subscription`，也只允许面向成人 BT 连续追踪，不引入任何影视资源订阅（包括动漫）。
- `watchlist sync` / `想看 同步` 已完成：当前会把想看清单按相同 `chat_id` / `title` / `year` / `media_kind` 原子同步进 `btsub`，不触发自动下载，也不会在失败时留下部分成功。
- `adult BT minimum wedge` 已完成并已推送到 `main`；当前只保留 Telegram 人工 smoke 收尾，不再扩 scope。
- direct `BT` / `magnet:?` 投递入口继续保留链路问询：先选 `观影 PT 链` 或 `BT 成人链`，不允许绕过问询直接把 BT 入口默认为成人链。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 保持 BT 支线继续只承接成人资源，不让 BT 主线重新回流到影视资源或动漫资源。
- direct `BT` / `magnet:?` 入口继续通过 `PT / BT` 问询把用户意图显式分流，避免把观影片源误投到成人 BT 链。
- 在不放宽 `confirm` 边界的前提下，只为成人 BT 连续追踪补最小能力，而不是把 watchlist 或 btsub 偷变成自动下载。
- 保持 adult BT minimum wedge、config capability contract、sidecar host 解耦和 shared private-chat runtime 边界不回退。

## Only do

- 当前只做一件事：把 BT 支线的后续扩边继续锁在成人 BT 专线内。
- 若要继续扩 `BT subscription`，下一轮也只允许锁定成人 BT 连续追踪的最小 contract；继续保持人工 `confirm`，不把 auto-confirm 偷带进来。
- 优先补 focused tests 和最小 contract，不在同一轮同时把通知渠道扩边、richer reply、多渠道交互形态或 personal WeChat 登录重做绑进来。
- 继续保持 config capability contract、shared private-chat runtime 边界、`shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 完成态，以及 `watchlist sync` 的原子桥接语义不回退。
- 继续保持 `make quality`、`make verify-mainline` 和 `make verify-adult-bt-wedge` 可复验。

## Do not do

- 不回切 `services` 结构降本，不顺手拆大文件。
- 不改 SQLite schema，不改 BT/PT 主链语义，不改 `ExecutionGate`。
- 不把配置格式改成 YAML，不重做部署拓扑。
- 不从 BT 线索取任何影视资源，包括动漫；影视资源继续走 PT 主链。
- 不把 `raw_bt subscription`、动漫 BT、通用影视 BT 订阅绑进这轮。
- 不顺手收口 `app/bot/private_chat_runtime.py` 对 `app/bot/telegram_bot.py` 的残余 helper 依赖；那条 channel-neutral 收口主线后移。
- 不顺手改 richer reply、多渠道交互形态或 non-Telegram 后台通知主线，不把 personal WeChat 登录重做绑进这轮。

## Done when

1. BT 支线继续只承接成人资源，文档与实现都不再把影视资源或动漫资源写回 BT 主线。
2. direct `BT` / `magnet:?` 投递继续通过 `观影 PT 链 / BT 成人链` 问询显式分流。
3. 该主线对应的 focused tests 与 operator 文档真相一致。
4. `make quality` 通过。
5. `make verify-mainline` 通过。
6. `make verify-adult-bt-wedge` 通过。

## After this step

1. 后续如果再回到 non-Telegram 后台主动通知，先单独开一轮，不和 BT subscription 扩边混跑。
2. 若 Telegram 人工 smoke 暴露 adult BT bug，先做最小修复闭环，再回到成人 BT 专线主线。
3. 若候选改动开始触碰协议、SQLite 真相边界或下载 / 导入语义，先停下确认。
