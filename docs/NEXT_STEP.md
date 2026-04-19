# Next step (v217)

## Current goal

- 当前进行中的 promoted 主线是 **`.ass` 字幕最小支持**。目标是在不改 approval / import 真相、不扩大字幕能力边界的前提下，让现有字幕翻译链在 `.srt` 之外再支持最小 `.ass` 文本替换。
- 这条主线承接 `docs/SERIES_ANIME_NAMING_PLAN.md` §7 已写明的边界：只识别 `.ass`、只处理 `Dialogue:` 文本字段、保留原 Style / 时间轴 / 其余结构，不扩成 `.ssa`、嵌入字幕、OCR 或复杂样式改写。
- 上一条已完成主线仍是 **cleanup PT 最小保护窗口**。2026-04-19 已验证：当 `pt_min_seed_hours` > 0 时，PT 任务会按 `download_monitor.completion_observed_at` 做保守阻断，必要真相缺失时 fail-closed；这一步不宣称已接入 downloader live seeding 秒数。
- 更早完成主线：Jellyfin / Plex provider 选择、最小人类可用入口补齐、shared private-chat 交付体验收口、`series / anime` 独立名称解析最小实现、`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身、下载完成轮询、Feishu 风险收口、持久化吞错收口都保持完成态，不回退。
- 当前主线蓝图和详细历史分别看 `docs/SERIES_ANIME_NAMING_PLAN.md` §7 与 `docs/SERIES_ANIME_NAMING_LOG.md` 2.3。

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线蓝图：`docs/SERIES_ANIME_NAMING_PLAN.md`
- 当前主线台账：`docs/SERIES_ANIME_NAMING_LOG.md`
- 刚完成主线蓝图 / 台账：`docs/BT_SCORING_PLAN.md`、`docs/BT_SCORING_LOG.md`
- 刚完成主线蓝图 / 交付物：`docs/QUICK_START_PLAN.md`、`docs/DEPLOY_CHECKLIST.md`
- 更早主线台账：`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 当前优先交付：
  - 给 `app/services/subtitle_translator.py` 增加 `.ass` 文件识别、`Dialogue:` 文本提取、最小翻译回写
  - 保持 `.srt` 现有行为和输出文件命名不回退
  - 让 `.ass` 新能力继续只服务现有导入后字幕翻译链，不引入新 workflow、新审批或新渠道协议
- 保持 Telegram / personal WeChat / Feishu / WeCom 四渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持 cleanup / search / approval / import / status / watchlist / btsub 既有协议和 guardrail 不回退
- 文档继续分层：`STATUS.md` 只保留当前快照；`.ass` 主线详细闭环继续合并进 `docs/SERIES_ANIME_NAMING_LOG.md` 2.3，不把长台账回灌到 `STATUS.md`

## Do not do

- 不引入 DSL / 通用规则语言 / LLM 判分
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不在这一步引入 `.ssa`、嵌入字幕流、OCR、多语言批量字幕平台或复杂样式改写
- 不改现有 metadata scraping、refresh、import 成功真相和失败回滚纪律
- 不把这一步扩成 anime 专用评分器、AniDB / Bangumi 集成或新的名称解析主线

## Done when

当前 `.ass` 主线视为 **已收口**，满足以下任一条即可：

1. `.venv/bin/python -m pytest -q tests/test_subtitle_translator.py` 全绿，且覆盖 `.srt` 不回退、`.ass` 识别、`.ass` 回写和异常分支；
2. `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k subtitle` 全绿，确认导入后字幕翻译链仍能消费新 `.ass` 出口；
3. `docs/NEXT_STEP.md` / `docs/STATUS.md` / `README.md` / `AGENTS.md` 一致表达“当前主线是 `.ass` 字幕最小支持”，且不把范围写大到 `.ssa` / 嵌入字幕 / OCR。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `AGENTS.md` / `docs/SERIES_ANIME_NAMING_PLAN.md` / `docs/SERIES_ANIME_NAMING_LOG.md` / 其余完成台账继续保持分层一致，不重新写回长台账

## After this step

1. 重新评估 PT live seeding 真相、Jellyfin / Plex 真实联调、BT 批量任务三者里哪一个更值钱
2. 把该事项提升成新的 promoted 主线，并在本文件补齐 `Current goal / Only do / Done when`
