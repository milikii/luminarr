# Next step (v254)

## Current goal

- 当前质量硬化阶段的下一条最小主线切到 **热点大文件里 frustration / reset 路由分支的继续瘦身**。
- 上一条已完成主线是 **`private_chat_runtime.py` 里的 BT 直接入口 pending 初始化分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT 批量确认路由分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 只读探索 / cleanup 路由分支瘦身**，当前不回退。
- 更早一条已完成主线 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- `raw_bt` 目录问询、BT TMDB 关联问询、下载器角色绑定解析、execution gate / sync policy helper、frustration / BT intent / BT choice 文本解析 helper、search reactive recovery helper、BT processing path pending state helper、BT classification pending state helper、BT TMDB association pending state helper、raw BT destination pending state helper、BT 流程入口 helper、BT follow-up lookup / logging helper，以及 BT 只读探索 / cleanup / 批量确认 / 直接入口执行 helper 已分别抽成共享 helper 或并入共享 runtime；当前剩余最小闭环改为 **`private_chat_runtime.py` 里的 frustration / reset 路由分支**。
- 这一步继续只做最小边界解耦与热点分支瘦身，不顺手放大成新的渠道平台化或大文件总重写。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。

## User value

- 把 `private_chat_runtime.py` 里 frustration / reset 分支仍然混在一起的 pending job 查询、approval cancel、搜索候选清理和 BT pending cancel 再拆薄一点，减少后续修改取消 / 重来语义时误伤其他分支的概率。
- 在默认分支已经稳绿的前提下，优先继续降低热点文件耦合，避免未来回归再次堆到 `telegram_bot.py` 和 `private_chat_runtime.py`。

## Only do

- 只做 `private_chat_runtime.py` 中 frustration / reset 路由分支的最小瘦身。
- 保持现有 parser / routing / approval / SQLite 真相边界不变，不新增用户可感知功能，不改渠道外部协议。
- 保持当前 shared delivery 文本、中文日志和现有 confirm / cancel / follow-up 语义不回退。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线。

## Do not do

- 不放宽 approval、`jobs` / `job_event` / lease/version / SQLite 真相边界。
- 不新增功能、不扩协议、不顺手重写整个 `telegram_bot.py` / `private_chat_runtime.py`。
- 不因为 shared runtime 解耦而把渠道私有 UX 重新散回各渠道各自拼接。
- 不回到 BT 页面 proof、BT dispatch 取证或 Plex 实例追查。

## Done when

当前 **热点大文件里 frustration / reset 路由分支的继续瘦身** 主线视为 **已收口**，满足以下任一条即可：

1. `app/bot/private_chat_runtime.py` 当前选中的 frustration / reset 分支，不再继续把 pending job 查询、approval cancel、搜索候选清理和 BT pending cancel 混在同一段里；
2. focused tests 能继续覆盖对应渠道入口和 shared runtime 的最小回归，且默认分支全量 pytest 继续保持绿灯；
3. 文档继续保持分层一致，`STATUS.md` 只写当前快照，`NEXT_STEP.md` 只写当前唯一主线。

## After this step

1. 如果这条 frustration / reset 路由分支瘦身完成，就继续沿同一方向挑下一段最小边界收口点。
2. 如果这条解耦证明不值得继续细拆，就回到同一职责族里再找一个更小、更保守的结构降本点。
3. 只有在 shared runtime 边界和热点大文件都没有更小闭环可做时，再回到 Makefile / focused tests / 真实 smoke 入口补强。
