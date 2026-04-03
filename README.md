# Luminarr (v20)

Luminarr 是一个**面向 2–4 人自托管影视场景的垂直自动化 Harness**。

当前已实现主线仍然是：

**搜索 -> 选择 -> 下载审批 -> 投递下载 -> 查询状态 -> 导入审批 -> 硬链接入库 -> Emby 刷新**

更长的完整自动化链路：

**意图 -> 元数据 -> 搜索 -> 用户确认 -> 下载 -> 自动入库 -> 规范化命名 -> 刮削 -> 字幕 -> 刷新 -> 追更 -> 通知 -> 清理**

是后续阶段路线，不是当前已经落地的事实。

---

## 1. 当前固定运行画像

当前主线固定为：

- **Telegram 私聊**：唯一当前入口
- **TMDB**：唯一元数据源
- **Prowlarr**：唯一搜索聚合器
- **Transmission**：唯一下载器
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
- 手动 `watchlist` 基线（add/list/remove/clear）
- 硬链接导入 + Emby refresh

---

## 3. 当前最近一步

当前 next step 不是 watchlist，也不是自动化大升级，而是：

- **最小 completion-monitor / scheduler 前置能力**

这一小步的目标是：

- 给后续自动化闭环准备最小运行时真相
- 不引入通用 scheduler 平台化
- 复用已有持久化与执行所有权边界
- 保持当前 `search/select/add/status/import/confirm/watchlist` 行为稳定

---

## 4. 当前之后的阶段化路线

下面这些是**后续路线**，不是当前一步要同时开工的内容。推进顺序固定为“每次只做一个小目标”。

### 阶段 A：控制层收尾

- 最小 completion-monitor / scheduler 前置能力

### 阶段 B：自动化闭环

- 下载完成后自动入库
- 资源自动选优规则
- 文件规范化重命名
- 元数据刮削（TMDB + Fanart.tv）
- 字幕自动翻译

### 阶段 C：追更与多内容类型

- 剧集 / 动漫 watchlist 驱动追更
- BT/PT 分离下载器路由
- `qBittorrent` 作为后续 BT 下载器

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
- 多下载器并行支持
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

## 6. 工程立场

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

## 7. 本地集成测试栈

涉及 `add_to_downloader`、`import_to_library`、`refresh_media_server` 的真实联调，使用 WSL Docker 本地测试栈：

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

---

## 9. 一句话总结

**Luminarr v20 = 一个电影优先、Telegram 私聊唯一入口的垂直媒体自动化 Harness；当前主线已经把搜索、审批、下载、导入、刷新和执行卫生补到了较稳定状态，callback 路由与 cross-filesystem copy fallback approval 已落地，下一步补最小 completion-monitor / scheduler 前置能力。**
