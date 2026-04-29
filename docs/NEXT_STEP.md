# Next step (v424)

## Current goal

- 当前唯一主线切到清理当前依赖告警。
- `app/config.py` 启动硬依赖解耦方案 A 已完成；`telegram_sidecar_runtime.py` 宿主解耦已完成；`manage_bt_subscription.py` 首个超大业务文件收口切口已完成；Feishu 可选依赖策略已完成。
- `adult BT minimum wedge` 已完成并已推送到 `main`；当前只保留 Telegram 人工 smoke 收尾，不再扩 scope。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 让主线验证输出重新聚焦真实失败，不再被长期悬挂的 deprecation warnings 稀释。
- 给后续 smoke、真实私聊验证和 operator 排障一个更干净的信号面。
- 保持 adult BT minimum wedge、config capability contract、sidecar host 解耦、服务收口和 Feishu 依赖真相都不回退。
- 默认分支继续可验证、可回滚，不把主线重新带回 `services` 结构降本。

## Only do

- 只盘点 `lark_oapi` / `websockets` deprecation warnings 的真实来源和最小修法。
- 优先选“升级版本 / 局部兼容修补 / 局部 warnings 隔离”里差异最小的一条；没有 focused tests 先补 focused tests。
- 继续保持 config capability contract、sidecar host 解耦、shared private-chat runtime 边界、已完成的服务收口和 Feishu 依赖真相不回退。
- 继续保持 `make quality`、`make verify-mainline` 和 `make verify-adult-bt-wedge` 可复验。

## Do not do

- 不回切 `services` 结构降本，不顺手拆大文件。
- 不改 SQLite schema，不改 BT/PT 主链语义，不改 `ExecutionGate`。
- 不把配置格式改成 YAML，不重做部署拓扑。
- 不顺手改宿主/配置主线，不顺手改 richer reply、多渠道交互形态或 watchlist/btsub 产品面。

## Done when

1. `make verify-mainline` 不再持续打印当前已知的 `lark_oapi` / `websockets` deprecation warnings，或这些 warnings 被明确局部隔离且不影响主线信号面。
2. 相关依赖版本 / 兼容层 / focused tests 与文档真相一致。
3. `make quality` 通过。
4. `make verify-mainline` 通过。
5. `make verify-adult-bt-wedge` 通过。

## After this step

1. 若依赖告警收口完成，再继续评估 non-Telegram 一等公民、watchlist 衔接和 `btsub` 扩边界。
2. 若 Telegram 人工 smoke 暴露 adult BT bug，先做最小修复闭环，再回到依赖告警主线。
3. 若候选改动开始触碰协议、SQLite 真相边界或下载 / 导入语义，先停下确认。
