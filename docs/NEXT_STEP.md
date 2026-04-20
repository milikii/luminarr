# Next step (v243)

## Current goal

- 刚完成的 **共享状态 follow-up helper 结构降本** 已在 2026-04-20 冷启动审计中确认收口：`GetDownloadStatusService.get_status_text()` 已只保留状态查询和回复组装，实际共享 follow-up 已委托给 `StatusFollowUpRecorder.record()`；focused tests 继续覆盖状态查询、状态 follow-up、后台 completion polling 与自动导入最小回归，文档也已按分层收口到 `docs/PERSISTENCE_CLOSURE_LOG.md`。
- 刚完成的 **`download_monitor_repo.py` / `job_event` 共享状态 helper 值得性评估** 保持完成态：当前固定调用方仍是 `StatusFollowUpRecorder.record()`、`PostDownloadAutoImportService.run_for_record()`、`telegram_bot._poll_pending_download_completion_once()`；三处继续围绕 `download_monitor` / `job_event` 真相推进“状态观察落盘 -> 完成事件查询/追加 -> 自动导入消费”。
- 刚完成的 **`post_download_auto_import.py` 自动导入编排层瘦身 / 模块化** 继续保持完成态：`run_once()` 只保留候选扫描与计数编排，候选读取 / 逐条任务推进 helper 已独立到 `app/services/auto_import_batch.py`，focused tests `8 passed, 34 deselected`，扩展自动导入 / 状态 follow-up focused tests `21 passed, 21 deselected`。
- 上一条 **`get_download_status.py` 状态编排层瘦身 / 模块化** 继续保持完成态：状态展示 helper 已独立到 `app/services/status_delivery.py`，观察落盘 / 完成事件 / 自动导入 follow-up 已独立到 `app/services/status_follow_up.py`，展示侧 focused tests `4 passed, 38 deselected`、观察 / 自动导入 focused tests `21 passed, 21 deselected`、跨渠道 status 回归 `6 passed, 372 deselected`。
- 当前进行中的 promoted 主线切到 **Telegram 后台 completion polling 直连共享 follow-up helper 收口**。
- 当前更小也更有价值的闭环，是只把 `telegram_bot._poll_pending_download_completion_once()` 从 `get_status_text()` 的间接副作用里拆出来，改成直接复用共享 follow-up helper；这一步仍只做最小 repo / orchestration 降本，不顺手改协议、不放大成新的 service 大重构。
- 当前主线入口继续看 `docs/NEXT_STEP.md` 与 `docs/STATUS.md`；刚完成的自动导入瘦身台账继续看 `docs/POST_DOWNLOAD_AUTO_IMPORT_SLIMMING_LOG.md`；刚完成的状态 service 瘦身继续看 `docs/GET_DOWNLOAD_STATUS_SLIMMING_LOG.md`；BT 批量确认、单条真实 dispatch、页面 proof 和 Plex 值得性重评估都保持完成态，不回退成进行中。
- 更早完成的 **BT 用户页 / 编号范围页能力** 继续保持完成态，不回退。
- 2026-04-19 刚完成的主线是 **Plex 真实 refresh smoke 值得性重评估**：当前主机没有可达 Plex 实例，这一批次统一收口为“先回到 BT 更大范围能力”。
- 再上一条完成主线是 **Jellyfin / Plex 真实联调重评估**：provider 缺配置时的静默关闭 refresh 已收口，focused tests 为 `10 passed, 46 deselected`。
- 更早一条完成主线是 **Jellyfin 单 provider 真实 refresh smoke**：真实失败探针已把失败点定位到 `provider + target + request_url`。
- 更早一条刚完成主线是 **BT 批量任务显式批量确认**：`bt批量 / bt batch` 的只读批量预览与 `bt批量确认 / bt batch confirm` 的显式批量确认都已落地，focused tests 为 `11 passed, 312 deselected`。
- 再上一条已完成主线是 **PT live seeding 真相接入 cleanup 阻断**。冷启动审计已确认它满足文档出口；详细蓝图继续看 `docs/PT_LIVE_SEEDING_PLAN.md`。
- 更早一条已完成主线是 **`.ass` 字幕最小支持**。2026-04-19 已补齐 `.srt` + 最小 `.ass` 字幕翻译路径，focused tests 为 `10 passed`，导入后字幕 focused tests 为 `2 passed, 140 deselected`；详细闭环继续看 `docs/SERIES_ANIME_NAMING_LOG.md` 2.3。
- 更早完成主线：cleanup PT 最小保护窗口、Jellyfin / Plex provider 选择、最小人类可用入口补齐、shared private-chat 交付体验收口、`series / anime` 独立名称解析最小实现、`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身、下载完成轮询、Feishu 风险收口、持久化吞错收口都保持完成态，不回退。
- 刚完成主线蓝图继续看 `docs/BT_BATCH_PLAN.md`；更早完成的单条真实 dispatch 证据继续看 `docs/BT_REAL_DISPATCH_SMOKE_PLAN.md`。

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线台账：`docs/POST_DOWNLOAD_AUTO_IMPORT_SLIMMING_LOG.md`
- 刚完成主线台账：`docs/GET_DOWNLOAD_STATUS_SLIMMING_LOG.md`
- 刚完成主线蓝图：`docs/BT_BATCH_PLAN.md`
- 更早完成主线蓝图：`docs/BT_REAL_DISPATCH_SMOKE_PLAN.md`
- 更早完成主线蓝图：`docs/BT_PAGE_RANGE_PLAN.md`
- 更早完成主线蓝图：`docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md`
- 再上一条主线蓝图：`docs/JELLYFIN_REAL_VERIFICATION_PLAN.md`
- 更早主线蓝图：`docs/PT_LIVE_SEEDING_PLAN.md`
- 刚完成主线蓝图 / 台账：`docs/SERIES_ANIME_NAMING_PLAN.md`、`docs/SERIES_ANIME_NAMING_LOG.md`
- 刚完成主线蓝图 / 台账：`docs/BT_SCORING_PLAN.md`、`docs/BT_SCORING_LOG.md`
- 刚完成主线蓝图 / 交付物：`docs/QUICK_START_PLAN.md`、`docs/DEPLOY_CHECKLIST.md`
- 更早主线台账：`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 当前优先交付：
  - 当前只做 Telegram 后台 completion polling 直连共享 helper 的最小结构降本，不直接开更大重构
  - 优先让后台轮询直接复用共享的状态观察 / 完成事件 / 自动导入 follow-up helper，不再让渠道层依赖 `get_status_text()` 的间接副作用
  - 保持 `download_monitor`、`job_event`、`AutoImportStateUnavailableError`、显式中文日志和现有状态 follow-up 语义不回退
  - 保持 `get_download_status.py`、`post_download_auto_import.py`、`telegram_bot.py` 现有对外协议不变
  - 保持“repo 内固定 Docker refresh 栈仍只有 Emby；Plex 暂不继续追实例”这条边界，不顺手回到 refresh 大主线
