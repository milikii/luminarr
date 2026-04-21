# Next step (v254)

## Current goal

- 当前质量硬化阶段的下一条最小主线仍是 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口**。
- `raw_bt` 目录问询、BT TMDB 关联问询、下载器角色绑定解析、execution gate / sync policy helper、frustration / BT intent / BT choice 文本解析 helper、search reactive recovery helper、BT processing path pending state helper、BT classification pending state helper、BT TMDB association pending state helper 已分别抽成 `app/bot/raw_bt_destination_runtime.py`、`app/bot/bt_tmdb_association_runtime.py`、`app/bot/downloader_execution_runtime.py`、`app/bot/execution_runtime.py`、`app/bot/query_text_runtime.py`、`app/bot/search_recovery_runtime.py`、`app/bot/bt_processing_path_runtime.py`、`app/bot/bt_classification_runtime.py`，以及并入 `app/bot/bt_tmdb_association_runtime.py`；当前剩余最小闭环改为 **raw BT destination pending state helper** 的同类收口。
- 这一步继续只做最小边界解耦，不顺手放大成新的渠道平台化或大文件总重写。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1630 passed, 2 skipped`。

## User value

- 把 shared runtime 从 Telegram 内部 raw BT destination pending state 细节里再拔一层，减少后续修改某个渠道入口时误伤全渠道行为的概率。
- 在默认分支已经稳绿的前提下，优先继续降低热点文件耦合，避免未来回归再次堆到 `telegram_bot.py` 和 `private_chat_runtime.py`。

## Only do

- 只做 shared runtime 与 Telegram raw BT destination pending state helper 边界的最小解耦。
- 保持现有 parser / routing / approval / SQLite 真相边界不变，不新增用户可感知功能，不改渠道外部协议。
- 保持当前 shared delivery 文本、中文日志和现有 confirm / cancel / follow-up 语义不回退。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线。

## Do not do

- 不放宽 approval、`jobs` / `job_event` / lease/version / SQLite 真相边界。
- 不新增功能、不扩协议、不顺手重写整个 `telegram_bot.py` / `private_chat_runtime.py`。
- 不因为 shared runtime 解耦而把渠道私有 UX 重新散回各渠道各自拼接。
- 不回到 BT 页面 proof、BT dispatch 取证或 Plex 实例追查。

## Done when

当前 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 主线视为 **已收口**，满足以下任一条即可：

1. `app/bot/private_chat_runtime.py` 不再直接依赖当前选中的那段 Telegram 私有 helper，shared runtime 只通过中性 helper / adapter 继续推进相同行为；
2. focused tests 能继续覆盖对应渠道入口和 shared runtime 的最小回归，且默认分支全量 pytest 继续保持绿灯；
3. 文档继续保持分层一致，`STATUS.md` 只写当前快照，`NEXT_STEP.md` 只写当前唯一主线。

## After this step

1. 如果这条 raw BT destination pending state helper 解耦完成，就继续沿同一方向挑下一段最小边界收口点。
2. 如果这条解耦证明不值得继续细拆，就回到同一职责族里再找一个更小、更保守的结构降本点。
3. 只有在 shared runtime 边界和热点大文件都没有更小闭环可做时，再回到 Makefile / focused tests / 真实 smoke 入口补强。
