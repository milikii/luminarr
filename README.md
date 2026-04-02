# Luminarr (v15)

Luminarr 是一个**面向自托管影视自动化场景的轻量自然语言 Harness**。
它不是通用 AI 助手，也不是大而全媒体平台，而是把：

**搜索 -> 选择 -> 审批 -> 提交下载 -> 查询状态 -> 导入 -> 刷新**

这条链路，放进一个**可控、可测、可恢复、可审计**的运行时里。

---

## 1. 当前固定运行画像

当前主线写死为：

- **Telegram 私聊**：唯一用户入口
- **TMDB**：唯一元数据源
- **Prowlarr**：唯一搜索聚合器
- **Transmission**：唯一下载器
- **Emby**：唯一媒体服务器
- **SQLite**：唯一数据库
- **Docker Compose**：唯一部署方式
- **单实例 / 单进程 / 单机**
- **电影优先**

当前不是：
- 通用 AI 助手
- 通用 Agent 平台
- Sonarr / Radarr 替代品
- qBittorrent / Jellyfin 双线并行项目
- 自动 watchlist 下载系统

---

## 2. 当前已落地能力

目前仓库已经落地的主链能力包括：

- Telegram 最小运行时
- `search_media`
- TMDB-first 电影元数据基线
- 固定搜索顺序：
  1. English title + year
  2. original title + year
  3. parser-normalized original query（仅 TMDB 不可用或无命中时）
- 中文海报卡片文本基线
- 候选映射持久化（SQLite）
- `add_to_downloader` 显式审批
- Transmission 投递
- `status <id/hash>` 查询
- `import <id/hash>` 进入 pending
- `confirm <id/hash>` 路由到 downloader/import 的待确认副作用
- `approval_record` 最小 pending/approved 协议
- downloader/import confirm 的最小 lease/version 防重放
- `job_event` 最小事件轨迹

---

## 3. v15 这次调整了什么

这版文档吸收了新的 review 意见，但不会把系统直接拉向“大而全”。
v15 采纳的是**工程原则升级**，不是“下一步一次做完 5 个大特性”。

### 已采纳为制度规则
- 只读工具允许进入**安全并发调度**；有副作用工具必须串行
- 对 LLM 的 413 / 截断等**物理异常**，后续要走响应式恢复，而不是把错误暴露给用户
- 模糊搜索允许使用**只读探索代理 / 探索子流程**，但不得污染主状态机
- 任务从审批挂起恢复时，必须做**精确上下文重建**
- 在 Telegram 交互层加入**低成本挫败感探测与短路重置**

### 尚未实现、但不再忽视
- `telegram_updates` 已落地为 Telegram message de-dup 真相源
- `jobs.version + lease_owner + lease_until` 已落地为 import wake/replay + downloader approval wake/replay 最小真相
- `confirm <id/hash>` 的 approval-wake context rebuild 已落地
- frustration/reset short-circuit 已落地到选择 reset + pending downloader/import cancel
- approval expiry / timeout policy
- 真正的 concurrency-safe executor
- reactive recovery implementation
- watchlist baseline（重新回到下一步）

---

## 4. 当前最重要的工程立场

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

## 5. 工具与调度原则

当前核心工具仍然只保留 6 个：

- `search_media`
- `add_to_downloader`
- `get_download_status`
- `import_to_library`
- `refresh_media_server`
- `manage_watchlist`

### 调度纪律
- `search_media`、`get_download_status`：只读，可并发
- `add_to_downloader`、`import_to_library`、`refresh_media_server`：有副作用，串行
- 同一 job 的副作用路径必须持有执行所有权
- `manage_watchlist` 先按串行实现，后续如仅做提醒查询再放宽

---

## 6. 审批与上下文重建

当前已经落地：
- 选择序号不会立即投递下载，而是先进入 pending approval
- `import <id/hash>` 只进入 pending
- `confirm <id/hash>` 才执行 downloader/import 副作用

v15 新要求：
- 审批唤醒后，执行阶段不得直接复用旧对话长历史
- 必须从持久化状态重建一个极小执行上下文
- 后续 `add_to_downloader` 也要遵循同样模式

---

## 7. 当前不该做什么

不要把下一步发散到这些方向：
- watchlist 自动下载
- 多下载器并行支持
- 多媒体服务器并行支持
- Webhook / Web UI / 群聊
- 一次性引入 Redis / MQ / PostgreSQL
- 复杂命名模板 / 解压 / 清理策略
- 通用多 Agent 平台化

---

## 8. 下一步正确优先级

v15 下，执行卫生和控制层已补到 downloader approval。
下一步应回到 **watchlist baseline**：

1. `telegram_updates` 去重真相源
2. `jobs` 表最小执行所有权协议
3. approval-wake context rebuild
4. frustration detector / deterministic reset
5. `add_to_downloader` 的显式审批
6. 现在回到 watchlist baseline

---

## 9. 部署前提

推荐宿主机目录：

```text
/srv/media/
├── downloads/
│   ├── tr/
│   ├── incomplete/
│   └── watch/
└── library/
    └── movies/

/srv/luminarr/
├── config/
├── data/
├── logs/
├── cache/
└── backups/
```

容器内统一视图：

```text
/data/downloads/tr
/data/library/movies
```

约束：
- 下载目录和库目录必须位于同一文件系统
- 硬链接优先
- 硬链接失败默认不自动 copy
- copy fallback 必须审批

---

## 10. 文档入口

开始任何新任务前，先读：

1. `docs/DECISIONS.md`
2. `docs/NEXT_STEP.md`
3. `docs/STATUS.md`
4. `AGENTS.md`

---

## 11. 一句话总结

**Luminarr v15 = 一个电影优先、Telegram 私聊唯一入口的垂直媒体自动化 Harness；它保留 TMDB-first 搜索、import-confirm、最小 lease/version 防重放等已落地能力，同时把“安全并发、响应式恢复、审批唤醒重建、挫败感短路”正式提升为下一阶段工程纪律。**
