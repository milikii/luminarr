# Current status (v563)

## Current mainline
- `质量硬化`、adult BT minimum wedge、config 能力化解耦、Telegram 宿主解耦和 adult-only `btsub` 收口都保持完成态。
- `T16 成人 BT 下载前防重记忆层`、`T17 Telegram-first 高频主链交付层`、`T18 成人 BT 来源角色底座`、`T19 Stage 1 聚合验证与运维真相同步` 已完成；`2026-05-07` 的真实 Telegram 入站、PT 后半段和 fresh-hash 导入后处理 smoke 也已补齐，当前唯一下一步从执行阶段切到收尾阶段。
- `app/bot/private_chat_runtime.py` 继续作为 shared private-chat runtime 边界；`app/bot/telegram_bot.py` 继续作为 Telegram wrapper 边界；shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口继续保持完成态。
- adult-only BT 边界继续不变：direct `BT` / `magnet:?` 仍先问 `观影 PT 链 / BT 成人链`，`btsub add` 继续只接受成人 BT 精确番号追踪，`watchlist sync` 继续 fail-closed。
- 当前单一 Stage 1 focused verification 入口已固定为 `make verify-stage1`；`make verify-adult-bt-wedge` 保留为成人 BT 专线补充验证。

## Current health
- `make quality` 通过。
- `make verify-mainline` 通过。
- `make verify-stage1` 通过（`8` 个子组、`44 passed`）。
- `make verify-adult-bt-wedge` 通过（总计 `429 passed`）。
- `make lint` 通过。
- Telegram-first focused gate 与实机证据都已补齐：`make verify-stage1-telegram-delivery` 通过（`16 passed`）；`2026-05-07` 已确认 `.env` 中 Telegram token 与默认代理有效，替代代理 `http://192.168.2.220:7890` 调 `getMe` 返回 `200 / ok=true`；同日 `logs/trace.log` 已补到真实 `ping` / `start` 入站、`功夫熊猫 -> PT 资源卡 -> dispatch -> 下载状态 ✓`，以及 `超人 -> PT 资源卡 -> 已添加下载 -> 下载状态 ⏳ -> import.succeeded / metadata.succeeded / subtitle.skipped / refresh.succeeded / telegram.summary_sent`。
- 仓库内最近一轮真实 Telegram trace 证据仍可复查：`logs/trace.log` 保留 `成人搜 SSIS-483`、direct magnet、`BT 成人链`、`confirm bt-372f049d`、`status 3849...` 的完整链路。
- 当前 active docs root：`15`；docs gate 预算继续满足。

## Latest verification
- `2026-05-07` Telegram 入口收口复核：Telegram 渠道已删除“已添加下载”消息中的独立 `查看状态` 按钮，也已删除实时进度卡片上的 `查看状态` 按钮；Telegram 继续保留实时进度卡片和最终总结通知。
- `2026-05-07` 超人 fresh-hash 完结复核：`job_event` 已记录 `import.succeeded`、`metadata.succeeded`、`subtitle.skipped`、`refresh.succeeded`、`telegram.summary_sent`，说明 fresh hash `52bde7...` 已完成导入与后处理。
- `2026-05-07` 重启恢复复核：对 fresh hash `52bde7...` 重启 `app.main` 后，`download_monitor.telegram_progress_last_synced_at` 从 `08:26:18` 推进到 `08:27:57`、再到 `08:28:10`，持久化进度文本也从 `3%` 刷到 `4%`，证明未完成任务卡片在重启后会继续同步。
- `2026-05-07` 新 hash PT 复核：`logs/trace.log` 记录到 `15:54:22` inbound `超人`、`15:54:56` `【PT资源卡】 3d9006a4`、`15:56:12` `confirm_dispatch/confirm_finalize succeeded`、`15:56:14` reply `已添加下载：Superman 2025...`、`15:57:58` reply `下载状态 ⏳`；`job_event` 与 `download_monitor` 确认新 hash `52bde7...` 当前仍在下载中。
- `2026-05-07` 真实 PT 后半段复核：`logs/trace.log` 记录到 `15:35:02` inbound `功夫熊猫`、`15:35:21` `【PT资源卡】 a6a75e1b`、`15:35:27` `confirm_dispatch/confirm_finalize succeeded`、`15:40:22` reply `下载状态 ✓`；`job_event` 同步记录新的 `downloader.succeeded` 与 `downloader.completed_observed`。
- `2026-05-07` 真实 Telegram 入站复核：`logs/trace.log` 记录到 `14:38:55` inbound `ping`、`14:38:57` reply `候选作品：ping ✓`、`14:38:57` inbound `start`、`14:39:14` reply `候选作品：start ✓`，证明当前会话已恢复 Telegram 入站与回包。
- `2026-05-07` 修正后的 Telegram 环境复核：`.env` 中 `TELEGRAM_BOT_TOKEN` 已正确加载（非空、包含 `:`）；当前 `.env` 默认代理为 `http://192.168.2.106:10808`；替代代理 `http://192.168.2.220:7890` 也可达，且 Telegram Bot API `getMe` 通过该代理返回 `200 / ok=true`。
- `2026-05-07` Telegram 环境补充说明：宿主直连 `api.telegram.org` 仍不稳定，但当前已通过可用代理和本地运行态补到真实入站与后半段 smoke；后续若继续加做实机复验，应作为增量证据处理。

## Current biggest risk
- 当前最大风险已经从“Stage 1 三条子线语义会不会互相带偏”切到“并行未提交改动分组”：Telegram 真实 smoke 已补到 fresh-hash 完整闭环，且 Telegram 渠道已去掉多余 `查看状态` 入口；当前主要风险是工作树里仍混有其他并行任务改动，提交时必须按主线拆组。
- `cleanup_*_support.py` 当前为 `0` 个。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md 进入收尾阶段。

Stage 1 (`T16`~`T19`) 已通过 `make verify-stage1` 收口，且 `2026-05-07` 已有真实 Telegram 入站与 PT 后半段 smoke。当前这一轮只做 QA / ship / 文档漂移复查；不要重开新功能线。若你要追加新的真实 Telegram smoke，先确认当前机器可达 `api.telegram.org` 且本地 `app.main` 在运行，再把新证据作为增量补上。
```
