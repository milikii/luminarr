# Next step (v427)

## Current goal

- 当前唯一主线切到 non-Telegram 后台主动通知所需的可逆会话真相。
- `Feishu-only` / `WeCom-only` 两个最小宿主画像已完成：当前在 Telegram token 为空时，会按可用凭据进入对应的 non-Telegram 宿主路径。
- 当前已补上第一层 truth：Feishu / WeCom / personal WeChat inbound 会把外部会话地址记录到运行态联系人注册表。
- `BT subscription scheduler` 在无主动 `send_text` 能力的宿主上现在会显式不启动，避免把 non-Telegram 背景通知伪装成可用。
- `adult BT minimum wedge` 已完成并已推送到 `main`；当前只保留 Telegram 人工 smoke 收尾，不再扩 scope。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界。精确行数以代码为准，不作为长期文档真相。

## User value

- 先把 non-Telegram 的入站宿主收口成可复验事实，再把“后台能不能发回去”单独收口成第二层可逆真相。
- 避免后台通知半通不通：当前没有主动 `send_text` 能力的宿主会显式降级，不再把真正的能力缺口埋成运行时失败。
- 保持 adult BT minimum wedge、config capability contract、sidecar host 解耦、Feishu / WeCom 依赖真相和 non-Telegram 宿主完成态不回退。

## Only do

- 当前只做一件事：non-Telegram 后台主动通知所需的可逆会话真相。
- 当前不要把“运行态联系人注册表”误当成后台通知已打通；这轮剩余的是把这份真相真正接到后台回发链路。
- 优先补 focused tests 和最小 contract，不在同一轮同时把 personal WeChat 登录重做、richer reply 或 watchlist/btsub 产品面一起做。
- 继续保持 config capability contract、sidecar host 解耦、shared private-chat runtime 边界、`shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 完成态，以及 `Feishu-only` / `WeCom-only` 最小画像不回退。
- 继续保持 `make quality`、`make verify-mainline` 和 `make verify-adult-bt-wedge` 可复验。

## Do not do

- 不回切 `services` 结构降本，不顺手拆大文件。
- 不改 SQLite schema，不改 BT/PT 主链语义，不改 `ExecutionGate`。
- 不把配置格式改成 YAML，不重做部署拓扑。
- 不顺手收口 `app/bot/private_chat_runtime.py` 对 `app/bot/telegram_bot.py` 的残余 helper 依赖；那条 channel-neutral 收口主线后移。
- 不顺手改 richer reply、多渠道交互形态或 watchlist/btsub 产品面，不把 personal WeChat 登录重做绑进这轮。

## Done when

1. non-Telegram 的入站宿主画像已经收口，当前只剩后台通知可逆真相这一层。
2. 该画像对应的 focused tests 与 operator 文档真相一致。
3. `make quality` 通过。
4. `make verify-mainline` 通过。
5. `make verify-adult-bt-wedge` 通过。

## After this step

1. 后续如果再做 personal WeChat 登录重做，先单独开一轮，不和后台通知真相混跑。
2. 若 Telegram 人工 smoke 暴露 adult BT bug，先做最小修复闭环，再回到后台通知真相。
3. 若候选改动开始触碰协议、SQLite 真相边界或下载 / 导入语义，先停下确认。
