# Current status (v555)

## Current mainline
- `质量硬化`、adult BT minimum wedge、config 能力化解耦、Telegram 宿主解耦和 adult-only `btsub` 收口都保持完成态。
- `T16 成人 BT 下载前防重记忆层`、`T17 Telegram-first 高频主链交付层`、`T18 成人 BT 来源角色底座`、`T19 Stage 1 聚合验证与运维真相同步` 已完成；当前唯一下一步从执行阶段切到收尾阶段。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界；shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口继续保持完成态。
- adult-only BT 边界继续不变：direct `BT` / `magnet:?` 仍先问 `观影 PT 链 / BT 成人链`，`btsub add` 继续只接受成人 BT 精确番号追踪，`watchlist sync` 继续 fail-closed。
- 当前单一 Stage 1 focused verification 入口已固定为 `make verify-stage1`；`make verify-adult-bt-wedge` 保留为成人 BT 专线补充验证。

## Current health
- `make quality` 通过。
- `make verify-mainline` 通过。
- `make verify-stage1` 通过（`8` 个子组、`43 passed`）。
- `make verify-adult-bt-wedge` 通过（总计 `429 passed`）。
- `make lint` 通过。
- Telegram-first 等价证据已补充：`make verify-stage1-telegram-delivery` 通过（`16 passed`）；当前环境快照同时显示 `telegram bot api unreachable`、`no luminarr process running`，因此本轮未能补到新的真实 Telegram 入站 smoke。
- 仓库内最近一轮真实 Telegram trace 证据仍可复查：`logs/trace.log` 保留 `成人搜 SSIS-483`、direct magnet、`BT 成人链`、`confirm bt-372f049d`、`status 3849...` 的完整链路。
- 当前 active docs root：`15`；docs gate 预算继续满足。

## Latest verification
- `2026-04-30` `make verify-stage1-duplicate-memory` 通过：snapshot persistence（`4 passed`）、duplicate service/tooling（`6 passed`）、duplicate gate/runtime（`6 passed`）。
- `2026-04-30` `make verify-stage1-telegram-delivery` 通过：delivery renderer/runtime（`10 passed`）、Telegram-first 高频主链 focused path（`6 passed`）。
- `2026-04-30` `make verify-stage1-bt-source-roles` 通过：source role registry（`3 passed`）、helper-only/read-only contract（`7 passed`）、main wiring（`1 passed`）。
- `2026-04-30` 仓库级 gate 继续全绿：`make quality`、`make verify-mainline`、`make verify-adult-bt-wedge`、`make lint` 通过。
- `2026-04-30` Telegram 环境等价证据：`.venv/bin/python -c "from pathlib import Path; from app.maintenance.cleanup_verification_docs import _run_telegram_bot_api_snapshot; print(_run_telegram_bot_api_snapshot(Path('.')))"` 返回 `telegram bot api unreachable`；`.venv/bin/python -c "from pathlib import Path; from app.maintenance.cleanup_verification_docs import _run_runtime_process_snapshot; print(_run_runtime_process_snapshot(Path('.')))"` 返回 `no luminarr process running`。

## Current biggest risk
- 当前最大风险已经从“Stage 1 三条子线语义会不会互相带偏”切到“环境侧 Telegram 可达性漂移”：代码与 focused gate 已经收口，但若这台机器暂时打不到 `api.telegram.org` 或本地没有运行中的 `app.main`，就无法在这一轮补新的真实 Telegram 入站 smoke。
- `cleanup_*_support.py` 当前为 `0` 个。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md 进入收尾阶段。

Stage 1 (`T16`~`T19`) 已通过 `make verify-stage1` 收口。当前这一轮只做 QA / ship / 文档漂移复查；不要重开新功能线。如果你要补真实 Telegram smoke，先恢复当前机器到可达 `api.telegram.org` 且本地 `app.main` 在运行的状态，再单独复验。
```
