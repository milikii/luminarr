# Luminarr (v27)

Luminarr 是一个**面向 2–4 人自托管影视场景的垂直自动化 Harness**。

当前已实现主线已经补到：

**搜索 -> 选择 -> 下载审批 -> 投递下载 -> 查询状态 / 完成观察 -> 导入审批 -> 硬链接入库 -> 规范化命名 / metadata scrape / subtitle auto-translation / Emby 刷新**

更长的完整自动化链路：

**意图 -> 元数据 -> 搜索 -> 用户确认 -> 下载 -> 自动入库 -> 规范化命名 -> 刮削 -> 字幕 -> 刷新 -> 追更 -> 通知 -> 清理**

是后续阶段路线，不是当前已经落地的事实。

---

## 1. 当前固定运行画像

当前主线固定为：

- **Telegram 私聊**：唯一当前入口
- **TMDB**：唯一元数据源
- **Prowlarr**：唯一搜索聚合器
- **Transmission**：当前唯一已实现下载器客户端
- **Emby**：唯一媒体服务器
- **SQLite**：唯一数据库
- **Docker Compose**：唯一部署方式
- **单实例 / 单进程 / 单机**
- **电影优先**

---

## 2. 当前主线已落地能力

目前仓库已经落地的主链能力包括：

- Telegram 最小运行时
- `search_media`
- TMDB-first 电影元数据搜索
- 固定搜索顺序：
  1. English title + year
  2. original title + year
  3. parser-normalized original query（仅 TMDB 不可用或无命中时）
- 中文海报卡片文本基线
- 候选映射持久化（SQLite）
- `add_to_downloader` 显式审批
- `status <id/hash>` 查询
- `import <id/hash>` 进入 pending
- `confirm <id/hash>` 路由到 downloader/import 的待确认副作用
- downloader/import confirm 的最小 lease/version 防重放
- `telegram_updates` 去重真相源
- `jobs.version + lease_owner + lease_until` 最小执行所有权
- approval-wake context rebuild
- frustration/reset short-circuit
- approval expiry / timeout baseline
- LLM 物理异常响应式恢复最小基线
- read-only concurrency-safe execution policy baseline
- ambiguous-title 只读澄清隔离
- clarification pending restart-durable baseline
- Telegram callback workflow routing baseline
- cross-filesystem import copy fallback approval baseline
- completion-monitor / scheduler prerequisite baseline
- post-download auto import baseline
- resource auto-selection rules baseline
- filename normalization / rename baseline
- metadata scraping（`TMDB + Fanart.tv`）baseline
- subtitle auto-translation baseline
- 手动 `watchlist` 基线（add/list/remove/clear）
- `watchlist` 的 `movie / series / anime` 最小分类持久化
- 硬链接导入 + Emby refresh

---

## 3. 当前最近一步

当前 next step 不是下载器角色绑定，也不是 BT 后半段投递，而是：

- **PT / BT parser-level intent split baseline**

这一小步的目标是：

- 在 parser / 路由层，先把“正常观影需求”和“直接 BT / 磁力下载需求”分开
- 当前这一步不引入下载器角色绑定，不引入 qBittorrent，不引入 BT 分类后半段
- 当前这一步不直接改变现有 downloader / import 副作用链
- 保持当前 `search/select/add/status/import/confirm/watchlist` 行为稳定

---

## 4. 当前所处阶段与后续路线

下面这些用于说明：项目刚补完了哪一段，以及后面按什么顺序继续走。推进顺序仍然固定为“每次只做一个小目标”。

### 已落地的自动化闭环补齐

- 下载完成观察 + completion-monitor 真相
- post-download auto import（仍然保留 `confirm <id/hash>` 边界）
- 文件规范化命名
- 元数据刮削（TMDB + Fanart.tv）
- 字幕自动翻译

### 阶段 C：追更、PT/BT 分流与多内容类型

