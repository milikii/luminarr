# Next step (v428)

## Current goal

- 当前唯一主线切到扩展 BT subscription 边界，优先锁定 raw BT subscription 的最小 contract。
- `watchlist sync` / `想看 同步` 已完成：当前会把想看清单按相同 `chat_id` / `title` / `year` / `media_kind` 原子同步进 `btsub`，不触发自动下载，也不会在失败时留下部分成功。
- `adult BT minimum wedge` 已完成并已推送到 `main`；当前只保留 Telegram 人工 smoke 收尾，不再扩 scope。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 让刚补完的 `watchlist -> btsub` 桥接真正有更完整的自动化承接面，而不是仍被当前最小 `btsub` 边界卡住。
- 在不放宽 `confirm` 边界的前提下，继续增强 BT 连续追踪能力，而不是把 watchlist 或 btsub 偷变成自动下载。
- 保持 adult BT minimum wedge、config capability contract、sidecar host 解耦和 shared private-chat runtime 边界不回退。

## Only do

- 当前只做一件事：扩展 BT subscription 边界。
- 下一轮优先锁定 raw BT subscription 的最小 contract；继续保持人工 `confirm`，不把 auto-confirm 偷带进来。
- 优先补 focused tests 和最小 contract，不在同一轮同时把通知渠道扩边、richer reply、多渠道交互形态或 personal WeChat 登录重做绑进来。
- 继续保持 config capability contract、shared private-chat runtime 边界、`shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 完成态，以及 `watchlist sync` 的原子桥接语义不回退。
- 继续保持 `make quality`、`make verify-mainline` 和 `make verify-adult-bt-wedge` 可复验。

## Do not do

- 不回切 `services` 结构降本，不顺手拆大文件。
- 不改 SQLite schema，不改 BT/PT 主链语义，不改 `ExecutionGate`。
- 不把配置格式改成 YAML，不重做部署拓扑。
- 不顺手收口 `app/bot/private_chat_runtime.py` 对 `app/bot/telegram_bot.py` 的残余 helper 依赖；那条 channel-neutral 收口主线后移。
- 不顺手改 richer reply、多渠道交互形态或 non-Telegram 后台通知主线，不把 personal WeChat 登录重做绑进这轮。

## Done when

1. `BT subscription` 当前最小边界已经被扩到下一条明确的可复验 contract，且不回退现有 movie/series/anime 追踪路径。
2. 该主线对应的 focused tests 与 operator 文档真相一致。
3. `make quality` 通过。
4. `make verify-mainline` 通过。
5. `make verify-adult-bt-wedge` 通过。

## After this step

1. 后续如果再回到 non-Telegram 后台主动通知，先单独开一轮，不和 BT subscription 扩边混跑。
2. 若 Telegram 人工 smoke 暴露 adult BT bug，先做最小修复闭环，再回到 BT subscription 主线。
3. 若候选改动开始触碰协议、SQLite 真相边界或下载 / 导入语义，先停下确认。
