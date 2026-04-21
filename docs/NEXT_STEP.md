# Next step (v259)

## Current goal

- 当前质量硬化阶段的下一条最小主线切到 **`telegram_bot.py` 里的 `post_download_auto_import` / `download_completion_polling` 调度边界瘦身**。
- 当前这条主线只观察 **Telegram 渠道的 follow-up 调度段**，优先把下载完成轮询与自动导入调度 helper 从 `telegram_bot.py` 挤出的同文件协调里收口出去，不把执行真相散回渠道适配层。
- 上一条已完成主线是 **`app/bot/telegram_runtime_adapter.py` 的 message / callback 入口边界收口**：Telegram message / callback 入口共用的 chat/user 解析、去重落盘和 reply 包装已抽到 `app/bot/telegram_update_runtime.py`，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 尾部 confirm / 数字选项 / 搜索 fallback 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT TMDB / raw_bt follow-up 与 pending reminder 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT processing-path / classification follow-up 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 frustration / reset 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT 直接入口 pending 初始化分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 批量确认路由分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 只读探索 / cleanup 路由分支瘦身**，当前不回退。
- 更早一条已完成主线 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- `telegram_runtime_adapter.py` 的 message / callback 入口已完成单独收口；当前 Telegram 热点里更高风险、也更适合继续降本的是 `telegram_bot.py` 中同时管理 `post_download_auto_import`、`download_completion_polling` 和渠道启动/停止的调度段。
- 这一步继续只做最小边界解耦与热点分支瘦身，不顺手放大成新的渠道平台化、后台平台化或大文件总重写。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。

## User value

- 把高风险 follow-up 调度链从 Telegram 渠道大文件里剥出来，后续排查“下载完成轮询 -> 状态 follow-up -> 自动导入”时，不必再同时读 Telegram 发送和渠道启动逻辑。
- 在默认分支已经稳绿的前提下，优先继续降低热点文件耦合，避免未来回归再次堆到 `telegram_bot.py`。
- 让 focused tests 更贴近这条调度链本身，而不是继续把 follow-up 保护都堆在 `tests/test_telegram_bot.py`。

## Only do

- 只做一次保守瘦身：围绕 `post_download_auto_import` / `download_completion_polling` 调度边界抽出最小 helper 或 runtime。
- 保持现有 parser / routing / approval / SQLite 真相边界不变，不新增用户可感知功能，不改渠道外部协议。
- 保持当前 shared delivery 文本、中文日志和现有 confirm / cancel / follow-up 语义不回退。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线。

## Do not do

- 不放宽 approval、`jobs` / `job_event` / lease/version / SQLite 真相边界。
- 不新增功能、不扩协议、不顺手重写整个 `telegram_bot.py` / `private_chat_runtime.py`。
- 不把 Telegram 渠道调度段直接平台化成新的全局 scheduler 抽象。
- 不因为 shared runtime 解耦而把渠道私有 UX 重新散回各渠道各自拼接。
- 不回到 BT 页面 proof、BT dispatch 取证或 Plex 实例追查。

## Done when

当前 **`telegram_bot.py` 的 `post_download_auto_import` / `download_completion_polling` 调度边界瘦身** 主线视为 **已收口**，满足以下任一条即可：

1. `post_download_auto_import` 与 `download_completion_polling` 至少有一段最小调度 helper 从 `telegram_bot.py` 抽离，且 Telegram 启动/停止入口语义不变；
2. focused tests 能继续覆盖下载完成轮询、自动导入调度和 Telegram 启停的最小回归；
3. 默认分支全量 pytest 继续保持绿灯；
4. 文档继续保持分层一致，`STATUS.md` 只写当前快照，`NEXT_STEP.md` 只写当前唯一主线。

## After this step

1. 如果 `post_download_auto_import` / `download_completion_polling` 已收口一轮，就继续看 `telegram_bot.py` 里剩余的调度或发送边界是否还有更小闭环。
2. 如果 Telegram 调度热点没有更小闭环，再回到 `private_chat_runtime.py` 或 `import_to_library.py` 选下一条最小瘦身主线。
3. 只有在 shared runtime 边界和热点大文件都没有更小闭环可做时，再回到 Makefile / focused tests / 真实 smoke 入口补强。
