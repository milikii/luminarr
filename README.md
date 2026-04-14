# Luminarr (v62)

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
  - personal WeChat 二维码登录入口 + 单账号私聊文本轮询
  - Feishu 私聊文本 webhook + 文本回消息 + 事件验签
  - WeCom callback URL 校验 + 验签解密入站 + 加密被动文本回包
  - `telegram_updates` 去重、`jobs` 执行所有权、approval timeout、confirm wake rebuild
- 媒体主链：
  - `search -> select -> downloader approval -> confirm -> dispatch -> status`
  - `import approval -> confirm -> hardlink import`
  - cross-filesystem copy-fallback approval
  - completion-monitor + post-download auto import
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
- 当前最稳的是 movie-first；`series / anime` 独立名称解析还没实现。
- 字幕翻译当前仅处理 `.srt`；`series / anime` 落地时需同步评估 `.ass`。
- BT 路线已可用，但还没升级成共享确定性评分器。

## 5. 当前 next step

- 当前不再把 cleanup 当成无限观察项，而是执行一个有退出条件的四渠道验证窗口。
- cleanup 详细窗口台账和当前进度统一看 `docs/CLEANUP_VERIFICATION_WINDOW.md` 与 `docs/STATUS.md`，不要把窗口细节再抄回仓库入口。
- 退出条件：
  - 完成 7 天真实使用验证
  - Telegram / personal WeChat / Feishu / WeCom 四个渠道各至少完成 1 次真实私聊 smoke
  - cleanup discoverability / inspect / execution / rejection guidance / success follow-up / failure observability 没有协议回退
  - verification docs gate 持续通过
- 这一步只允许修 shared runtime 回归、渠道胶水回归和显式日志缺口，不新增自动 cleanup、批量 cleanup 或删种。
- 截至 2026-04-14，当前四渠道真实私聊 smoke 已补齐 Telegram / personal WeChat / Feishu，剩余唯一待补缺口只剩 WeCom。
- `tests/test_cleanup_cross_channel_smoke.py` 继续保障四渠道 cleanup discoverability / inspect / execution / rejection guidance / post-cleanup confirmation / mixed-case 英文 `cleanup / cleanup inspect` 输入 / chat-scoped `task_ref` -> jobs -> import correlation，且已把 `job_event` 关联查询失败、缺结构化 `source_path/target_path` 两类 identity retention，以及 `guard-rejected` rejection guidance 验证进来。
- 当前 cleanup 窗口的本地 gate 入口有十条：`make test-cleanup-smoke` 只跑四渠道 smoke gate，`make test-cleanup-service-not-ready` 单独盯 service-not-ready observability，`make test-cleanup-telegram` 跑 Telegram cleanup 入口回归，`make test-cleanup-personal-wechat` 跑 personal WeChat cleanup 入口回归，`make test-cleanup-feishu` 跑 Feishu cleanup 入口回归，`make test-cleanup-wecom` 跑 WeCom cleanup 入口回归，`make test-cleanup-feishu-webhook` 跑 Feishu webhook cleanup 入口回归，`make test-cleanup` 跑 cleanup 聚合回归，`make test-cleanup-docs-gate` 跑 cleanup verification docs gate，`make test-cleanup-window` 会连续跑 smoke gate、cleanup 聚合回归和 verification docs gate；它们都不能替代四渠道真实私聊 smoke 证据。
- 如果当前只想确认 WeCom 本地 callback 已就绪，先确保 `app.main` 正在运行，再跑 `curl -si http://127.0.0.1:18889/wecom/callback`；这条地址来自当前本地已验证 `.env`，不是 `.env.example` 的默认端口/路径。当前无校验参数时返回 `400 missing echostr` 属于本地入口可达，不等于 WeCom 真实私聊 smoke 已完成；如果直接得到 `connection refused`，先检查应用有没有起起来。
- 如果当前环境没有 `make`，就直接用底层一行命令跑：四渠道 smoke gate 用 `.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`，cleanup service-not-ready gate 用 `.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py -k service_not_ready`，Telegram cleanup 回归用 `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k cleanup`，cleanup 聚合回归用 `.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`，cleanup docs gate 用 `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`，其余单渠道与窗口组合 gate 继续看 `docs/GETTING_STARTED.md` 里的等价一行命令。
- cleanup 验证窗口结束后，下一步按顺序推进：
  1. 独立后台下载完成轮询
  2. `series / anime` 独立名称解析最小实现（结构化解析 + 小型识别词/替换配置）
  3. `.ass` 字幕支持评估与最小实现
  4. shared private-chat 交付体验收口（图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI）
  5. 最小人类可用入口（quick start / 配置模板 / 首个渠道 10 分钟跑通）
  6. BT 共享确定性评分器
  7. Jellyfin / Plex 支持（后续）
  8. plugin 体系后置评估

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
7. `AGENTS.md`
8. `docs/HISTORY.md`（只看背景，不看当前执行真相）

常用入口：

- `docs/INDEX.md`：文档地图
- `docs/GETTING_STARTED.md`：从零到跑通
- `docs/ARCHITECTURE.md`：系统怎么工作
- `.env.example`：配置模板
- `Makefile`：常用命令入口
- `Dockerfile` / `docker-compose.yml`：最小容器启动入口
