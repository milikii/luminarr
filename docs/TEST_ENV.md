# docs/TEST_ENV.md — 本地集成测试栈配置

> 这份文件是 WSL Docker 本地测试栈的正式说明入口。
> 它记录端点、路径、健康检查和配置占位；不要把真实凭据提交到 Git。
> 真实用户名、密码、API Key、Library ID 应保存在本地 `.env` 或本地配置覆盖中。
> 当前仓库默认假设：Transmission 与 Emby 已作为 WSL 本机 Docker 常驻测试依赖运行。

---

## 测试栈位置

Docker Compose 文件：

```text
/home/alex/projects/luminarr/docker-compose.test.yml
```

测试栈配置目录根：

```text
/home/alex/luminarr-test
```

启动测试栈：

```bash
docker compose -f /home/alex/projects/luminarr/docker-compose.test.yml up -d
```

停止测试栈：

```bash
docker compose -f /home/alex/projects/luminarr/docker-compose.test.yml down
```

说明：
- PT Transmission 配置目录：`/home/alex/luminarr-test/config/transmission`
- BT Transmission 配置目录：`/home/alex/luminarr-test/config/transmission-bt-stack`
- Emby 配置目录：`/home/alex/luminarr-test/config/emby`
- 三个容器都运行在 WSL 本机 Docker 中，通过宿主机端口映射给应用访问
- 两个 Transmission 都按 LinuxServer 官方约定分别挂载 `/downloads/complete`、`/downloads/incomplete` 和 `/watch`；Emby 使用 `/data/library:/data/library` 挂载
- BT Transmission 会把 PT Transmission 已有的 `trguing-zh` 自定义 WebUI 只读挂进自己的 `/config/webui/trguing-zh`，所以两台 TR 的 WebUI 保持同一套界面资源，但运行状态仍各自独立
- 当前 compose 文件在仓库里，实际容器配置和状态仍落在 `/home/alex/luminarr-test`

---

## Transmission（下载器测试实例）

| 项目 | 值 |
|---|---|
| WSL 访问地址 | `http://127.0.0.1:19091` |
| RPC 路径 | `/transmission/rpc` |
| RPC 认证 | 当前测试栈已关闭认证（`TRANSMISSION_RPC_AUTHENTICATION_REQUIRED=false`） |
| 下载目录（宿主机） | `/data/downloads/tr` |
| 下载目录（容器内） | `/downloads/complete` |
| incomplete 目录（宿主机） | `/data/downloads/incomplete` |
| incomplete 目录（容器内） | `/downloads/incomplete` |
| watch 目录（宿主机） | `/data/downloads/watch` |
| watch 目录（容器内） | `/watch` |

健康检查：

```bash
curl -si http://127.0.0.1:19091/transmission/rpc | grep -q "X-Transmission-Session-Id" && echo "TR up" || echo "TR down"
```

---

## BT Transmission（BT 下载器测试实例）

| 项目 | 值 |
|---|---|
| WSL 访问地址 | `http://127.0.0.1:19092` |
| RPC 路径 | `/transmission/rpc` |
| RPC 认证 | 当前测试栈已关闭认证（`TRANSMISSION_RPC_AUTHENTICATION_REQUIRED=false`） |
| 下载目录（宿主机） | `/data/downloads/tr-bt` |
| 下载目录（容器内） | `/downloads/complete` |
| incomplete 目录（宿主机） | `/data/downloads/incomplete-bt` |
| incomplete 目录（容器内） | `/downloads/incomplete` |
| watch 目录（宿主机） | `/data/downloads/watch-bt` |
| watch 目录（容器内） | `/watch` |
| 配置目录（宿主机） | `/home/alex/luminarr-test/config/transmission-bt-stack` |
| 自定义 WebUI | 继续复用 PT Transmission 的 `trguing-zh`（只读挂载） |

健康检查：

```bash
curl -si http://127.0.0.1:19092/transmission/rpc | grep -q "X-Transmission-Session-Id" && echo "BT TR up" || echo "BT TR down"
```

