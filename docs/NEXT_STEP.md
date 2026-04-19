# Next step (v217)

## Current goal

- 当前 promoted 主线：**cleanup PT 最小保护窗口**。本轮只补保守阻断：当 `pt_min_seed_hours` > 0 时，若 PT 下载的 `download_monitor.completion_observed_at` 未满最小时长，或必要真相缺失，则 `cleanup inspect` / `cleanup` 显式拒绝。
- 这一步不宣称已接入 downloader live seeding 秒数；只允许复用现有 completion observation 真相做保守保护，不扩成新的 cleanup workflow。
- 上一条完成主线是 **Jellyfin / Plex 支持已基本完成**。2026-04-19 的 provider 选择 focused tests 为 `56 passed`；历史验收细节继续看 `docs/JELLYFIN_PLEX_PLAN.md` 与 `docs/STATUS.md`
- 刚完成主线：**最小人类可用入口继续补齐已完成**；部署蓝图继续看 `docs/QUICK_START_PLAN.md`，交付物继续看 `docs/DEPLOY_CHECKLIST.md`
- 上一条完成主线：**shared private-chat 交付体验收口已完成**；详细闭环继续写在 `docs/SHARED_DELIVERY_UX_LOG.md`
- 再上一条完成主线：**`series / anime` 独立名称解析最小实现已完成**；详细闭环继续写在 `docs/SERIES_ANIME_NAMING_LOG.md`
- 更早完成主线：**`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化已完成**；详细闭环继续写在 `docs/CLEANUP_SLIMMING_LOG.md`
- 更早完成主线：`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身、下载完成轮询、Feishu 风险收口、持久化吞错收口都保持完成态，不回退
- 当前最小闭环：给 PT cleanup 补最小保护窗口基线，不改删除范围、不改四渠道文本协议、不把 BT 或 raw_bt 一起拉进来
- 当前主线蓝图统一写在 `docs/JELLYFIN_PLEX_PLAN.md`

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线蓝图：`docs/JELLYFIN_PLEX_PLAN.md`
- 刚完成主线蓝图 / 台账：`docs/BT_SCORING_PLAN.md`、`docs/BT_SCORING_LOG.md`
- 刚完成主线蓝图 / 交付物：`docs/QUICK_START_PLAN.md`、`docs/DEPLOY_CHECKLIST.md`
- 更早主线台账：`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/SERIES_ANIME_NAMING_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 当前优先交付：
  - `cleanup inspect` / `cleanup` 在 PT 场景下能按 `pt_min_seed_hours` 做保守阻断
  - 真相缺失时显式中文日志 + fix hint，fail-closed
  - 文档同步说明这一步是“completion observation 时间窗保护”，不是 live seeding 秒数能力
- 保持 Telegram / personal WeChat / Feishu / WeCom 四渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持 cleanup / search / approval / import / status / watchlist / btsub 既有协议和 guardrail 不回退
- 文档继续分层：`STATUS.md` 只保留当前快照；`CLEANUP_VERIFICATION_WINDOW.md` 继续只保留 cleanup 完成窗口历史证据，不把这次新 guard 的实现台账写回窗口文档

## Do not do

- 不引入 DSL / 通用规则语言 / LLM 判分
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不在这一步引入自动 `confirm`、自动下载、新 workflow、媒体库自动探测或其他新集成
- 不把这一步变成站点白名单平台、偏好学习器或自动 confirm 一条龙
- 不把这一步包装成“已接入完整 PT live seeding 信息”或顺手改 BT / raw_bt cleanup 边界

## Done when

本主线满足以下三点即可收口：

1. `cleanup inspect` / `cleanup` 在 PT 任务上，当 `pt_min_seed_hours` > 0 且完成观察时间未满最小时长时，会显式拒绝并给出中文 fix hint；
2. `cleanup inspect` / `cleanup` 在 PT 任务上，当 `pt_min_seed_hours` > 0 但缺少 `download_monitor.completion_observed_at` 等必要真相时，会 fail-closed，而不是静默放行；
3. focused tests 和一条本地最小验证都能证明：现有 cleanup 删除范围、四渠道协议和 BT / raw_bt 边界没有被顺手改坏。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `verification docs gate` 与 cleanup 完成态证据持续通过
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `AGENTS.md` / `docs/JELLYFIN_PLEX_PLAN.md` / `docs/QUICK_START_PLAN.md` / `docs/DEPLOY_CHECKLIST.md` / 其余完成台账继续保持分层一致，不重新写回长台账

## After this step

1. 回到“当前没有进行中的 promoted 主线”的切线状态
2. 由用户明确下一条要做的事项
3. 把该事项提升成新的 promoted 主线，并在本文件补齐 `Current goal / Only do / Done when`
