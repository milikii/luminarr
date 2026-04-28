# Next step (v424)

## Current goal

- 当前唯一主线切到 `app/config.py` 启动硬依赖解耦。
- 先把 `load_settings()` 里的 `TELEGRAM_BOT_TOKEN`、`PROWLARR_*`、`TRANSMISSION_BASE_URL` 从全局硬必填收口成按功能 / 下载器实际使用关系判定。
- `adult BT minimum wedge` 已完成并已推送到 `main`；当前只保留 Telegram 人工 smoke 收尾，不再扩 scope。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 让非 Telegram / 非 Transmission / 非 Prowlarr 场景不再被无关硬依赖卡住。
- 保持 adult BT minimum wedge 可用，同时给后续多渠道独立运行铺平入口。
- 默认分支继续可验证、可回滚，不把主线重新带回 `services` 结构降本。

## Only do

- 只盘点真实启动依赖、功能开关和下载器实例使用关系。
- 只改 `app/config.py` 和必要的启动装配 / 测试路径；没有测试先补 focused tests。
- 继续保持 `make quality`、`make verify-mainline` 和 `make verify-adult-bt-wedge` 可复验。

## Do not do

- 不回切 `services` 结构降本，不顺手拆大文件。
- 不改 SQLite schema，不改 BT/PT 主链语义，不改 `ExecutionGate`。
- 不把配置格式改成 YAML，不重做部署拓扑。

## Done when

1. `load_settings()` 不再无条件硬要求 Telegram / Prowlarr / Transmission 全套键。
2. Telegram-only、non-Telegram、multi-downloader 等最小启动矩阵有 focused tests。
3. `make quality` 通过。
4. `make verify-mainline` 通过。
5. adult BT wedge 现有验证入口不回归。

## After this step

1. 若启动硬依赖解耦完成，下一条主线切 `app/bot/telegram_sidecar_runtime.py` 宿主解耦。
2. 若 Telegram 人工 smoke 暴露 adult BT bug，先做最小修复闭环，再回到 config 主线。
3. 若候选改动开始触碰协议、SQLite 真相边界或下载 / 导入语义，先停下确认。
