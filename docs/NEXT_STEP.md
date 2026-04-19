# Next step (v218)

## Current goal

- 当前进行中的 promoted 主线是 **BT 批量任务最小预览**。本轮先只做 `raw_bt / pure_bt` 的确定性批量预览：解析批量查询、读取现有 BT 候选、做范围过滤并回只读预览文本，不执行下载投递。
- 2026-04-19 冷启动审计已确认：上一条 **PT live seeding 真相接入 cleanup 阻断** 主线已经满足 `Done when` 第 3 条文档出口，当前不再继续把它当进行中主线；详细蓝图继续看 `docs/PT_LIVE_SEEDING_PLAN.md`。
- 再上一条已完成主线是 **`.ass` 字幕最小支持**。2026-04-19 已补齐 `.srt` + 最小 `.ass` 字幕翻译路径，focused tests 为 `10 passed`，导入后字幕 focused tests 为 `2 passed, 140 deselected`；详细闭环继续看 `docs/SERIES_ANIME_NAMING_LOG.md` 2.3。
- 更早完成主线：cleanup PT 最小保护窗口、Jellyfin / Plex provider 选择、最小人类可用入口补齐、shared private-chat 交付体验收口、`series / anime` 独立名称解析最小实现、`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身、下载完成轮询、Feishu 风险收口、持久化吞错收口都保持完成态，不回退。
- 当前主线蓝图统一写在 `docs/BT_BATCH_PLAN.md`。

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线蓝图：`docs/BT_BATCH_PLAN.md`
- 刚完成主线蓝图：`docs/PT_LIVE_SEEDING_PLAN.md`
- 刚完成主线蓝图 / 台账：`docs/SERIES_ANIME_NAMING_PLAN.md`、`docs/SERIES_ANIME_NAMING_LOG.md`
- 刚完成主线蓝图 / 台账：`docs/BT_SCORING_PLAN.md`、`docs/BT_SCORING_LOG.md`
- 刚完成主线蓝图 / 交付物：`docs/QUICK_START_PLAN.md`、`docs/DEPLOY_CHECKLIST.md`
- 更早主线台账：`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 当前优先交付：
  - 给 BT 支线补一个确定性批量预览入口
  - 先支持关键词 + 编号范围的最小批量请求
  - 继续只回预览文本，不创建批量 approval，不 dispatch 下载器
- 保持 Telegram / personal WeChat / Feishu / WeCom 四渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持 cleanup / search / approval / import / status / watchlist / btsub 既有协议和 guardrail 不回退
- 文档继续分层：`STATUS.md` 只保留当前快照；BT 批量任务蓝图细节继续写在 `docs/BT_BATCH_PLAN.md`，不把长台账回灌到 `STATUS.md`

## Do not do

- 不引入 DSL / 通用规则语言 / LLM 判分
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不把这一步扩成批量 approval / 批量 `confirm` / 自动 dispatch
- 不改 cleanup 删除范围、媒体库导入成功真相或字幕主线出口
- 不把这一步扩成 Jellyfin / Plex 真实联调或新的下载器平台化主线

## Done when

当前 BT 批量任务最小预览主线视为 **已收口**，满足以下任一条即可：

1. `bt批量` / `bt batch` 已能走确定性批量预览，且 `.venv/bin/python -m pytest -q tests/test_pure_bt.py tests/test_search_media.py tests/test_telegram_bot.py -k "bt_batch or bt_read_only_helper"` 全绿；
2. 批量请求的范围非法、越界、无结果和搜索异常都能回显式中文文本，且仍保持只读；
3. `docs/NEXT_STEP.md` / `docs/STATUS.md` / `README.md` / `AGENTS.md` 一致表达“当前主线是 BT 批量任务最小预览”，且不把范围写大到批量 dispatch 或 Jellyfin / Plex 真实联调。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `AGENTS.md` / `docs/BT_BATCH_PLAN.md` / `docs/PT_LIVE_SEEDING_PLAN.md` / 其余完成台账继续保持分层一致，不重新写回长台账

## After this step

1. 在 BT 主线里补“显式批量确认”，继续复用既有 approval -> confirm -> jobs 真相边界
2. BT 批量任务最小闭环完成后，再重新评估 Jellyfin / Plex 真实联调
