# Luminarr (v64)

Luminarr 是一个面向 **2–4 人自托管影视场景** 的垂直自动化 Harness。

它当前同时服务 Telegram / personal WeChat / Feishu / WeCom 四个私聊入口，但不做通用 AI 助手、通用多渠道平台或通用 plugin / skill / MCP 平台。

## 0. 从哪里开始

如果你是第一次看这个仓库，先读：

1. `docs/INDEX.md`
2. `docs/GETTING_STARTED.md`
3. `docs/ARCHITECTURE.md`

如果你想直接跑：

1. 复制 `.env.example` 为 `.env`
2. 按 `docs/GETTING_STARTED.md` 填配置
3. 用 `make run` / `docker compose up -d`，或 `set -a && . ./.env && set +a && .venv/bin/python -m app.main` 启动

当前最小启动真相：

- `TELEGRAM_BOT_TOKEN`、`PROWLARR_BASE_URL`、`PROWLARR_API_KEY`、`TRANSMISSION_BASE_URL` 是当前启动硬必填
- 如果 WSL 机器不能直连公网，可额外填写 `OUTBOUND_PROXY_URL` 给 Telegram / TMDB / Fanart / BT 外站 / 字幕翻译出站请求复用；Transmission / Emby / Prowlarr 这类本地地址仍直连
- `TMDB_API_KEY` 当前不是启动硬必填；不填时只会关闭 TMDB 相关增强能力
- `DOWNLOADER_INSTANCES` 当前只是多实例路由补充配置，不能替代 `TRANSMISSION_BASE_URL`
- `make run` 现在会先检查 `ENV_FILE` 指向的环境文件是否存在；缺失时会打印红色中文 `[环境文件缺失]` 和 `[处理建议]`
- 如果环境文件不在仓库根目录，可用 `ENV_FILE=/绝对路径 make run` 指向已有配置

## 1. 它在解决什么问题

一个人用手机发一句话，系统完成搜索、审批、下载、入库、刷新，让内容出现在私人媒体库里。

## 2. 当前系统长什么样

- 四个渠道当前都是正式入口：
  - Telegram
  - personal WeChat
  - Feishu
  - WeCom
- 四个渠道共用同一套：
  - `shared private-chat text runtime`
  - workflow / approval / `jobs` / SQLite 真相
- 渠道层只负责：
  - 验签、解密、轮询或回包
  - 外部会话标识投影到现有 `chat_id / user_id`
  - 调用 shared runtime
  - 把文本、图片/文件或最小信息卡片发回原渠道
- 当前固定主线：
  - TMDB
  - Prowlarr（当前主来源）+ 最小 BT WebSource（仅 BT 使用）
  - Transmission + qBittorrent
  - Emby
  - SQLite
  - Docker Compose
  - 单实例 / 单进程 / 单机
  - movie-first

## 3. 当前已经落地

- 控制层：
  - Telegram runtime + 最小图片/文件发送 + 搜索结果/下载审批/导入审批文本 polish
  - personal WeChat 二维码登录入口 + PNG 二维码回传 + 单账号私聊文本轮询
  - Feishu 私聊文本 webhook + 文本回消息 + 事件验签
  - Feishu 可选 `long_connection` 入站模式
  - WeCom callback URL 校验 + 验签解密入站 + 加密被动文本回包
  - `telegram_updates` 去重、`jobs` 执行所有权、approval timeout、confirm wake rebuild
- 媒体主链：
  - `search -> select -> downloader approval -> confirm -> dispatch -> status`
  - `import approval -> confirm -> hardlink import`
  - cross-filesystem copy-fallback approval
  - completion-monitor + post-download auto import + 最小后台 auto-import tick
  - filename normalization
  - metadata scraping（TMDB + Fanart.tv）
  - subtitle auto-translation（当前仅 `.srt`）
  - Emby refresh
- cleanup 最小闭环：
  - `cleanup inspect`
  - `cleanup`
  - discoverability
  - rejection guidance
  - success follow-up
  - failure observability
  - chat-scoped `task_ref` 解析
