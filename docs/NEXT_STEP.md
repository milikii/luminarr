# Next step (v220)

## Current goal

- 当前进行中的 promoted 主线是 **Jellyfin / Plex 真实联调重评估**。2026-04-19 冷启动审计已确认 BT 批量任务显式批量确认主线满足 `Done when` 第 1 条并转入完成态；本轮开始按上一条主线的 `After this step` 第 1 项重开新主线。
- 当前现实是：`app/main.py` 已能按配置选择 Emby / Jellyfin / Plex refresh client，但仓库正式本地真实 refresh 测试栈仍只有 Emby；如果 `MEDIA_SERVER_PROVIDER=jellyfin / plex` 且缺少对应地址或 token，当前装配还会静默返回 `None`，缺少显式中文提示与 focused tests。
- 2026-04-19 刚完成的主线是 **BT 批量任务显式批量确认**：`bt批量 / bt batch` 的只读批量预览与 `bt批量确认 / bt batch confirm` 的显式批量确认都已落地，focused tests 为 `11 passed, 312 deselected`。
- 再上一条已完成主线是 **PT live seeding 真相接入 cleanup 阻断**。冷启动审计已确认它满足文档出口；详细蓝图继续看 `docs/PT_LIVE_SEEDING_PLAN.md`。
- 更早一条已完成主线是 **`.ass` 字幕最小支持**。2026-04-19 已补齐 `.srt` + 最小 `.ass` 字幕翻译路径，focused tests 为 `10 passed`，导入后字幕 focused tests 为 `2 passed, 140 deselected`；详细闭环继续看 `docs/SERIES_ANIME_NAMING_LOG.md` 2.3。
- 更早完成主线：cleanup PT 最小保护窗口、Jellyfin / Plex provider 选择、最小人类可用入口补齐、shared private-chat 交付体验收口、`series / anime` 独立名称解析最小实现、`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身、下载完成轮询、Feishu 风险收口、持久化吞错收口都保持完成态，不回退。
- 当前主线蓝图统一写在 `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md`。

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线蓝图：`docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md`
- 刚完成主线蓝图：`docs/BT_BATCH_PLAN.md`
- 再上一条主线蓝图：`docs/PT_LIVE_SEEDING_PLAN.md`
- 刚完成主线蓝图 / 台账：`docs/SERIES_ANIME_NAMING_PLAN.md`、`docs/SERIES_ANIME_NAMING_LOG.md`
- 刚完成主线蓝图 / 台账：`docs/BT_SCORING_PLAN.md`、`docs/BT_SCORING_LOG.md`
- 刚完成主线蓝图 / 交付物：`docs/QUICK_START_PLAN.md`、`docs/DEPLOY_CHECKLIST.md`
- 更早主线台账：`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 当前优先交付：
  - 补 `MEDIA_SERVER_PROVIDER=jellyfin / plex` 但缺少必填配置时的显式中文日志与 focused tests
  - 复用现有 WSL Docker `Transmission + Emby` 测试栈，确认真实 refresh baseline 的最小落点
  - 在做 readiness 评估时，不把“当前只有 Emby 正式测试栈”伪装成“Jellyfin / Plex 已有固定真机入口”
- 保持 Telegram / personal WeChat / Feishu / WeCom 四渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持 cleanup / search / approval / import / status / watchlist / btsub 既有协议和 guardrail 不回退
- 文档继续分层：`STATUS.md` 只保留当前快照；当前主线细节写在 `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md`；已完成的 BT 批量蓝图继续留在 `docs/BT_BATCH_PLAN.md`

## Do not do

- 不引入 DSL / 通用规则语言 / LLM 判分
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不新增 Jellyfin / Plex Docker 测试栈，不把这一步扩成环境编排大改
- 不把这一步改成自动 `confirm` / 自动 dispatch
- 不改 cleanup 删除范围、媒体库导入成功真相或字幕主线出口
- 不把这一步扩成 Jellyfin / Plex 全量能力对齐、自动探测或新的下载器平台化主线

## Done when

当前 Jellyfin / Plex 真实联调重评估主线视为 **已收口**，满足以下任一条即可：

1. `MEDIA_SERVER_PROVIDER=jellyfin / plex` 且缺少必填配置时，启动装配会打印显式中文日志和 `[处理建议]`，且 `.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py tests/test_config.py -k "media_server or refresh"` 全绿；
2. `docs/TEST_ENV.md` / `docs/NEXT_STEP.md` / `docs/STATUS.md` / `README.md` / `AGENTS.md` 一致表达“当前正式本地真实 refresh 栈只有 Emby；Jellyfin / Plex 先做 readiness 评估”；
3. 使用现有 Emby 测试栈完成一条真实 refresh baseline 记录，并能明确回答“下一条 promoted 主线是否值得切到 Jellyfin 或 Plex 单 provider 联调”。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `AGENTS.md` / `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md` / `docs/BT_BATCH_PLAN.md` / `docs/PT_LIVE_SEEDING_PLAN.md` / 其余完成台账继续保持分层一致，不重新写回长台账

## After this step

1. 如果 readiness 评估表明值得继续，选 Jellyfin 或 Plex 其中一个切成单 provider 真实联调主线
2. 如果不做 Jellyfin / Plex，再回到 BT 更大范围的用户页 / 编号范围页能力