- 保持 Telegram / personal WeChat / Feishu / WeCom 四渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持 cleanup / search / approval / import / status / watchlist / btsub 既有协议和 guardrail 不回退
- 文档继续分层：`STATUS.md` 只保留当前快照；当前瘦身主线细节写在 `docs/POST_DOWNLOAD_AUTO_IMPORT_SLIMMING_LOG.md`；刚完成的状态 service 瘦身细节继续留在 `docs/GET_DOWNLOAD_STATUS_SLIMMING_LOG.md`；刚完成的 BT 批量真实 dispatch 收口细节继续留在 `docs/BT_BATCH_PLAN.md`；更早完成的单条 BT real dispatch 细节继续留在 `docs/BT_REAL_DISPATCH_SMOKE_PLAN.md`；刚完成的 BT 页面 proof 细节继续留在 `docs/BT_PAGE_RANGE_PLAN.md`；更早完成的 Plex 值得性重评估细节继续留在 `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md`

## Do not do

- 不引入 DSL / 通用规则语言 / LLM 判分
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不新增自动导入规则、不改低质量过滤语义、不改 `AutoImportRunResult` 字段含义
- 不在这一步直接把 `download_monitor_repo.py`、`job_event`、`get_download_status.py` 或渠道层合并进更大的重构
- 不新增 Jellyfin / Plex Docker 测试栈，不把这一步拉回 refresh 环境编排
- 不把这一步改成自动 `confirm` / 自动 dispatch
- 不回到 BT allowlist 页面 URL 家族、单条 direct `magnet:?` 或批量连续真实 dispatch 继续重复取证
- 不改 cleanup 删除范围、媒体库导入成功真相或字幕主线出口
- 不把这一步重新放大成 Jellyfin + Plex 双线并行、全量能力对齐、自动探测或新的下载器平台化主线
- 不接未知站点、动态站点、CAPTCHA、登录态页面或通用抓站平台

## Done when

当前 **Telegram 后台 completion polling 直连共享 follow-up helper 收口** 主线视为 **已收口**，满足以下任一条即可：

1. `telegram_bot._poll_pending_download_completion_once()` 不再通过 `get_status_text()` 间接触发共享副作用，而是直接复用共享 helper 推进状态观察落盘、完成事件追加和自动导入消费，并保持现有中文日志、停路语义和对外协议不变；
2. focused tests 能继续覆盖状态查询、状态 follow-up、后台 completion polling 与自动导入最小回归；
3. 文档继续保持分层一致，`STATUS.md` 只写当前快照，详细结论继续收口到 `docs/PERSISTENCE_CLOSURE_LOG.md`。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `AGENTS.md` / `docs/POST_DOWNLOAD_AUTO_IMPORT_SLIMMING_LOG.md` / `docs/GET_DOWNLOAD_STATUS_SLIMMING_LOG.md` / `docs/BT_REAL_DISPATCH_SMOKE_PLAN.md` / `docs/BT_PAGE_RANGE_PLAN.md` / `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md` / `docs/JELLYFIN_REAL_VERIFICATION_PLAN.md` / `docs/BT_BATCH_PLAN.md` / `docs/PT_LIVE_SEEDING_PLAN.md` / 其余完成台账继续保持分层一致，不重新写回长台账

## After this step

1. 如果这条 Telegram 后台 polling 直连 helper 收口完成，就继续在同一职责族里挑下一段最小 repo / orchestration 降本点
2. 如果这条 Telegram 后台 polling 直连 helper 证明不值得继续细拆，就回到同一职责族里再找一个更小、更保守的结构降本点
3. 如果后续单独拿到 Plex 实例，再开一条最小 Plex real smoke 主线
