# Next step (v263)

## Current goal

- 当前质量硬化阶段仍停留在 **`telegram_bot.py` 生命周期编排边界瘦身** 主线。
- 这条主线里 sidecar 启停 helper 和 Application lifecycle 入口都已抽到 `app/bot/telegram_sidecar_runtime.py`；当前更小的下一刀，是把这个 runtime 对 `telegram_bot.py` 的懒导入继续切薄。
- `app/bot/private_chat_runtime.py` 仍保留为当前另一块 `1421` 行热点文件，但这轮先不回头继续拆它，先处理 `telegram_bot.py` 里更容易落成闭环的生命周期编排。
- 上一条已完成闭环是 **Telegram lifecycle 公开入口收口**：`telegram_runtime_adapter.py` 现在直接绑定 `telegram_sidecar_runtime.py` 的公开入口，不再直接依赖 `telegram_bot.py` 的私有 `_start/_stop` helper。
- 上一条已完成闭环是 **Telegram 生命周期 sidecar helper 收口**：Feishu/WeCom webhook、personal WeChat、download follow-up scheduler 启停已抽到 `app/bot/telegram_sidecar_runtime.py`，`telegram_bot.py` 只保留 BT 订阅调度入口与现有兼容符号。
- 上一条已完成主线是 **`Makefile` / `verify-mainline` 补齐 download follow-up runtime 的固定质量入口**：`app/bot/download_follow_up_runtime.py` focused tests 已纳入固定回归，当前不回退。
- 再上一条已完成主线是 **`telegram_bot.py` 里的 `post_download_auto_import` / `download_completion_polling` 调度边界瘦身**：下载完成轮询与自动导入调度已抽到 `app/bot/download_follow_up_runtime.py`，当前不回退。
- 再上一条已完成主线是 **`app/bot/telegram_runtime_adapter.py` 的 message / callback 入口边界收口**：Telegram message / callback 入口共用的 chat/user 解析、去重落盘和 reply 包装已抽到 `app/bot/telegram_update_runtime.py`，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT TMDB / raw_bt follow-up 与 pending reminder 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT processing-path / classification follow-up 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 frustration / reset 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT 直接入口 pending 初始化分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 批量确认路由分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 只读探索 / cleanup 路由分支瘦身**，当前不回退。
- 更早一条已完成主线 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- `telegram_bot.py` 的入口边界、follow-up 调度边界和 sidecar 启停都已经补过一轮；当前更小也更直接的下一步，是继续削掉 `telegram_sidecar_runtime.py -> telegram_bot.py` 这条 lifecycle 懒导入。
- 这一步继续只做最小边界瘦身，不顺手放大成新的渠道平台、统一 webhook 框架或大文件总重写。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。

## User value

- 把 webhook / personal WeChat / download follow-up 这些 sidecar 启停和 lifecycle 入口都先收出去，再继续把 runtime 对 `telegram_bot.py` 的回看切薄，后续排查启动顺序时不必来回跳公开入口和私有 helper。
- 在默认分支已经稳绿、固定 gate 已补齐的前提下，优先继续降低热点文件体积和渠道总调度耦合。
- 避免 `telegram_bot.py` 在入口、follow-up、生命周期三条链都刚拆完后又继续回涨。

## Only do

- 只做一次保守瘦身：围绕 Telegram 渠道生命周期入口与 scheduler helper 抽出最小 runtime 或薄封装。
- 保持现有 parser / routing / approval / SQLite 真相边界不变，不新增用户可感知功能，不改渠道外部协议。
- 保持当前 shared delivery 文本、中文日志和现有 confirm / cancel / follow-up 语义不回退。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线。

## Do not do

- 不放宽 approval、`jobs` / `job_event` / lease/version / SQLite 真相边界。
- 不新增功能、不扩协议、不顺手重写整个 `telegram_bot.py` / `private_chat_runtime.py`。
- 不把 Telegram 渠道调度段直接平台化成新的全局 scheduler 抽象。
- 不把 Feishu/WeCom webhook、personal WeChat、BT 订阅启动逻辑强行揉成新的“统一 sidecar 平台”。
- 不因为 shared runtime 解耦而把渠道私有 UX 重新散回各渠道各自拼接。
- 不回到 BT 页面 proof、BT dispatch 取证或 Plex 实例追查。

## Done when

当前 **Telegram 生命周期编排边界瘦身** 主线视为 **已收口**，满足以下任一条即可：

1. Telegram 渠道生命周期里至少一段 sidecar 启停 helper 或 lifecycle 入口从 `telegram_bot.py` / `telegram_runtime_adapter.py` 之间抽离，且启动/停止顺序语义不变；
2. focused tests 能继续覆盖对应 sidecar 的启动/停止和 Telegram 主入口最小回归；
3. 默认分支全量 pytest 继续保持绿灯；
4. 文档继续保持分层一致，`STATUS.md` 只写当前快照，`NEXT_STEP.md` 只写当前唯一主线。

## After this step

1. 如果 Telegram 生命周期编排已收口一轮，就继续看 `telegram_bot.py` 剩余发送/格式化边界，或回到 `private_chat_runtime.py` 选下一条最小瘦身主线。
2. 如果热点文件暂时没有更小闭环，再继续补 Makefile / focused tests / 真实 smoke 的其他缺口。
3. 只有在 shared runtime 边界和热点大文件都没有更小闭环可做时，才重新考虑次级结构债。
