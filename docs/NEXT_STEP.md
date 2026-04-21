# Next step (v260)

## Current goal

- 当前质量硬化阶段的下一条最小主线切到 **`Makefile` / `verify-mainline` 补齐 download follow-up runtime 的固定质量入口**。
- 当前这条主线只观察 **快速质量入口**，把刚拆出的 `app/bot/download_follow_up_runtime.py` focused tests 纳入固定回归，不等到全量 pytest 才发现 follow-up 链退化。
- `app/bot/private_chat_runtime.py` 仍保留为当前另一块 `1421` 行热点文件，但这轮先不回头继续拆它，优先补齐更早暴露回归的质量 gate。
- 上一条已完成主线是 **`telegram_bot.py` 里的 `post_download_auto_import` / `download_completion_polling` 调度边界瘦身**：下载完成轮询与自动导入调度已抽到 `app/bot/download_follow_up_runtime.py`，当前不回退。
- 再上一条已完成主线是 **`app/bot/telegram_runtime_adapter.py` 的 message / callback 入口边界收口**：Telegram message / callback 入口共用的 chat/user 解析、去重落盘和 reply 包装已抽到 `app/bot/telegram_update_runtime.py`，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 尾部 confirm / 数字选项 / 搜索 fallback 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT TMDB / raw_bt follow-up 与 pending reminder 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT processing-path / classification follow-up 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 frustration / reset 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT 直接入口 pending 初始化分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 批量确认路由分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 只读探索 / cleanup 路由分支瘦身**，当前不回退。
- 更早一条已完成主线 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- `telegram_bot.py` 的 download follow-up 调度段已经完成单独收口；当前更小也更直接的下一步，是把这条 focused 回归接进固定质量入口。
- 这一步继续只做最小质量 gate 补强，不顺手放大成新的测试平台、后台平台化或大文件总重写。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。

## User value

- 让 `verify-mainline` 直接跑到 download follow-up runtime focused tests，后续这条链退化时能比全量 pytest 更早被挡住。
- 在默认分支已经稳绿的前提下，优先补齐“固定可复用质量入口”，降低长期人工挑命令的维护成本。
- 保持第 2 轮刚拆出的 follow-up runtime 有对应的固定守门员，不让它重新变成“拆出去了但没人固定跑”的悬空模块。

## Only do

- 只做一次保守补强：更新 `Makefile` / `tests/test_makefile.py`，把 download follow-up runtime focused 回归纳入固定入口。
- 保持现有 parser / routing / approval / SQLite 真相边界不变，不新增用户可感知功能，不改渠道外部协议。
- 保持当前 shared delivery 文本、中文日志和现有 confirm / cancel / follow-up 语义不回退。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线。

## Do not do

- 不放宽 approval、`jobs` / `job_event` / lease/version / SQLite 真相边界。
- 不新增功能、不扩协议、不顺手重写整个 `telegram_bot.py` / `private_chat_runtime.py`。
- 不把 Telegram 渠道调度段直接平台化成新的全局 scheduler 抽象。
- 不把 `verify-mainline` 重新塞回一长串难维护的散装 focused 命令。
- 不因为 shared runtime 解耦而把渠道私有 UX 重新散回各渠道各自拼接。
- 不回到 BT 页面 proof、BT dispatch 取证或 Plex 实例追查。

## Done when

当前 **`Makefile` / `verify-mainline` 补齐 download follow-up runtime 的固定质量入口** 主线视为 **已收口**，满足以下任一条即可：

1. `verify-mainline` 能直接跑到 `tests/test_download_follow_up_runtime.py` 的最小 focused 回归；
2. `tests/test_makefile.py` 能锁住这条入口，避免后续改 Makefile 时把 follow-up runtime gate 静默丢掉；
3. 默认分支全量 pytest 继续保持绿灯；
4. 文档继续保持分层一致，`STATUS.md` 只写当前快照，`NEXT_STEP.md` 只写当前唯一主线。

## After this step

1. 如果这条 quality gate 已收口，就继续看 `telegram_bot.py` 剩余发送/启动边界，或回到 `private_chat_runtime.py` 选下一条最小瘦身主线。
2. 如果热点文件暂时没有更小闭环，再继续补 Makefile / focused tests / 真实 smoke 的其他缺口。
3. 只有在 shared runtime 边界和热点大文件都没有更小闭环可做时，才重新考虑次级结构债。
