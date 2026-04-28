# Next step (v424)

## Current goal

- 当前唯一主线切到 `app/bot/telegram_sidecar_runtime.py` 宿主解耦。
- `app/config.py` 启动硬依赖解耦方案 A 已完成：`PROWLARR_*` 已改成能力必填，legacy `TRANSMISSION_BASE_URL` 在已有可用 downloader instances 时可留空；`TELEGRAM_BOT_TOKEN` 继续保持当前宿主必填。
- `adult BT minimum wedge` 已完成并已推送到 `main`；当前只保留 Telegram 人工 smoke 收尾，不再扩 scope。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 让非 Telegram 场景不再被 Telegram `Application` 生命周期硬绑死。
- 为 Feishu、WeCom、personal WeChat 和后台 scheduler 提供独立于 Telegram 的宿主边界。
- 保持 adult BT minimum wedge 和刚完成的 config capability contract 不回退。
- 默认分支继续可验证、可回滚，不把主线重新带回 `services` 结构降本。

## Only do

- 只盘点 Telegram 生命周期下当前承载的 sidecar、webhook server 和 scheduler。
- 只改宿主边界、启动装配和必要的 focused tests；没有测试先补 focused tests。
- 继续保持 config capability contract、shared private-chat runtime 和现有业务服务边界不回退。
- 继续保持 `make quality`、`make verify-mainline` 和 `make verify-adult-bt-wedge` 可复验。

## Do not do

- 不回切 `services` 结构降本，不顺手拆大文件。
- 不改 SQLite schema，不改 BT/PT 主链语义，不改 `ExecutionGate`。
- 不把配置格式改成 YAML，不重做部署拓扑。
- 不顺手改 richer reply、多渠道交互形态或 watchlist/btsub 产品面。

## Done when

1. Feishu、WeCom、personal WeChat、自动导入轮询与 `btsub` scheduler 不再只能挂在 Telegram `Application` 生命周期下。
2. Telegram 继续作为一个渠道 wrapper，而不是唯一宿主真相边界。
3. non-Telegram 运行所需的最小宿主边界有 focused tests。
4. `make quality` 通过。
5. `make verify-mainline` 通过。
6. `make verify-adult-bt-wedge` 通过。

## After this step

1. 若宿主解耦完成，再评估是否把 non-Telegram 运行模式做成一等公民。
2. 若 Telegram 人工 smoke 暴露 adult BT bug，先做最小修复闭环，再回到宿主主线。
3. 若候选改动开始触碰协议、SQLite 真相边界或下载 / 导入语义，先停下确认。
