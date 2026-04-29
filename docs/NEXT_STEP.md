# Next step (v424)

## Current goal

- 当前唯一主线切到明确 Feishu 可选依赖策略。
- `app/config.py` 启动硬依赖解耦方案 A 已完成；`telegram_sidecar_runtime.py` 宿主解耦已完成；`manage_bt_subscription.py` 首个超大业务文件收口切口已完成。
- `adult BT minimum wedge` 已完成并已推送到 `main`；当前只保留 Telegram 人工 smoke 收尾，不再扩 scope。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 让 Feishu 这条能力链不再处于“代码可启动但依赖声明不明确”的灰区。
- 给非程序员操作者一个一致的装机真相，避免出现“requirements 没写、文档也没锁死、运行时才报 ImportError”的冷启动坑。
- 保持 adult BT minimum wedge、config capability contract、sidecar host 解耦和已完成的服务收口都不回退。
- 默认分支继续可验证、可回滚，不把主线重新带回 `services` 结构降本。

## Only do

- 只盘点 `lark_oapi` 在 Feishu 长连接链路里的真实依赖边界和装机入口。
- 只在“补 `requirements.txt` / 改成 extras / 明确写死操作文档”三种收口方式里选一个最小方案；没有 focused tests 先补 focused tests。
- 继续保持 config capability contract、sidecar host 解耦、shared private-chat runtime 边界和已完成的服务收口不回退。
- 继续保持 `make quality`、`make verify-mainline` 和 `make verify-adult-bt-wedge` 可复验。

## Do not do

- 不回切 `services` 结构降本，不顺手拆大文件。
- 不改 SQLite schema，不改 BT/PT 主链语义，不改 `ExecutionGate`。
- 不把配置格式改成 YAML，不重做部署拓扑。
- 不顺手改宿主/配置主线，不顺手改 richer reply、多渠道交互形态或 watchlist/btsub 产品面。

## Done when

1. `lark_oapi` 的安装真相被明确收口到一个稳定入口：`requirements.txt`、extras 或 operator docs 三者之一，不再模糊。
2. `docs/GETTING_STARTED.md` / `.env.example` / 相关代码边界与该方案一致。
3. `make quality` 通过。
4. `make verify-mainline` 通过。
5. `make verify-adult-bt-wedge` 通过。

## After this step

1. 若 Feishu 依赖策略收口完成，再继续清理当前依赖告警。
2. 若 Telegram 人工 smoke 暴露 adult BT bug，先做最小修复闭环，再回到依赖主线。
3. 若候选改动开始触碰协议、SQLite 真相边界或下载 / 导入语义，先停下确认。
