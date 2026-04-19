# Next step (v221)

## Current goal

- 当前进行中的 promoted 主线是 **Jellyfin 单 provider 真实联调预备**。2026-04-19 已满足 `Done when` 第 1 条：refresh 失败日志已带 `provider=jellyfin / plex / emby` 显式字段；本轮闭环已完成，下一次继续时按 `After this step` 第 1 项进入 Jellyfin 单 provider 真实 refresh smoke，不在这条线上继续拆微分流。
- 当前选择 Jellyfin 而不是 Plex：`app/clients/jellyfin.py` 与 `app/clients/emby.py` 都走 `POST /Library/Refresh`，协议形状更接近，风险更低；Plex 继续留在后续再评估。
- 当前最小缺口是：refresh 成功/失败日志还只写泛化的“媒体库刷新”，还没有把 provider 名称显式打出来；后续真联调时排障信息不够聚焦。
- 2026-04-19 刚完成的主线是 **Jellyfin / Plex 真实联调重评估**：provider 缺配置时的静默关闭 refresh 已收口，focused tests 为 `10 passed, 46 deselected`。
- 再上一条刚完成主线是 **BT 批量任务显式批量确认**：`bt批量 / bt batch` 的只读批量预览与 `bt批量确认 / bt batch confirm` 的显式批量确认都已落地，focused tests 为 `11 passed, 312 deselected`。
- 再上一条已完成主线是 **PT live seeding 真相接入 cleanup 阻断**。冷启动审计已确认它满足文档出口；详细蓝图继续看 `docs/PT_LIVE_SEEDING_PLAN.md`。
- 更早一条已完成主线是 **`.ass` 字幕最小支持**。2026-04-19 已补齐 `.srt` + 最小 `.ass` 字幕翻译路径，focused tests 为 `10 passed`，导入后字幕 focused tests 为 `2 passed, 140 deselected`；详细闭环继续看 `docs/SERIES_ANIME_NAMING_LOG.md` 2.3。
- 更早完成主线：cleanup PT 最小保护窗口、Jellyfin / Plex provider 选择、最小人类可用入口补齐、shared private-chat 交付体验收口、`series / anime` 独立名称解析最小实现、`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身、下载完成轮询、Feishu 风险收口、持久化吞错收口都保持完成态，不回退。
- 当前主线蓝图统一写在 `docs/JELLYFIN_REAL_VERIFICATION_PLAN.md`。

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线蓝图：`docs/JELLYFIN_REAL_VERIFICATION_PLAN.md`
- 刚完成主线蓝图：`docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md`
- 再上一条主线蓝图：`docs/BT_BATCH_PLAN.md`
- 更早主线蓝图：`docs/PT_LIVE_SEEDING_PLAN.md`
- 刚完成主线蓝图 / 台账：`docs/SERIES_ANIME_NAMING_PLAN.md`、`docs/SERIES_ANIME_NAMING_LOG.md`
- 刚完成主线蓝图 / 台账：`docs/BT_SCORING_PLAN.md`、`docs/BT_SCORING_LOG.md`
- 刚完成主线蓝图 / 交付物：`docs/QUICK_START_PLAN.md`、`docs/DEPLOY_CHECKLIST.md`
- 更早主线台账：`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 当前优先交付：
  - 补 refresh 成功/失败日志里的 provider 可观测性，优先把 Jellyfin 路径打清楚
  - 保持用户侧 refresh 成功/失败文本边界不变，不改导入成功真相
  - 继续保留“当前正式本地真实 refresh 栈只有 Emby”这条边界，不伪装成 Jellyfin 已有现成真机入口
- 保持 Telegram / personal WeChat / Feishu / WeCom 四渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持 cleanup / search / approval / import / status / watchlist / btsub 既有协议和 guardrail 不回退
- 文档继续分层：`STATUS.md` 只保留当前快照；当前主线细节写在 `docs/JELLYFIN_REAL_VERIFICATION_PLAN.md`；刚完成的 readiness 评估继续留在 `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md`

## Do not do

- 不引入 DSL / 通用规则语言 / LLM 判分
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不新增 Jellyfin / Plex Docker 测试栈，不把这一步扩成环境编排大改
- 不把这一步改成自动 `confirm` / 自动 dispatch
- 不改 cleanup 删除范围、媒体库导入成功真相或字幕主线出口
- 不把这一步重新放大成 Jellyfin + Plex 双线并行、全量能力对齐、自动探测或新的下载器平台化主线

## Done when

当前 Jellyfin 单 provider 真实联调预备主线视为 **已收口**，满足以下任一条即可：

1. refresh 失败日志已带 `provider=jellyfin` 等显式字段，且 `.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py -k "refresh"` 全绿；
2. `docs/NEXT_STEP.md` / `docs/STATUS.md` / `README.md` / `AGENTS.md` / `docs/JELLYFIN_REAL_VERIFICATION_PLAN.md` 一致表达“当前主线是 Jellyfin 单 provider 真实联调预备”；
3. 本轮代码变更 `< 20` 行且只是对同一个 refresh 路径补一条诊断日志分支，触发 `AGENTS.md §11` 停机规则。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `AGENTS.md` / `docs/JELLYFIN_REAL_VERIFICATION_PLAN.md` / `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md` / `docs/BT_BATCH_PLAN.md` / `docs/PT_LIVE_SEEDING_PLAN.md` / 其余完成台账继续保持分层一致，不重新写回长台账

## After this step

1. 如果后续拿到 Jellyfin 实例，继续做单 provider 真实 refresh smoke
2. 如果 Jellyfin 继续缺实例或价值不足，再评估 Plex 或回到 BT 更大范围的用户页 / 编号范围页能力
