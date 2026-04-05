# Luminarr (v45)

Luminarr 是一个面向 **2–4 人自托管影视场景** 的垂直自动化 Harness。

它当前不是通用 Agent 平台，也不是通用 skill 平台。它的目标很窄：让 Telegram / Feishu / WeCom 私聊里的影视下载和入库链路稳定跑通。

---

## 1. 当前主线是什么

当前固定主线：

- Telegram + Feishu + WeCom（当前为最小私聊文本基线）
- TMDB
- Prowlarr（当前主来源）+ 最小 BT WebSource（仅 BT 使用）
- Transmission + qBittorrent
- Emby
- SQLite
- Docker Compose
- 单实例 / 单进程 / 单机
- movie-first

---

## 2. 当前已经做到哪

当前已落地主链：

**搜索 -> 选择 -> 下载审批 -> 投递下载 -> 查询状态 / 完成观察 -> 导入审批 -> 硬链接入库 -> 规范化命名 -> metadata scraping -> subtitle auto-translation -> Emby refresh**

已经落地的关键能力：

- 控制层：
  - Telegram media sending baseline（最小图片/文件发送）
  - personal WeChat login ingress baseline（Telegram 私聊发送 `微信登录` 即可触发 `wechat-clawbot` 二维码登录，并回传 SVG 二维码文件；扫码成功后会保存凭据并回发最小结果文本）
  - shared private-chat text runtime baseline
  - Feishu private-chat identity projection + text event adapter baseline
  - Feishu private-chat adapter baseline（最小 webhook 请求入口 + 文本回消息）
  - Feishu webhook event-signature verification baseline
  - WeCom private-chat decrypted-text adapter kernel baseline
  - WeCom callback envelope + text reply baseline（URL 校验 + 解密后 XML 入站 + 加密被动文本回包）
  - `telegram_updates` 去重
  - `jobs` 执行所有权
  - approval / replay guard / timeout
  - confirm wake rebuild
  - frustration/reset short-circuit
  - callback routing
  - clarification restart-durable truth
  - read-only concurrency-safe execution policy

- 媒体主链：
  - TMDB-first 搜索
  - candidate mapping persistence
  - downloader approval / import approval
  - completion-monitor
  - post-download auto import（仍保留 `confirm`）
  - cross-filesystem copy fallback approval
  - filename normalization
  - metadata scraping（TMDB + Fanart.tv）
  - subtitle auto-translation（当前仅 `.srt`）
  - Emby refresh

- BT 主链：
  - PT / BT 分流
  - 原始磁力 processing-path inquiry
  - BT classification
  - BT TMDB association
  - `raw_bt` 目标目录选择
  - pure BT 单片优选
  - BT shared source adapter（`Prowlarr + WebSource`）
  - BT external web-source baseline（当前最小静态 HTML + 直接 magnet / torrent link）
  - BT WebSource richer metadata extraction baseline（当前内建 `nyaa` 静态 HTML 已补 `size + seeders`）
  - BT-only read-only helper baseline（`bt搜 <关键词>` / `bt search <关键词>` 走共享 BT 来源适配，只返回文本候选和调试参考）
  - downloader role binding
  - BT dispatch / transfer execution
  - qBittorrent 最小协议执行
  - `btsub` 手动基线
  - `btsub` scheduler-tick 基线
  - `btsub` deterministic candidate-selection 基线

- 其他业务面：
  - `watchlist` 手动持久化基线
  - `watchlist` 的 `movie / series / anime` 分类真相

---

## 3. 当前最近一步

当前刚落地：

- **personal WeChat login ingress baseline**

这一步已完成：

- Telegram 私聊发送 `微信登录` 后，Luminarr 当前进程会调用 `wechat-clawbot` 发起二维码登录
- 当前把触发该命令的 Telegram 私聊视为二维码回传目标，并复用现有 Telegram 媒资发送回传 SVG 二维码文件
- 扫码确认成功后，会把最小结果文本回发到同一 Telegram 私聊，并把凭据保存到 `wechat-clawbot` 状态目录
- personal WeChat 登录启动、二维码生成、二维码回传、等待登录、结果通知失败时，都会打印显式中文彩色日志和处理建议
- 不改现有 workflow / service / approval / jobs / lease / SQLite 真相边界
- Telegram / Feishu / WeCom 现有搜索、BT 直达入口继续复用同一条主链

当前 next step：

- personal WeChat private-chat text baseline（在已落地二维码登录和凭据保存之上，只补最小私聊文本收发）

