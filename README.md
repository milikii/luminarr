# Luminarr

Luminarr 是一个面向自托管影视自动化场景的轻量自然语言 Agent。

它只专注一个小垂直领域：

- 搜索影视/动漫资源
- 投递到下载器
- 查询下载状态
- 下载完成后硬链接入库
- 刷新 Jellyfin / Emby
- 管理追更列表

用户主要通过 Telegram 与它交互；系统内部通过少量结构化工具和明确工作流执行操作。

## 当前定位

Luminarr 不是通用型 AI 助手，也不是传统大而全的媒体管理面板。

它当前只做：

- Telegram 主渠道
- 一个下载器（Transmission 或 qBittorrent 二选一）
- Prowlarr 搜索
- Jellyfin / Emby 刷新
- SQLite 状态持久化
- Docker Compose 部署

微信是后续辅助渠道，不是 v1 主验收范围。

## 目标用户

适合这类用户：

- 有 NAS / VPS / Docker / Linux 基础操作经验
- 不一定会写代码，但能执行命令、看日志、改配置
- 希望通过聊天完成媒体自动化，而不是频繁点 Web UI

## v1 范围

v1 只做这 6 个工具能力：

- `search_media`
- `add_to_downloader`
- `get_download_status`
- `import_to_library`
- `refresh_media_server`
- `manage_watchlist`

## 当前开发原则

- Telegram 是唯一主验收渠道
- 保留自然语言体验，但内部必须走结构化工具调用
- 路径设计必须兼容 Docker 共享 `/data` 根路径
- 硬链接前提是：下载目录和媒体库目录在同一文件系统
- 优先保证“搜索 → 下载 → 入库 → 刷新”主链路稳定
- 字幕翻译、微信、Skills 都后置

## 推荐目录设计

宿主机：

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

容器内统一视图：

```text
/data/downloads/tr
/data/downloads/qb
/data/library/movies
/data/library/shows
/data/library/anime
```

## 本地开发环境

当前默认环境：

- Windows
- Codex Desktop
- Ubuntu WSL
- Docker Desktop with WSL integration

建议把仓库放在 WSL 内，例如：

```bash
mkdir -p ~/projects/luminarr
cd ~/projects/luminarr
```

## 快速开始

### 1. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行测试

```bash
.venv/bin/pytest -q
```

### 4. 运行应用

```bash
export TELEGRAM_BOT_TOKEN="你的 Bot Token"
python -m app.main
```

### 5. 最小手工验收

- 给 Bot 发送任意消息
- 预期收到固定回复：`✅ 我收到了`

## 开发节奏

建议固定按以下顺序推进：

1. Telegram 收发消息
2. `search_media`
3. `add_to_downloader`
4. `get_download_status`
5. `import_to_library`
6. `refresh_media_server`
7. `manage_watchlist`
8. 字幕 / 微信 / Skills

## 当前状态文件

请始终维护：

- `AGENTS.md`
- `docs/STATUS.md`
- `docs/NEXT_STEP.md`

每次开新线程前，让 Codex 先读取这三个文件再继续工作。