- BT 主链：
  - PT / BT 分流
  - 原始磁力 processing-path inquiry
  - BT classification
  - `movie / series / anime` TMDB association
  - `raw_bt` 目标目录选择
  - BT shared source adapter（`Prowlarr + WebSource`）
  - pure BT single-item ranking
  - BT external web-source
  - BT WebSource richer metadata extraction
  - BT-only read-only helper（`bt搜 <关键词>` / `bt search <关键词>`）
  - `btsub` 手动命令 + scheduler tick + deterministic candidate-selection
- 其他：
  - `watchlist` 手动持久化基线

## 4. 当前边界

- 四个渠道都要可用，但业务真相只维护一套；不为同一条协议做四份分叉实现。
- 当前只支持私聊文本主线；Feishu / WeCom 不做群聊、卡片、按钮回调，personal WeChat 不做多账号编排。
- personal WeChat 当前回复依赖有效 `context_token`；WeCom 仍只有 callback 被动回包，没有独立主动发消息客户端。
- 交付形态继续以私聊 bot 为主；后续体验优化优先走渠道内更美观的图片/信息卡片/字符排版，不做 Web UI。
- cleanup 只清 downloader/source 侧已导入资产，不删除库内目标、sidecar 或其他任务文件。
- cleanup 当前只对带结构化 `source_path + target_path` 的导入任务可用。
- cleanup 当前还没有 PT 做种状态 / `pt_min_seed_hours` 保护校验；cleanup 验证窗口退出前必须把这条风险确认清楚。
- 当前最稳的是 movie-first；`shared private-chat` 交付体验主线已完成，当前缺口转到最小人类可用入口（quick start / 配置模板 / 首个渠道 10 分钟跑通）。
- 字幕翻译当前仍只处理 `.srt`；`.ass` 继续保留为后续能力缺口，不阻塞当前主线切换。
- BT 路线已可用，但还没升级成共享确定性评分器。

## 5. 当前 next step

- **当前唯一主线**：最小人类可用入口继续补齐，按 `docs/QUICK_START_PLAN.md` 推进。
- **详细目标与可测量退出条件**：`docs/NEXT_STEP.md`
- **当前快照**：`docs/STATUS.md`
- **当前主线蓝图**：`docs/QUICK_START_PLAN.md`
- **当前主线交付物**：`docs/DEPLOY_CHECKLIST.md`
- **上一条主线台账**：`docs/SERIES_ANIME_NAMING_LOG.md`（`series / anime` 名称解析主线已在 2026-04-19 达到退出条件 1）
- **上一条主线台账**：`docs/APP_MAIN_SLIMMING_LOG.md`（`app/main.py` 瘦身主线已在 2026-04-19 达到退出条件 1）
- **再上一条主线台账**：`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`（shared runtime 编排层瘦身主线已在 2026-04-19 达到退出条件 2）
- **更早主线台账**：`docs/CLEANUP_SLIMMING_LOG.md`（cleanup 编排层瘦身主线已在 2026-04-19 达到退出条件 1）
- **更早主线台账**：`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`（BT 订阅编排层瘦身主线已在 2026-04-19 达到退出条件 1）
- **更早主线台账**：`docs/SEARCH_MEDIA_SLIMMING_LOG.md`（搜索编排层瘦身主线已在 2026-04-19 达到退出条件 1）
- **更早主线台账**：`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`（下载编排层瘦身主线已在 2026-04-19 达到退出条件 1）
- **更早主线台账**：`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`（导入编排层瘦身主线已在 2026-04-19 达到退出条件 1）
- **更早主线台账**：`docs/TELEGRAM_BOT_SLIMMING_LOG.md`（Telegram 渠道层瘦身主线已在 2026-04-19 达到退出条件 1）
- **更早主线台账**：`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`（下载完成轮询主线已在 2026-04-18 达到退出条件 1）
- **更早主线台账**：`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`（Feishu 私聊事件解析器去重已在 2026-04-18 达到退出条件 3）
- **更早主线台账**：`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`（Feishu 长连接私有 API 风险收口已在 2026-04-18 达到退出条件 1）
- **更早主线台账**：`docs/PERSISTENCE_CLOSURE_LOG.md`（持久化吞错收口已在 2026-04-18 冷启动审计中达到退出条件 3）
- **cleanup 完成证据**：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- **本地回归命令**：当前主线入口看 `docs/QUICK_START_PLAN.md` 和 `docs/DEPLOY_CHECKLIST.md`；刚完成的 `series / anime` 主线回归入口见 `docs/SERIES_ANIME_NAMING_LOG.md`。
- 这一步只允许收部署入口、配置模板和部署者文档，不顺手改 workflow 真相、下载器、cleanup 或其他编排层。
- 当前主线完成后，按 `docs/NEXT_STEP.md` 的 `After this step` 编号顺序推进（BT 共享确定性评分器 → 等等）。