---

## Emby（媒体服务器测试实例）

| 项目 | 值 |
|---|---|
| WSL 访问地址 | `http://127.0.0.1:18096` |
| API Key | `（按本地实际填写，在 Emby 管理后台生成）` |
| 库路径（宿主机） | `/data/library/movies` |
| 库路径（容器内） | `/data/library/movies` |
| Library ID | 当前代码未使用，可留在本地记录中 |

健康检查：

```bash
curl -s http://127.0.0.1:18096/System/Info/Public | grep -q "ServerName" && echo "Emby up" || echo "Emby down"
```

---

## 路径约束（硬链接必须满足）

下载目录和库目录**必须在同一 WSL 文件系统**上：

```text
/data/downloads/tr
/data/downloads/tr-bt
/data/library/movies
```

验证是否同一文件系统：

```bash
stat -c "%d %n" /data/downloads/tr /data/downloads/tr-bt /data/library/movies
```

三个路径的设备号相同，才表示 PT / BT 两个 Transmission 到媒体库都满足硬链接前提。

---

## 对应的 app 配置（.env 或本地 config）

```env
# Telegram
TELEGRAM_BOT_TOKEN=（按本地实际填写）

# Prowlarr
PROWLARR_BASE_URL=http://192.168.2.220:7188
PROWLARR_API_KEY=（按本地实际填写）

# TMDB
TMDB_API_KEY=（按本地实际填写）

# Transmission
TRANSMISSION_BASE_URL=http://127.0.0.1:19091
TRANSMISSION_USERNAME=
TRANSMISSION_PASSWORD=

# 可选：如果你要让 PT / BT 在本地测试栈里明确分流到两台 Transmission
DOWNLOADER_INSTANCES=tr-pt|transmission|http://127.0.0.1:19091|/data/downloads/tr;tr-bt|transmission|http://127.0.0.1:19092|/data/downloads/tr-bt
PT_DOWNLOADER=tr-pt
BT_DOWNLOADER=tr-bt

# Emby
EMBY_BASE_URL=http://127.0.0.1:18096
EMBY_API_KEY=（按本地实际填写）

# 导入目标目录（WSL 宿主机视角，供 import hardlink 使用）
LIBRARY_TARGET_DIR=/data/library/movies

# SQLite
SQLITE_DB_PATH=/home/alex/projects/luminarr/data/luminarr.db
```

说明：
- 当前代码读取的是 `TRANSMISSION_BASE_URL`，不是 `TRANSMISSION_HOST`
- 当前代码读取的是 `TRANSMISSION_USERNAME` / `TRANSMISSION_PASSWORD`，不是 `TRANSMISSION_USER` / `TRANSMISSION_PASS`
- 如果你要验证 PT / BT 双 Transmission 分流，当前代码要靠 `DOWNLOADER_INSTANCES + PT_DOWNLOADER + BT_DOWNLOADER` 明确绑定；只填 `TRANSMISSION_BASE_URL` 时，两条链都会落回默认 Transmission
- 当前代码读取的是 `LIBRARY_TARGET_DIR`，不是 `LIBRARY_MOVIES_PATH`
- 当前测试栈 Transmission 关闭了 RPC 认证，所以用户名和密码可留空

---

## Codex 使用规范

1. 执行涉及 `import_to_library` / `refresh_media_server` / `add_to_downloader` 的端到端验证前，必须先做健康检查。
2. 如果健康检查失败，不要继续执行，先让用户启动测试栈。
3. 后续联调默认把 `PT Transmission(http://127.0.0.1:19091)`、`BT Transmission(http://127.0.0.1:19092)` 和 `Emby(http://127.0.0.1:18096)` 视为常驻依赖；正常情况下无需再次询问用户“它们在哪里”。
4. 不要把测试栈真实凭据硬编码进仓库代码，始终从本地 config / `.env` 读取。
5. 测试完成后，Transmission 中的测试任务和 Emby 中的测试媒体条目可以手动清理，不要求仓库代码自动清理。
