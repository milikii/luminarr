# Luminarr

Luminarr 是一个**面向自托管影视 / 动漫自动化场景的轻量自然语言 Agent**。

它的目标不是替代所有现有媒体工具，而是把“**搜索 -> 下载 -> 入库 -> 刷新媒体库 -> 状态查询 -> 追更**”这条链路串起来，让用户主要通过 **Telegram** 与系统交互，并在后续支持 **微信辅助入口**。

> 当前项目路线：**自建极简底座**、**Telegram 主验收渠道**、**Docker Compose 部署**、**统一 `/data` 路径设计**、**先主链路后扩展字幕/刮削/Skills**。

---

## 1. 项目定位

### 一句话

**Luminarr = 一个专注影视自动化的小垂直自然语言 Agent。**

用户通过聊天完成：
- 搜索资源
- 投递下载
- 查看下载状态
- 下载完成后入库
- 刷新 Jellyfin / Emby
- 管理追更

### 不追求的方向

Luminarr **不是**：
- 通用 AI 助手
- 多领域工具平台
- OpenClaw 替代品
- 一开始就覆盖所有下载器 / 所有媒体服务器 / 所有聊天平台的大而全系统
- 以 Web UI 为核心的传统媒体管理面板

### 当前边界

当前阶段只专注：
- 影视 / 动漫资源自动化
- 自然语言交互
- 工具调用可控、可测试、可恢复
- 适合 NAS / VPS / Docker 场景

---

## 2. 适合谁

Luminarr 适合这类用户：
- 有 NAS / VPS / Docker / Linux 基础操作经验
- 不一定会写代码，但能执行命令、配置服务、查看日志
- 希望少折腾前端，多通过聊天完成操作
- 个人或小范围自用（1-3 人）

---

## 3. 当前架构原则

### 用户看到的是自然语言

例如：
- 帮我找《星际穿越》4K，优先蓝光原盘
- 把昨天卡住的任务重试一下
- 这部番下周有新集吗

### 系统内部是结构化执行

系统内部不会让模型直接“自由发挥”，而是固定走：
1. 理解用户意图
2. 提取结构化参数
3. 选择少量已定义工具
4. 推进明确工作流
5. 对高风险动作要求确认
6. 将关键状态持久化到 SQLite

### 主渠道与辅助渠道

- **Telegram**：主渠道、主验收渠道
- **微信**：后续辅助渠道，不进入 v1 主线验收

---

## 4. 当前 v1 核心能力

v1 只围绕这 6 个核心工具展开：

- `search_media`
- `add_to_downloader`
- `get_download_status`
- `import_to_library`
- `refresh_media_server`
- `manage_watchlist`

说明：
- `add_to_downloader` 统一处理搜索结果、magnet、torrent 文件三类输入
- 不在 v1 中把同类能力拆成大量细碎工具

---

## 5. 部署范围说明（重要）

## Luminarr 的 Docker 部署 **只包含 Luminarr 自己**

本项目当前的 Docker / Docker Compose 部署，指的是：

- 部署 **Luminarr 服务本体**
- 挂载配置目录、数据库目录、日志目录、媒体公共根目录
- 通过配置连接**已经存在的外部服务**

### 当前 **不内置、不打包、不代管** 的程序

以下程序默认视为**外部依赖**，由用户自行部署、维护和配置：

- **Prowlarr**：资源搜索 / 索引聚合
- **Transmission** 或 **qBittorrent**：下载器（v1 先支持其中一个）
- **Jellyfin** 或 **Emby**：媒体服务器
- **TMDB / Bangumi**：元数据来源

也就是说：

**Luminarr 不负责替你一键部署整套媒体生态。**
它只负责作为“媒体自动化编排层”和“聊天入口层”，连接并调度这些已有组件。

---

## 6. 运行 Luminarr 之前，你需要准备什么

在运行 Luminarr 之前，建议你已经具备以下外部服务：

### 必需

1. **一个聊天入口**
   - Telegram Bot Token（v1 必需）

2. **一个搜索聚合器**
   - Prowlarr

