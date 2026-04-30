# Current status (v552)

## Current mainline
- `质量硬化`、`adult BT minimum wedge`、config 能力化解耦、Telegram 宿主解耦和 adult-only `btsub` 收口都保持完成态。
- 2026-04-30 已正式重开新的 Stage 1 规划态：`Telegram-first 主操作者控制面 + 成人 BT 来源底座` 已写回仓库文档，但代码尚未开始实现。
- 当前唯一执行起点是 `T16 成人 BT 下载前防重记忆层`；canonical plan 是 `docs/plans/2026-04-30-adult-duplicate-memory-execution.md`。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态；`cleanup_*_support.py` 当前为 `0` 个。
- adult-only BT 边界继续不变：direct `BT` / `magnet:?`` 仍先问 `观影 PT 链 / BT 成人链`，`btsub add` 继续只接受成人 BT 精确番号追踪，`watchlist sync` 继续 fail-closed。

## Current health
- `make quality` 通过（`28 passed`）。
- `make verify-mainline` 通过。
- `make verify-adult-bt-wedge` 通过（总计 `423 passed`）。
- `make lint` 通过。
- Telegram 成人 BT 真机 smoke 已完成（`2026-04-28`）。
- 当前 active docs root：`15`；docs gate 绿灯。

## Latest verification
- `2026-04-30` 冻结态冷启动一致性检查通过：`make quality`、`make verify-mainline`、`make verify-adult-bt-wedge`、`make lint` 全绿。
- `.venv/bin/python -m pytest -q tests/test_bt_subscription_candidate_helpers.py tests/test_manage_bt_subscription.py` 通过（`50 passed`）。
- `.venv/bin/python -m pytest -q tests/test_search_media.py` 通过（`187 passed`）。
- Telegram 成人 BT 真机 evidence 继续可用：`logs/trace.log` 已记录 `成人搜 SSIS-483`、direct magnet、`BT 成人链`、`confirm bt-372f049d`、`status 3849...`。
- active docs root 预算验证：排除 `PROGRESS.md` / `BLOCKERS.md` 后为 `15`。

## Current biggest risk
- 当前最大风险已经从“完成态失守”切到“Stage 1 三条子线一起开工”：如果在 `T16` 落地前同时把 Telegram 交付层、来源扩站和 duplicate memory 混在一轮里，最容易把 adult-only BT 边界重新带偏。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md 执行单轮主线施工。

当前主线已切到 `T16 成人 BT 下载前防重记忆层`。先读 `docs/plans/2026-04-30-adult-duplicate-memory-execution.md`，只做 sibling snapshot 真相、shared duplicate gate、`duplicate_override` follow-up 和 focused tests；不要提前启动 Telegram buttons、Feishu/WeCom 交互增强或更大范围成人 BT 扩站。
```
