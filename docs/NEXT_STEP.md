# Next step (v217)

## Current goal

- 当前进行中的 promoted 主线是 **PT live seeding 真相接入 cleanup 阻断**。目标是在不放宽现有 fail-closed 边界的前提下，把 downloader 当前做种真相接到 PT cleanup guard。
- 这条主线只做“读 downloader live seeding 真相 -> 参与 `pt_min_seed_hours` 判断 -> 拿不到真相时显式中文日志 + fail-closed”这一条最小闭环。
- 上一条已完成主线是 **`.ass` 字幕最小支持**。2026-04-19 已补齐 `.srt` + 最小 `.ass` 字幕翻译路径，focused tests 为 `10 passed`，导入后字幕 focused tests 为 `2 passed, 140 deselected`；详细闭环继续看 `docs/SERIES_ANIME_NAMING_LOG.md` 2.3。
- 再上一条已完成主线仍是 **cleanup PT 最小保护窗口**。2026-04-19 已验证：当 `pt_min_seed_hours` > 0 时，PT 任务会按 `download_monitor.completion_observed_at` 做保守阻断，必要真相缺失时 fail-closed；这一步不宣称已接入 downloader live seeding 秒数。
- 更早完成主线：Jellyfin / Plex provider 选择、最小人类可用入口补齐、shared private-chat 交付体验收口、`series / anime` 独立名称解析最小实现、`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身、下载完成轮询、Feishu 风险收口、持久化吞错收口都保持完成态，不回退。
- 当前主线蓝图统一写在 `docs/PT_LIVE_SEEDING_PLAN.md`。

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线蓝图：`docs/PT_LIVE_SEEDING_PLAN.md`
- 刚完成主线蓝图 / 台账：`docs/SERIES_ANIME_NAMING_PLAN.md`、`docs/SERIES_ANIME_NAMING_LOG.md`
- 刚完成主线蓝图 / 台账：`docs/BT_SCORING_PLAN.md`、`docs/BT_SCORING_LOG.md`
- 刚完成主线蓝图 / 交付物：`docs/QUICK_START_PLAN.md`、`docs/DEPLOY_CHECKLIST.md`
- 更早主线台账：`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 当前优先交付：
  - 给 PT cleanup guard 接入 downloader live seeding 真相
  - 真相存在时按 live seeding 秒数判断 `pt_min_seed_hours`
  - 真相缺失、格式异常或下载器暂不支持时，继续显式中文日志 + fail-closed
- 保持 Telegram / personal WeChat / Feishu / WeCom 四渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持 cleanup / search / approval / import / status / watchlist / btsub 既有协议和 guardrail 不回退
- 文档继续分层：`STATUS.md` 只保留当前快照；PT live seeding 方案细节继续写在 `docs/PT_LIVE_SEEDING_PLAN.md`，不把长台账回灌到 `STATUS.md`

## Do not do

- 不引入 DSL / 通用规则语言 / LLM 判分
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不把“拿不到 live seeding 真相”改成乐观放行
- 不改 cleanup 删除范围、媒体库导入成功真相或字幕主线出口
- 不把这一步扩成 Jellyfin / Plex 联调、BT 批量任务或新的下载器平台化主线

## Done when

当前 PT live seeding 主线视为 **已收口**，满足以下任一条即可：

1. cleanup PT guard 已能优先读取 downloader live seeding 真相，且 `tests/test_cleanup_downloaded_source.py -k pt_seed_window` 全绿；
2. 当前 PT 角色绑定使用的下载器协议已接入 live seeding 真相，真相缺失或异常时仍显式中文日志 + fail-closed；
3. `docs/NEXT_STEP.md` / `docs/STATUS.md` / `README.md` / `AGENTS.md` 一致表达“当前主线是 PT live seeding 真相接入 cleanup 阻断”，且不把范围写大到 cleanup 自动化或乐观放行。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `AGENTS.md` / `docs/PT_LIVE_SEEDING_PLAN.md` / `docs/SERIES_ANIME_NAMING_LOG.md` / 其余完成台账继续保持分层一致，不重新写回长台账

## After this step

1. 重新评估 Jellyfin / Plex 真实联调、BT 批量任务两者里哪一个更值钱
2. 把该事项提升成新的 promoted 主线，并在本文件补齐 `Current goal / Only do / Done when`
