# Luminarr (v36)

Luminarr 是一个面向 **2–4 人自托管影视场景** 的垂直自动化 Harness。

它当前不是通用 Agent 平台，也不是通用 skill 平台。它的目标很窄：让 Telegram 私聊里的影视下载和入库链路稳定跑通。

---

## 1. 当前主线是什么

当前固定主线：

- Telegram 私聊
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

- **BT-only read-only helper baseline**

这一步已完成：

- 只服务 BT 分流
- 新增 `bt搜 <关键词>` / `bt search <关键词>` 最小只读探索入口
- helper 复用现有 `Prowlarr + WebSource` 共享 BT 来源适配入口
- 输出只包含文本候选、来源入口和链接参考
- helper 不写 workflow truth，不创建 approval，不 dispatch 下载器，不触发 import / refresh
- 保持现有 downloader / import 审批边界不变

当前 next step：

- richer BT WebSource site-rule enrichment baseline

---

## 4. 后续路线

当前已明确的后续顺序：

1. richer BT WebSource site-rule enrichment baseline
2. Feishu / WeCom / personal WeChat
3. downloader/library asset correlation and cleanup

补充说明：

- BT external web-source 当前已经先通过项目内共享 BT 来源适配层进入 BT 支线，没有污染 PT 主链。
- BT-only read-only helper 当前只提供最小文本型只读探索，不写 workflow truth、不得 dispatch 下载器、不得触发 import / refresh。
- 下一步只扩 WebSource 的确定性站点规则和结构化字段，不把 helper 扩成通用问答框架。

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

**Luminarr 当前是一个 Telegram 私聊唯一入口的垂直影视自动化 Harness；当前主线已经打通搜索、审批、下载、状态、导入、命名、刮削、字幕、刷新，以及 PT/BT 分流、pure BT 单片优选、BT shared source adapter、BT external web-source 和 BT-only read-only helper；当前 next step 是 richer BT WebSource site-rule enrichment baseline。**
