# Luminarr

Luminarr 是一个**面向自托管影视自动化场景的自然语言驱动 Harness**。

它不是通用 AI 助手，也不是大而全媒体平台，而是把以下这条完整链路，放进一个**可控、可测、可恢复、可审计**的运行时里：

**意图理解 → 元数据解析 → 资源搜索 → 用户确认 → 投递下载 → 自动入库 → 规范化重命名 → 刮削元数据 → 字幕翻译 → 刷新媒体库 → 追更监控 → 状态通知 → 资源清理**

---

## 1. 当前主线运行画像（已落地 / 开发中）

| 维度 | 当前主线 |
|---|---|
| 用户渠道 | Telegram 私聊（唯一当前入口） |
| 元数据源 | TMDB |
| 搜索聚合 | Prowlarr |
| 下载器 | Transmission（PT 专用） |
| 媒体服务器 | Emby |
| 数据库 | SQLite |
| 部署方式 | Docker Compose |
| 实例规模 | 单实例 / 单进程 / 单机 |
| 内容优先级 | 电影优先，剧集 / 动漫后续跟进 |

---

## 2. 完整功能路线图

### 阶段 A：主链路控制层（当前阶段，大部分已落地）

- [x] Telegram 最小运行时
- [x] TMDB-first 电影元数据搜索
- [x] Prowlarr 资源聚合搜索
- [x] 中文海报卡片文本基线
- [x] 候选映射持久化（SQLite）
- [x] 下载选择显式审批（用户只需确认选哪个资源）
- [x] Transmission 投递
- [x] `status` 查询
- [x] 硬链接入库 + Emby refresh
- [x] `approval_record` lease/version 防重放
- [x] `jobs` 持久化执行所有权
- [x] Telegram message 去重
- [x] 歧义查询只读澄清隔离
- [x] 挫败感短路 / 重置
- [x] LLM 物理异常响应式恢复
- [x] 只读路径并发，副作用路径串行
- [x] Approval 超时自动取消
- [x] 手动 watchlist（add / list / remove / clear）
- [ ] Clarification pending 重启持久化（当前 next step）

### 阶段 B：自动化闭环升级

- [ ] **下载完成后自动入库**（D-037）：取消手动 import confirm，下载完 → 自动硬链接 → 自动刷新 Emby → 通知用户
- [ ] **文件规范化重命名**（D-042）：硬链接后自动按 Emby/Jellyfin/Plex 规格重命名
- [ ] **刮削元数据**（D-042）：自动从 TMDB + Fanart.tv 拉取 .nfo / 海报 / 背景图
- [ ] **字幕自动翻译**（D-041）：无中文字幕时自动提取英文字幕 → AI 翻译 → 写回 .zh.srt
- [ ] **资源选择规则化**（D-038 前置）：按分辨率 / 字幕 / 做种数等规则自动选优质资源，无需手选

### 阶段 C：追更与多内容类型

- [ ] **剧集 / 动漫追更**（D-038）：watchlist 驱动，后台定期检查新集数 → 自动搜索 → 自动下载 → 通知全链路进度
- [ ] **qBittorrent 接入**（D-039）：BT 专用下载器，与 Transmission（PT 专用）路由分离

### 阶段 D：渠道扩展

- [ ] **飞书 Bot**（D-040，优先）：官方 Webhook，API 最规范，消息卡片支持
- [ ] **企业微信 Bot**（D-040）：官方 Webhook，稳定无封号风险
- [ ] **个人微信**（D-040，最后）：iLink 长轮询，扫码登录

### 阶段 E：运维自动化

- [ ] **下载器与库文件关联监控**（D-043）：库文件删除 → 自动清理下载器任务；孤儿任务定期收敛
- [ ] **PT 做种保留策略**（D-043）：PT 资源按配置的做种时长 / 比例决定是否随库文件删除
- [ ] Copy fallback 审批（跨文件系统 import 场景）
- [ ] 真实海报图片渲染（现为文字卡片）
- [ ] Scheduler / 定时重试基线

---

## 3. 永远不做的事

