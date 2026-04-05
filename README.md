# Luminarr (v58)

Luminarr 是一个面向 **2–4 人自托管影视场景** 的垂直自动化 Harness。

它当前同时服务 Telegram / personal WeChat / Feishu / WeCom 四个私聊入口，但不做通用 AI 助手、通用多渠道平台或通用 plugin / skill / MCP 平台。

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
  - 把文本或最小媒资发回原渠道
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
- cleanup 只清 downloader/source 侧已导入资产，不删除库内目标、sidecar 或其他任务文件。
- cleanup 当前只对带结构化 `source_path + target_path` 的导入任务可用。
- 当前最稳的是 movie-first；`series / anime` 独立名称解析还没实现。
- BT 路线已可用，但还没升级成共享确定性评分器。

## 5. 当前 next step

- 当前不再把 cleanup 当成无限观察项，而是执行一个有退出条件的四渠道验证窗口。
- 退出条件：
  - 完成 7 天真实使用验证
  - Telegram / personal WeChat / Feishu / WeCom 四个渠道各至少完成 1 次真实私聊 smoke
  - cleanup discoverability / inspect / execution / rejection guidance / success follow-up / failure observability 没有协议回退
- 这一步只允许修 shared runtime 回归、渠道胶水回归和显式日志缺口，不新增自动 cleanup、批量 cleanup 或删种。
- cleanup 验证窗口结束后，下一步按顺序推进：
  1. `series / anime` 独立名称解析最小实现
  2. BT 共享确定性评分器

## 6. 当前明确不做

- 通用 AI 助手
- 通用 Agent 平台
- 通用 plugin / skill / MCP 平台化
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

1. `docs/DECISIONS.md`
2. `docs/NEXT_STEP.md`
3. `docs/STATUS.md`
4. `README.md`
5. `AGENTS.md`
6. `docs/HISTORY.md`（只看背景，不看当前执行真相）
