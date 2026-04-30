# Current status (v553)

## Current mainline
- `质量硬化`、`adult BT minimum wedge`、config 能力化解耦、Telegram 宿主解耦和 adult-only `btsub` 收口都保持完成态。
- 2026-04-30 已正式把 Stage 1 从规划态推进到实现态：`T16 成人 BT 下载前防重记忆层` 已完成并提交。
- 当前下一条执行起点切到 `T17 Telegram-first 高频主链交付层`；`T16` 的 canonical plan 仍是 `docs/plans/2026-04-30-adult-duplicate-memory-execution.md`。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 继续保持完成态；`cleanup_*_support.py` 当前为 `0` 个。
- adult-only BT 边界继续不变：direct `BT` / `magnet:?`` 仍先问 `观影 PT 链 / BT 成人链`，`btsub add` 继续只接受成人 BT 精确番号追踪，`watchlist sync` 继续 fail-closed。
- `adult_duplicate_memory_snapshot` sibling 真相、shared duplicate memory service、`duplicate_override` follow-up 和 operator tooling 已落地，当前 adult-only 下载链会在创建待确认前先做 duplicate gate。

## Current health
- `make quality` 通过（`28 passed`）。
- `make verify-mainline` 通过。
- `make verify-adult-bt-wedge` 通过（总计 `428 passed`）。
- `make lint` 通过。
- `T16` focused verification 通过：snapshot persistence `4 passed`、duplicate service/tooling `6 passed`、duplicate gate/runtime `5 passed`、main wiring `3 passed`。
- Telegram 成人 BT 真机 smoke 已完成（`2026-04-28`）。
- 当前 active docs root：`15`；docs gate 绿灯。

## Latest verification
- `2026-04-30` 冻结态冷启动一致性检查通过：`make quality`、`make verify-mainline`、`make verify-adult-bt-wedge`、`make lint` 全绿。
- `2026-04-30` `T16` focused verification 通过：`.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py -k adult_duplicate_memory_snapshot`（`4 passed`）、`.venv/bin/python -m pytest -q tests/test_adult_duplicate_memory.py tests/test_adult_duplicate_memory_tools.py`（`6 passed`）、`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k duplicate`（`5 passed`）、`.venv/bin/python -m pytest -q tests/test_main.py -k "qb_only_runtime_without_prowlarr_or_legacy_transmission or feishu_is_available or wecom"`（`3 passed`）。
- `.venv/bin/python -m pytest -q tests/test_bt_subscription_candidate_helpers.py tests/test_manage_bt_subscription.py` 通过（`50 passed`）。
- `.venv/bin/python -m pytest -q tests/test_search_media.py` 通过（`187 passed`）。
- Telegram 成人 BT 真机 evidence 继续可用：`logs/trace.log` 已记录 `成人搜 SSIS-483`、direct magnet、`BT 成人链`、`confirm bt-372f049d`、`status 3849...`。
- active docs root 预算验证：排除 `PROGRESS.md` / `BLOCKERS.md` 后为 `15`。

## Current biggest risk
- 当前最大风险已经从“Stage 1 三条子线一起开工”切到“Telegram-first 交付层回退 duplicate 语义”：如果 `T17` 只顾做 Telegram 交付，而把 `T16` 刚落地的 duplicate 提醒 / 显式继续语义重新埋回长文本里，最容易让新边界失守。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md 执行单轮主线施工。

当前主线已切到 `T17 Telegram-first 高频主链交付层`。保持 `T16` 的 duplicate gate 和 `duplicate_override` follow-up 不回退，只做 Telegram 高频主链的交付层收口；不要提前启动更大范围成人 BT 来源扩站或多渠道统一升级。
```