- Web UI / 桌面端
- Telegram / 微信群聊
- Sonarr / Radarr 替代品（不做 season pack 拆包、复杂命名规则引擎）
- 通用 AI 助手 / 通用 Agent 平台
- 解压压缩包
- PostgreSQL / Redis / MQ（SQLite 长期主线）
- 多机分布式部署

---

## 4. 工程立场

Luminarr 不追求"更像一个通用 agent"，而追求：

1. **副作用动作有清晰边界**
2. **执行所有权有真相来源**
3. **失败可以阶段恢复**
4. **模型异常对用户透明**
5. **不该用 AI 的地方就不要用 AI**

parser-first，LLM-fallback；模型不负责幂等、不负责审批校验、不负责执行结果真相、不负责 lease/version。

---

## 5. 核心工具集（当前 + 规划）

| 工具 | 状态 | 说明 |
|---|---|---|
| `search_media` | 已落地 | 只读，可并发 |
| `add_to_downloader` | 已落地 | 有副作用，串行；后期加 PT/BT 路由 |
| `get_download_status` | 已落地 | 只读，可并发 |
| `import_to_library` | 已落地→改造 | D-037 后改为自动触发，不再手动 |
| `refresh_media_server` | 已落地 | 有副作用，串行 |
| `manage_watchlist` | 已落地 | D-038 后升级为追更驱动源 |
| `normalize_filename` | 规划（D-042）| 入库后规范化重命名 |
| `scrape_metadata` | 规划（D-042）| TMDB + Fanart.tv 刮削 |
| `translate_subtitle` | 规划（D-041）| 提取英文字幕 + AI 翻译 |
| `sync_downloader_assets` | 规划（D-043）| 关联监控 + 自动清理 |

---

## 6. 用户交互模型

**用户只需要做一件事：确认选哪部影视 / 哪个资源下载。**

其余全部自动：下载 → 入库 → 重命名 → 刮削 → 字幕翻译 → 刷新媒体库 → 通知完成。

追更场景：用户把剧加入 watchlist → 系统全自动，有更新通知，入库通知，无需再动手。

| 场景 | 用户操作 | 系统自动 |
|---|---|---|
| 搜索 | 说出影视名 | 查 TMDB + Prowlarr，返回候选列表 |
| 确认下载 | 选序号 → 确认 | 投递 Transmission |
| 下载中 | 可选：查进度 | 监控状态 |
| 下载完成 | 无需操作 | 硬链接 → 重命名 → 刮削 → 字幕检测 → Emby refresh → 通知 |
| 追更 | 加入 watchlist | 定期检查新集 → 自动全链路 → 通知 |

---

## 7. 部署前提

宿主机目录（正式环境）：

```text
/srv/media/
├── downloads/
│   ├── tr/              ← Transmission 下载目录（PT）
│   ├── qb/              ← qBittorrent 下载目录（BT，后期）
│   └── incomplete/
└── library/
    ├── movies/
    ├── tv/
    └── anime/

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
/data/downloads/qb
/data/library/movies
/data/library/tv
/data/library/anime
```

**硬链接约束：下载目录与库目录必须在同一文件系统。**

---

## 8. 文档入口

开始任何新任务前，先读：

1. `docs/DECISIONS.md`
2. `docs/NEXT_STEP.md`
3. `docs/STATUS.md`
4. `AGENTS.md`

---

## 9. 本地集成测试栈

开发环境：Windows + WSL（Ubuntu），仓库在 WSL 内，Codex 在 WSL 命令行交互。

涉及硬链接 / Emby refresh / Transmission RPC 的集成验证，使用 WSL Docker 本地测试栈：

| 服务 | 用途 | 地址 |
|---|---|---|
| Transmission | 下载器测试实例 | `http://localhost:9091` |
| Emby | 媒体服务器测试实例 | `http://localhost:8096` |

详细配置见 `docs/TEST_ENV.md`。

---

## 10. 一句话总结

**Luminarr = 一个面向 2–4 人自托管场景的完整影视自动化 Harness：用自然语言选片确认，其余从下载到入库到刮削到字幕翻译到追更通知全部自动完成，副作用有边界，状态有真相，失败有恢复，渠道可扩展。**