当前 personal WeChat 凭据默认跟随 `wechat-clawbot` 状态目录规则落盘：优先 `OPENCLAW_STATE_DIR`，其次 `CLAWDBOT_STATE_DIR`，否则落到 `~/.openclaw`。

启用当前 Feishu 最小基线时，需要补充 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_ENCRYPT_KEY`，并可按需覆盖 `FEISHU_BASE_URL`、`FEISHU_WEBHOOK_HOST`、`FEISHU_WEBHOOK_PORT`、`FEISHU_WEBHOOK_PATH`。

启用当前 WeCom 最小基线时，需要补充 `WECOM_TOKEN`、`WECOM_ENCODING_AES_KEY`、`WECOM_RECEIVE_ID`，并可按需覆盖 `WECOM_WEBHOOK_HOST`、`WECOM_WEBHOOK_PORT`、`WECOM_WEBHOOK_PATH`。

---

## 4. 后续路线

当前已明确的后续顺序：

1. personal WeChat private-chat text baseline
2. Telegram richer card/UI polish
3. downloader/library asset correlation and cleanup

补充说明：

- BT external web-source 当前已经先通过项目内共享 BT 来源适配层进入 BT 支线，没有污染 PT 主链。
- BT-only read-only helper 当前只提供最小文本型只读探索，不写 workflow truth、不得 dispatch 下载器、不得触发 import / refresh。
- 当前内建 `nyaa` 规则已能抽出 `size + seeders`，但 richer 字段覆盖和链接校验仍然很薄。
- Feishu 当前已补最小签名校验，但仍只做私聊文本 webhook + 文本回消息，不做群聊、图片、卡片、按钮回调。
- WeCom 当前已补最小 callback URL 校验、解密入站和加密被动文本回包，但仍只做私聊文本，不做群聊、图片、卡片、按钮回调或主动发消息客户端。
- Telegram 最小图片/文件发送能力已经被 personal WeChat 登录入口复用，当前二维码回传形态为 SVG 文档文件。
- personal WeChat 最小二维码登录入口已经落地，下一刀转到 personal WeChat 最小私聊文本适配，不急着扩到群聊、图片或更重的 UI 形态。
- personal WeChat 未来默认直接复用 `wechat-clawbot` Python 包提供的 iLink 客户端能力，不把 npm ClawBot 插件作为当前项目的主实现形态。
- personal WeChat 凭据当前仍由 `wechat-clawbot` 状态目录管理，还没有并入项目自己的 SQLite 真相。
- Telegram richer card/UI polish 仍然重要，但它是体验增强，不是 personal WeChat 最小私聊文本基线的硬前置。

---

## 5. 当前明确不做

- 通用 AI 助手
- 通用 Agent 平台
- 通用 plugin / skill / MCP 平台化
- Web UI / 桌面端
- Telegram / 微信群聊
- Redis / MQ / PostgreSQL
- 多机分布式部署

---

## 6. 工程立场

- parser-first，LLM-fallback
- 模型不负责幂等
- 模型不负责审批校验
- 模型不负责执行结果真相
- 模型不负责 lease/version
- 背景恢复和 scheduler tick 不依赖 LLM
- BT helper 当前只做只读辅助

---

## 7. 本地集成测试栈

涉及真实 downloader / import / refresh 联调时，使用 WSL Docker 本地测试栈：

- Transmission：`http://127.0.0.1:19091`
- Emby：`http://127.0.0.1:18096`

详细路径、健康检查、配置占位见 `docs/TEST_ENV.md`。

---

## 8. 文档入口

开始任何新任务前，先读：

1. `docs/DECISIONS.md`
2. `docs/NEXT_STEP.md`
3. `docs/STATUS.md`
4. `README.md`
5. `AGENTS.md`
6. `docs/HISTORY.md`（只看背景和演变，不看当前执行真相）

---

## 9. 一句话总结

**Luminarr 当前是一个 Telegram + Feishu + WeCom（最小私聊文本基线）的垂直影视自动化 Harness；当前主线已经打通搜索、审批、下载、状态、导入、命名、刮削、字幕、刷新，以及 PT/BT 分流、pure BT 单片优选、BT shared source adapter、BT external web-source、BT WebSource richer metadata extraction、BT-only read-only helper、shared private-chat text runtime、Telegram 最小图片/文件发送、personal WeChat 最小二维码登录入口、Feishu 最小私聊收发和 webhook 签名校验、WeCom callback URL 校验 / 解密入站 / 加密被动文本回包；当前 next step 是 personal WeChat private-chat text baseline。**
