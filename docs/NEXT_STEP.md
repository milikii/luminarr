# Next step (v424)

## Current goal

- 当前唯一主线切到继续收口超大业务文件。
- `app/config.py` 启动硬依赖解耦方案 A 已完成；`telegram_sidecar_runtime.py` 宿主解耦已完成。
- `adult BT minimum wedge` 已完成并已推送到 `main`；当前只保留 Telegram 人工 smoke 收尾，不再扩 scope。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 让后续业务改动不再被超大 service 文件拖慢。
- 优先把重复 helper、单消费者状态壳和局部职责拆分做成可验证的最小差异。
- 保持 adult BT minimum wedge、config capability contract 和 sidecar host 解耦都不回退。
- 默认分支继续可验证、可回滚，不把主线重新带回 `services` 结构降本。

## Only do

- 只盘点超大业务文件的体量、重复 helper 和单消费者切口。
- 先从最可控的局部职责拆分开始；没有 focused tests 先补 focused tests。
- 继续保持 config capability contract、sidecar host 解耦和 shared private-chat runtime 边界不回退。
- 继续保持 `make quality`、`make verify-mainline` 和 `make verify-adult-bt-wedge` 可复验。

## Do not do

- 不回切 `services` 结构降本，不顺手拆大文件。
- 不改 SQLite schema，不改 BT/PT 主链语义，不改 `ExecutionGate`。
- 不把配置格式改成 YAML，不重做部署拓扑。
- 不顺手改宿主/配置主线，不顺手改 richer reply、多渠道交互形态或 watchlist/btsub 产品面。

## Done when

1. 至少 1 个超大 service 文件被收口出明确的局部职责边界。
2. 重复 helper 或单消费者状态壳有 focused tests 保护。
3. `make quality` 通过。
4. `make verify-mainline` 通过。
5. `make verify-adult-bt-wedge` 通过。

## After this step

1. 若超大业务文件收口形成稳定模式，再继续评估 non-Telegram 一等公民、watchlist 衔接和 `btsub` 扩边界。
2. 若 Telegram 人工 smoke 暴露 adult BT bug，先做最小修复闭环，再回到服务收口主线。
3. 若候选改动开始触碰协议、SQLite 真相边界或下载 / 导入语义，先停下确认。