3. **一个下载器**
   - Transmission **或** qBittorrent（二选一）

4. **一个媒体服务器**
   - Jellyfin **或** Emby（二选一）

5. **媒体目录规划**
   - 下载目录
   - 媒体库目录
   - 二者位于同一文件系统

### 推荐

6. **元数据来源配置**
   - TMDB API Key
   - Bangumi（后续用于动漫增强）

7. **稳定的 Docker / NAS 路径规划**
   - 宿主机媒体根目录，例如 `/srv/media`
   - Luminarr 配置 / 数据目录，例如 `/srv/luminarr`

---

## 7. 路径与硬链接要求（非常重要）

Luminarr 设计默认遵循这条前提：

- 下载目录和媒体库目录必须位于**同一文件系统**
- 相关容器内部尽量看到**统一公共根路径**，例如 `/data`

推荐宿主机结构：

```text
/srv/media/
├── downloads/
│   ├── tr/
│   ├── qb/
│   ├── incomplete/
│   └── watch/
└── library/
    ├── movies/
    ├── shows/
    └── anime/

/srv/luminarr/
├── config/
├── data/
├── logs/
└── cache/
```

推荐容器内视图：

```text
/data/downloads/tr
/data/downloads/qb
/data/library/movies
/data/library/shows
/data/library/anime
```

### 为什么必须这样

因为：
- 硬链接不能跨文件系统
- 路径设计混乱会让后续入库、刷新、清理都变复杂
- 统一 `/data` 视图最适合长期维护和排错

---

## 8. 最小部署思路

### 你要部署的只有：
- Luminarr 容器

### 你要在配置里填写的通常包括：
- Telegram Bot Token
- 模型 API 地址 / Key
- Prowlarr 地址与 API Key
- 下载器地址与认证信息
- Jellyfin / Emby 地址与 API Key
- 媒体根路径映射
- SQLite 数据库路径

### 你需要自己保证：
- 外部服务已经能正常访问
- 下载目录和媒体库目录路径规划正确
- Luminarr 容器能看到共享媒体根目录

---

## 9. 当前开发节奏

### Phase 0
先搭好：
- README
- AGENTS.md
- docs/STATUS.md
- docs/NEXT_STEP.md
- 基础项目骨架

### Phase 1
只做最小可用闭环：
- Telegram 收消息
- 自然语言触发搜索
- 选择候选
- 投递到下载器
- 查看状态

### Phase 2
再做：
- 下载完成检测
- 硬链接入库
- 刷新 Jellyfin / Emby

### Phase 3
再做：
- watchlist / 追更

### Phase 4
再做：
- 字幕处理
- 更强刮削能力
- 微信辅助渠道
- Skills 化扩展

---

## 10. 开发环境

当前默认开发环境：
- Windows
- Codex Desktop
- Ubuntu WSL
- 项目仓库放在 WSL 内

建议：
- 代码始终在 WSL 的 Linux 文件系统里维护
- 通过 Git 与 GitHub 同步
- 用 Codex 负责计划、改代码、跑测试、更新状态文件
- 由人来做最终验收、commit、push

---

## 11. 当前状态文件

为了防止线程腐化、上下文丢失，项目长期维护以下文件：

- `AGENTS.md`：长期规则
- `docs/STATUS.md`：当前状态
- `docs/NEXT_STEP.md`：下一步唯一任务
- `docs/DECISIONS.md`：已拍板的架构与产品决策

新线程开始时，Codex 必须先读取这些文件，再继续当前任务。

---

## 12. 后续扩展方向

以下方向已经被保留为后续扩展，但不进入 v1 核心范围：

- 微信辅助接入
- Bangumi 动漫增强
- Subtitle 处理
- Metadata repair
- Library hygiene
- Skills 化本地扩展

---

## 13. 一句话总结

**Luminarr 当前不是“一键部署整套媒体栈”的项目，而是一个部署在你现有媒体生态之上的轻量自然语言编排层。**

它只负责把：
**搜索 -> 下载 -> 入库 -> 刷新 -> 查询 -> 追更**
这条链路通过聊天方式整合起来。