- 剧集 / 动漫 watchlist-driven tracking 基线已落地（当前先只补 `watchlist` 的 `media_kind` 真相）
- PT / BT parser-level intent split：
  - `我想看 X` / `追更 X` / `watchlist` 继续走 PT 主干
  - 直接磁力 / 明确“下载这个 BT”走 BT 主干
- BT 主干先做资源分类询问：
  - 先问资源分类（电影 / 电视剧 / 动漫 / 其他 BT 资源）
  - 选电影 / 电视剧 / 动漫时：做 TMDB 关联，下载完成后继续走命名 / metadata / 海报 / 字幕 / refresh
  - 选其他 BT 资源时：只做下载 -> 转移/放置文件；系统先展示预设目标目录选项，再由用户决定放到哪个目录
- 下载器实例与角色绑定：
  - 支持两种协议：Transmission / qBittorrent
  - 支持多个实例：你可以有多个 TR、多个 QB
  - `pt_downloader` / `bt_downloader` 只绑定到实例名，不写死软件类型
  - PT 和 BT 可以共用同一个实例，也可以分别走不同实例
- `qBittorrent` 作为后续要接入的协议，而不是当前已落地事实
- 只有上述分流稳定后，才评估 BT subscription / continuous-download 这类下一小步

### 阶段 D：渠道扩展

- 飞书
- 企业微信
- 个人微信

### 阶段 E：运维自动化

- 下载器资源与库文件关联监控
- 孤儿任务与清理策略

---

## 5. 当前不该做什么

### 不是当前主线

- 自动 watchlist 下载
- BT/PT 分流
- 多下载器角色绑定
- 多媒体服务器并行支持
- 多渠道并行接入
- 通用 scheduler 平台化

### 明确不做

- 通用 AI 助手
- 通用 Agent 平台
- Web UI / 桌面端
- Telegram / 微信群聊
- 一次性引入 Redis / MQ / PostgreSQL
- 多机分布式部署
- 解压压缩包流程

---

## 6. 与 OpenHarness 的关系

OpenHarness 是一个更通用的 agent harness；Luminarr 不是它的替代品，也不应该被改造成它那种形状。

当前只明确借鉴这些工程机制：

- 后台任务生命周期
- 统一 hook 点（工具前 / 工具后）
- path-level 权限规则
- 多 agent 协调思路

当前明确不借鉴这些方向：

- 通用工具箱平台
- React TUI
- plugin / skill / MCP 平台化

---

## 7. 工程立场

Luminarr 当前不追求“像一个更通用的 agent”，而追求：

1. **副作用动作有清晰边界**
2. **执行所有权有真相来源**
3. **失败可以阶段恢复**
4. **模型异常对用户尽量透明**
5. **不该用 AI 的地方就不要用 AI**

因此：

- parser-first，LLM-fallback
- 模型不负责幂等
- 模型不负责审批校验
- 模型不负责执行结果真相
- 模型不负责 lease/version

---

## 8. 本地集成测试栈

涉及 `add_to_downloader`、`import_to_library`、`refresh_media_server` 的真实联调，使用 WSL Docker 本地测试栈：

- Transmission：`http://127.0.0.1:19091`
- Emby：`http://127.0.0.1:18096`

详细路径、健康检查、配置占位见 `docs/TEST_ENV.md`。

---

## 9. 文档入口

开始任何新任务前，先读：

1. `docs/DECISIONS.md`
2. `docs/NEXT_STEP.md`
3. `docs/STATUS.md`
4. `README.md`
5. `AGENTS.md`

---

## 10. 一句话总结

**Luminarr v27 = 一个电影优先、Telegram 私聊唯一入口的垂直媒体自动化 Harness；当前主线已经补到 completion-monitor、post-download auto import、rename、metadata scraping、subtitle auto-translation，以及 `watchlist` 的 `movie / series / anime` 最小分类真相，当前最近一步前进到 PT/BT parser-level 分流。**
