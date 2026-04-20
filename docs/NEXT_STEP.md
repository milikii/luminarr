# Next step (v238)

## Current goal

- 当前进行中的 promoted 主线切到 **BT 批量确认多条连续真实 dispatch smoke 值得性评估**。上一条 **BT 批量确认真实 dispatch smoke** 已在 2026-04-20 按 `Done when` 第 2 条收口：一次性临时脚本先定位到本地 `.env` 缺少 `DOWNLOADER_INSTANCES / BT_DOWNLOADER`，再按 `docs/TEST_ENV.md` 临时覆盖 `tr-bt -> http://127.0.0.1:19092` 后，继续定位到 `request_url=http://127.0.0.1:19092/transmission/rpc` 不可达；同批次 `Emby(http://127.0.0.1:18096)` 仍可返回 `ServerName`。
- BT allowlist 页面 proof、**BT 用户页 / 编号范围页能力**、单条 BT 真实 dispatch、BT 批量确认真实 dispatch 都已收口。当前需要决定的，不是再补一条同口径单条 smoke，而是评估“多条连续真实 dispatch”是否还有新信息；若只是重复取证，就不要继续拆。
- 当前继续留在 BT 而不是回 Plex：Plex 这条线已经回答了“当前不值得继续追实例”；当前更小也更有用户价值的下一步，是判断 BT 批量确认多条连续真实 dispatch 是否值得继续投入。
- 当前主线优先复用现有批量预览 / 聊天缓存 / `bt批量确认`，不回到 direct `magnet:?` 单条真实 smoke，也不重做已收口页面。
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
  - 保持现有 BT 页面 URL 预览、聊天缓存、`bt批量确认` 复用和 `p=<页码>` 语法不回退
  - 当前只允许评估 **BT 批量确认多条连续真实 dispatch smoke** 是否还有新增用户价值；若只剩重复取证，就不要继续留在同一能力族里拆更小 proof
  - 保持 BT 角色绑定、approval、`jobs`、download_monitor 和显式中文日志边界不回退
  - 遇到未声明站点、未声明页面类型或非法范围时，显式中文 fail-closed，不静默降级成关键词搜索
  - 保持“repo 内固定 Docker refresh 栈仍只有 Emby；Plex 暂不继续追实例”这条边界，不顺手回到 refresh 大主线
- 保持 Telegram / personal WeChat / Feishu / WeCom 四渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持 cleanup / search / approval / import / status / watchlist / btsub 既有协议和 guardrail 不回退
- 文档继续分层：`STATUS.md` 只保留当前快照；刚完成的 BT 批量真实 dispatch 收口细节写在 `docs/BT_BATCH_PLAN.md`；更早完成的单条 BT real dispatch 细节继续留在 `docs/BT_REAL_DISPATCH_SMOKE_PLAN.md`；刚完成的 BT 页面 proof 细节继续留在 `docs/BT_PAGE_RANGE_PLAN.md`；更早完成的 Plex 值得性重评估细节继续留在 `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md`

## Do not do

- 不引入 DSL / 通用规则语言 / LLM 判分
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不新增 Jellyfin / Plex Docker 测试栈，不把这一步拉回 refresh 环境编排
- 不把这一步改成自动 `confirm` / 自动 dispatch
- 不回到 BT allowlist 页面 URL 家族里继续拆更小 proof
- 不回到单条 direct `magnet:?` 真实 smoke 继续重复取证
- 不改 cleanup 删除范围、媒体库导入成功真相或字幕主线出口
- 不把这一步重新放大成 Jellyfin + Plex 双线并行、全量能力对齐、自动探测或新的下载器平台化主线
- 不接未知站点、动态站点、CAPTCHA、登录态页面或通用抓站平台

## Done when

当前 **BT 批量确认多条连续真实 dispatch smoke 值得性评估** 主线视为 **已收口**，满足以下任一条即可：

1. 明确判断“多条连续真实 dispatch”仍有新的用户可感知信息，并把更小的下一条闭环写清楚；
2. 明确判断这一步只剩重复取证，没有新增副作用真相、协议能力或结构降本，于是直接停止，不再继续拆更小 proof；
3. 本轮代码变更 `< 20` 行且只是对同一个 batch confirm dispatch / route helper 补一条诊断日志分支，触发 `AGENTS.md §11` 停机规则。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `AGENTS.md` / `docs/BT_REAL_DISPATCH_SMOKE_PLAN.md` / `docs/BT_PAGE_RANGE_PLAN.md` / `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md` / `docs/JELLYFIN_REAL_VERIFICATION_PLAN.md` / `docs/BT_BATCH_PLAN.md` / `docs/PT_LIVE_SEEDING_PLAN.md` / 其余完成台账继续保持分层一致，不重新写回长台账

## After this step

1. 如果这条主线也收口，再回看当前 BT 方向是否还剩新的副作用真相或新的用户可感知协议能力；若没有，就不要继续留在同一能力族里拆 proof
2. 如果后续单独拿到 Plex 实例，再开一条最小 Plex real smoke 主线
