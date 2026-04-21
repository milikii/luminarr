# Next step (v258)

## Current goal

- 当前质量硬化阶段的下一条最小主线切到 **`private_chat_runtime.py` 继续细拆的收益递减重评估；若不值得继续，就转 `app/bot/telegram_runtime_adapter.py` 的 message / callback 入口边界**。
- 当前这条重评估仍以 **`app/bot/private_chat_runtime.py`** 为观察对象，不把执行真相再散回 `app/bot/telegram_bot.py`。
- 上一条已完成主线是 **`private_chat_runtime.py` 尾部 confirm / 数字选项 / 搜索 fallback 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT TMDB / raw_bt follow-up 与 pending reminder 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT processing-path / classification follow-up 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 frustration / reset 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT 直接入口 pending 初始化分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 批量确认路由分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 只读探索 / cleanup 路由分支瘦身**，当前不回退。
- 更早一条已完成主线 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- `raw_bt` 目录问询、BT TMDB 关联问询、下载器角色绑定解析、execution gate / sync policy helper、frustration / BT intent / BT choice 文本解析 helper、search reactive recovery helper、BT processing path pending state helper、BT classification pending state helper、BT TMDB association pending state helper、raw BT destination pending state helper、BT 流程入口 helper、BT follow-up lookup / logging helper，以及 BT 只读探索 / cleanup / 批量确认 / 直接入口执行 helper 已分别抽成共享 helper 或并入共享 runtime；当前同一文件里的主路由瘦身已推进到 **`private_chat_runtime.py` 尾部的 confirm / 数字选项 / 搜索 fallback 路由**，下一步先重评估是否还值得继续在同一文件里细拆。
- 这一步继续只做最小边界解耦与热点分支瘦身，不顺手放大成新的渠道平台化或大文件总重写。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。

## User value

- 先确认 `private_chat_runtime.py` 继续加 helper 是否还在真实降低维护成本，而不是只是把同一文件切得更碎但体积继续上涨。
- 如果同文件继续细拆已经进入收益递减，就把下一条更小闭环切到渠道适配层，优先重评估 `telegram_runtime_adapter.py` 的 message / callback 入口边界。
- 在默认分支已经稳绿的前提下，优先继续降低热点文件耦合，避免未来回归再次堆到 `telegram_bot.py` 和 `private_chat_runtime.py`。

## Only do

- 只做一次保守重评估：要么继续 `private_chat_runtime.py` 的最小收口，要么切到 `telegram_runtime_adapter.py` 的单一入口边界。
- 保持现有 parser / routing / approval / SQLite 真相边界不变，不新增用户可感知功能，不改渠道外部协议。
- 保持当前 shared delivery 文本、中文日志和现有 confirm / cancel / follow-up 语义不回退。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线。

## Do not do

- 不放宽 approval、`jobs` / `job_event` / lease/version / SQLite 真相边界。
- 不新增功能、不扩协议、不顺手重写整个 `telegram_bot.py` / `private_chat_runtime.py`。
- 不因为 shared runtime 解耦而把渠道私有 UX 重新散回各渠道各自拼接。
- 不回到 BT 页面 proof、BT dispatch 取证或 Plex 实例追查。

## Done when

当前 **`private_chat_runtime.py` 继续细拆的收益递减重评估** 主线视为 **已收口**，满足以下任一条即可：

1. 明确确认 `private_chat_runtime.py` 继续细拆仍有更小闭环，且不会只是把同一文件切成更多 helper；
2. 或者明确确认同文件继续细拆已经收益递减，并把下一条主线切到 `app/bot/telegram_runtime_adapter.py` 的单一入口边界；
3. focused tests 能继续覆盖对应渠道入口和 shared runtime 的最小回归，且默认分支全量 pytest 继续保持绿灯；
4. 文档继续保持分层一致，`STATUS.md` 只写当前快照，`NEXT_STEP.md` 只写当前唯一主线。

## After this step

1. 如果评估结果是同文件继续细拆已收益递减，就把下一轮切到 `app/bot/telegram_runtime_adapter.py` 的 message / callback 入口边界。
2. 如果评估结果是 `private_chat_runtime.py` 里仍有单一、可验证、不会放大文件体积的更小闭环，再继续沿同一方向推进一轮。
3. 只有在 shared runtime 边界和热点大文件都没有更小闭环可做时，再回到 Makefile / focused tests / 真实 smoke 入口补强。
