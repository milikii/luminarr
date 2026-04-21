# Next step (v264)

## Current goal

- 当前质量硬化阶段的下一条最小主线切到 **`private_chat_runtime.py` 的 import 路由边界瘦身**。
- 刚完成的上一条主线是 **`private_chat_runtime.py` 的状态查询路由边界瘦身**：状态查询路由已抽到 `app/bot/private_chat_status_runtime.py`，并把 status focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 personal WeChat 登录路由边界瘦身**：登录路由已抽到 `app/bot/private_chat_login_runtime.py`，并把 personal WeChat 登录 focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 trace 包装边界瘦身**：trace 路径解析、入站日志和 reply trace 包装已抽到 `app/bot/private_chat_trace_runtime.py`，`verify-mainline` 已补进 trace focused tests，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 digit-selection 路由边界瘦身**：澄清态判断、下载器解析和 add 调度已抽到 `app/bot/private_chat_selection_runtime.py`，并补了 digit focused tests，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 confirm 路由边界瘦身**：job 关联查询、workflow 分流和 pending add fallback 已抽到 `app/bot/private_chat_confirm_runtime.py`，并补了 confirm focused tests，当前不回退。
- 再上一条主线是 **Telegram 发送 helper 边界瘦身**：媒资发送、文本发送和 Telegram 图片/文件判定已抽到 `app/bot/telegram_delivery_runtime.py`，`telegram_runtime_adapter.py` 已直接复用这层发送出口，当前不回退。
- 再上一条主线是 **Telegram reply formatter 边界瘦身**：搜索卡片、下载审批、导入审批三段 Telegram 特有文本整形已抽到 `app/bot/telegram_reply_formatter.py`，当前不回退。
- 再上一条主线是 **Telegram 生命周期编排边界瘦身**：sidecar 启停、Application lifecycle 入口、BT scheduler loop / 日志 / downloader resolution 都已收进 `app/bot/telegram_sidecar_runtime.py`，当前不回退。
- `app/bot/private_chat_runtime.py` 仍保留为当前 `1203` 行热点文件；状态查询路由已抽离后，下一块更小也更贴近高风险副作用边界的段落，是 import 路由里仍直接读取 `ImportToLibraryService` 并触发导入审批链。
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
- `telegram_bot.py` 的入口边界、follow-up 调度边界、生命周期编排、reply formatter 和发送 helper 都已经补过一轮；`private_chat_runtime.py` 的状态查询路由也已收口，当前更小也更直接的下一步，是把 import 这段 shared runtime/service wiring 从主调度里切出去。
- 这一步继续只做最小边界瘦身，不顺手放大成新的导入平台、统一审批总线或大文件总重写。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1653 passed, 2 skipped`。

## User value

- 在状态查询路由已经抽离并补进固定 gate 后，继续收 import 路由，可以让 shared runtime 少直接碰 `ImportToLibraryService` 调用细节和导入审批入口。
- 在默认分支已经稳绿、固定 gate 已补齐的前提下，优先继续降低热点文件体积和 shared runtime/service 耦合。
- 避免 `private_chat_runtime.py` 的主调度函数继续同时背负 shared routing 和导入副作用 service 调度。

## Only do

- 只做一次保守瘦身：围绕 import 路由抽出最小 helper 或 runtime。
- 保持现有 parser / routing / approval / SQLite 真相边界不变，不新增用户可感知功能，不改渠道外部协议。
- 保持当前导入审批文本、导入执行边界、中文日志和现有 confirm / cancel / auto-import 语义不回退。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线。

## Do not do

- 不放宽 approval、`jobs` / `job_event` / lease/version / SQLite 真相边界。
- 不新增功能、不扩协议、不顺手重写整个 `telegram_bot.py` / `private_chat_runtime.py`。
- 不把 Telegram 渠道调度段直接平台化成新的全局 scheduler 抽象。
- 不改 import 协议、导入审批文本语义或 `ImportToLibraryService` 的 SQLite / approval 真相边界。
- 不调整 `confirm` / `select` 文本协议，不改 pending add / pending import / candidate mapping / trace 日志内容语义。
- 不把 Feishu/WeCom webhook、personal WeChat、BT 订阅启动逻辑强行揉成新的“统一 sidecar 平台”。
- 不因为 shared runtime 解耦而把渠道私有 UX 重新散回各渠道各自拼接。
- 不回到 BT 页面 proof、BT dispatch 取证或 Plex 实例追查。

## Done when

当前 **`private_chat_runtime.py` 的 import 路由边界瘦身** 主线视为 **已收口**，满足以下任一条即可：

1. import 路由里的 service 读取、导入执行或 reply 分发至少一段从 `private_chat_runtime.py` 抽离，且导入审批文本语义不变；
2. focused tests 能继续覆盖 import 路由和当前 shared runtime 最小回归；
3. 默认分支全量 pytest 继续保持绿灯；
4. 文档继续保持分层一致，`STATUS.md` 只写当前快照，`NEXT_STEP.md` 只写当前唯一主线。

## After this step

1. 如果 import 路由已收口一轮，就继续留在 `private_chat_runtime.py` 选下一条最小瘦身主线，或补对应 focused gate。
2. 如果热点文件暂时没有更小闭环，再继续补 Makefile / focused tests / 真实 smoke 的其他缺口。
3. 只有在 shared runtime 边界和热点大文件都没有更小闭环可做时，才重新考虑次级结构债。