## 6. 当前明确不做

- 通用 AI 助手
- 通用 Agent 平台
- 通用 plugin / skill / MCP 平台化
- Jellyfin / Plex 并行主线支持（当前不做，后续再补）
- Web UI / 桌面端
- Telegram / 微信群聊主线
- Redis / MQ / PostgreSQL
- 多机分布式部署

## 7. 工程立场

- parser-first，LLM-fallback
- 模型不负责幂等、审批校验、执行结果真相、lease/version
- 背景恢复和 scheduler tick 不依赖 LLM
- BT helper 只做只读辅助

## 8. 本地集成测试栈

涉及真实 downloader / import / refresh 联调时，使用 WSL Docker 本地测试栈：

- Transmission：`http://127.0.0.1:19091`
- BT Transmission：`http://127.0.0.1:19092`
- Emby：`http://127.0.0.1:18096`

详细路径、健康检查、配置占位见 `docs/TEST_ENV.md`。

## 9. 文档入口

开始任何新任务前，先读：

1. `docs/INDEX.md`
2. `docs/GETTING_STARTED.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DECISIONS.md`
5. `docs/NEXT_STEP.md`
6. `docs/STATUS.md`
7. `docs/PERSISTENCE_CLOSURE_LOG.md`
8. `AGENTS.md`
9. `docs/HISTORY.md`（只看背景，不看当前执行真相）

常用入口：

- `docs/INDEX.md`：文档地图
- `docs/GETTING_STARTED.md`：从零到跑通
- `docs/ARCHITECTURE.md`：系统怎么工作
- `docs/STATUS.md`：当前短快照
- `docs/QUICK_START_PLAN.md`：当前主线蓝图
- `docs/DEPLOY_CHECKLIST.md`：当前主线交付物
- `docs/SHARED_DELIVERY_UX_PLAN.md`：刚完成主线蓝图
- `docs/SHARED_DELIVERY_UX_LOG.md`：刚完成主线详细闭环
- `docs/SERIES_ANIME_NAMING_LOG.md`：刚完成的上一条主线详细闭环
- `docs/APP_MAIN_SLIMMING_LOG.md`：上一条主线详细闭环
- `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`：再上一条主线详细闭环
- `docs/CLEANUP_SLIMMING_LOG.md`：更早主线详细闭环
- `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`：更早主线详细闭环
- `docs/SEARCH_MEDIA_SLIMMING_LOG.md`：更早主线详细闭环
- `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`：更早主线详细闭环
- `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`：更早主线详细闭环
- `docs/TELEGRAM_BOT_SLIMMING_LOG.md`：更早主线详细闭环
- `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`：更早主线详细闭环
- `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`：更早主线详细闭环
- `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`：更早主线详细闭环
- `docs/PERSISTENCE_CLOSURE_LOG.md`：更早完成主线详细闭环
- `.env.example`：配置模板
- `Makefile`：常用命令入口
- `Dockerfile` / `docker-compose.yml`：最小容器启动入口
