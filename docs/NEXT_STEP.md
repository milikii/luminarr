# Next step (v217)

## Current goal

- 当前没有进行中的 promoted 主线；上一条完成主线是 **Jellyfin / Plex 支持已基本完成**。2026-04-19 的 provider 选择 focused tests 为 `56 passed`；历史验收细节继续看 `docs/JELLYFIN_PLEX_PLAN.md` 与 `docs/STATUS.md`
- 刚完成主线：**最小人类可用入口继续补齐已完成**；部署蓝图继续看 `docs/QUICK_START_PLAN.md`，交付物继续看 `docs/DEPLOY_CHECKLIST.md`
- 上一条完成主线：**shared private-chat 交付体验收口已完成**；详细闭环继续写在 `docs/SHARED_DELIVERY_UX_LOG.md`
- 再上一条完成主线：**`series / anime` 独立名称解析最小实现已完成**；详细闭环继续写在 `docs/SERIES_ANIME_NAMING_LOG.md`
- 更早完成主线：**`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化已完成**；详细闭环继续写在 `docs/CLEANUP_SLIMMING_LOG.md`
- 更早完成主线：`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身、下载完成轮询、Feishu 风险收口、持久化吞错收口都保持完成态，不回退
- 当前最小闭环：本轮只保留文档切线和交接整理；后续若要继续做“其他事情”，必须先把候选事项提升成新的 promoted 主线，再开工
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

- 当前不自动启动新施工；只维护完成态文档一致性和交接入口
- 当前优先交付：
  - 保持当前完成态文档一致
  - 后续若要继续做其他事项，先在本文写清新的 `Current goal / Only do / Done when`
- 保持 Telegram / personal WeChat / Feishu / WeCom 四渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持 cleanup / search / approval / import / status / watchlist / btsub 既有协议和 guardrail 不回退
- 文档继续分层：`STATUS.md` 只保留当前快照，`JELLYFIN_PLEX_PLAN.md` 承接当前完成态主线蓝图，`BT_SCORING_PLAN.md` / `QUICK_START_PLAN.md` / `DEPLOY_CHECKLIST.md` 保持刚完成主线与部署主线的蓝图和交付物定位，其余完成台账继续只作历史闭环入口
- 保持 cleanup 完成态证据、docs gate、quick start 完成态和 shared delivery 完成态结论稳定，不回退成“仍在进行中”

## Do not do

- 不引入 DSL / 通用规则语言 / LLM 判分
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不在这一步引入自动 `confirm`、自动下载、新 workflow、媒体库自动探测或其他新集成
- 不把这一步变成站点白名单平台、偏好学习器或自动 confirm 一条龙
- 不在本文还没切线前直接启动任何新的 promoted 主线

## Done when

当前文档切线状态视为 **已收口**，满足以下两点即可：

1. `docs/NEXT_STEP.md` / `docs/STATUS.md` / `README.md` / `AGENTS.md` 一致表达“当前没有进行中的 promoted 主线，后续继续其他事项前先切线”；
2. Jellyfin / Plex、quick start、BT 评分器、shared delivery、`series / anime` 等已完成主线的蓝图 / 台账入口保持不变。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `verification docs gate` 与 cleanup 完成态证据持续通过
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `docs/JELLYFIN_PLEX_PLAN.md` / `docs/QUICK_START_PLAN.md` / `docs/DEPLOY_CHECKLIST.md` / 其余完成台账继续保持分层一致，不重新写回长台账

## After this step

1. 由用户明确下一条要做的事项
2. 把该事项提升成新的 promoted 主线，并在本文件补齐 `Current goal / Only do / Done when`
