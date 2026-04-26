# docs/TEST_ENV.md — 本地集成测试栈配置

> 这份文件是 WSL Docker 本地测试栈的正式说明入口。
> 它记录端点、路径、健康检查和配置占位；不要把真实凭据提交到 Git。
> 真实用户名、密码、API Key、Library ID 应保存在本地 `.env` 或本地配置覆盖中。
> 当前仓库默认假设：Transmission / qBittorrent 与 Emby 已作为 WSL 本机 Docker 常驻测试依赖运行。
> 当前正式本地真实 refresh 测试栈仍以 Emby 为固定入口；qBittorrent 现在作为下载器协议辅助实例一并放进测试栈，但 Jellyfin / Plex 仍处在 readiness 评估阶段，不视为本仓库现成可用的固定容器入口。

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

如果当前 WSL shell 直接报 `/var/run/docker.sock` `permission denied`，就在宿主机可用的 sudo 环境里改用：

```bash
sudo docker compose -f /home/alex/projects/luminarr/docker-compose.test.yml up -d
```

停止测试栈：

```bash
docker compose -f /home/alex/projects/luminarr/docker-compose.test.yml down
```

说明：
- PT Transmission 配置目录：`/home/alex/luminarr-test/config/transmission`
- BT Transmission 配置目录：`/home/alex/luminarr-test/config/transmission-bt-stack`
- qBittorrent 配置目录：`/home/alex/projects/luminarr/docker/test/qbittorrent`
- Emby 配置目录：`/home/alex/luminarr-test/config/emby`
- 四个容器都运行在 WSL 本机 Docker 中，通过宿主机端口映射给应用访问
- 两个 Transmission 都按 LinuxServer 官方约定分别挂载 `/downloads/complete`、`/downloads/incomplete` 和 `/watch`；qBittorrent 与 Emby 分别按宿主机同路径挂载 `/data/downloads/qb`、`/data/downloads/incomplete-qb` 与 `/data/library:/data/library`
- BT Transmission 会把 PT Transmission 已有的 `trguing-zh` 自定义 WebUI 只读挂进自己的 `/config/webui/trguing-zh`，所以两台 TR 的 WebUI 保持同一套界面资源，但运行状态仍各自独立
- 当前 qB 测试栈为避免 WebUI `Host header` 端口不匹配，必须保持 `WEBUI_PORT=18098` 和 `18098:18098` 同步；不要回退成 `18098:8080`
- qB 容器会在 `docker/test/qbittorrent/qBittorrent` 下生成 GeoDB / logs / RSS / lockfile / `qBittorrent-data.conf` 等运行态文件；这些文件不属于固定配置，不应提交到 Git
- 当前 compose 文件在仓库里，Transmission / Emby 的实际容器配置和状态仍主要落在 `/home/alex/luminarr-test`
- 截至 `2026-04-26` 本轮复验，`19091` RPC 返回 `409 + X-Transmission-Session-Id`、`19092` RPC 返回 `409 + X-Transmission-Session-Id`、`18096` 返回 `ServerName`、`18098/api/v2/torrents/info` 返回 `200 OK`

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

说明：
- 当前 `19092` 仍应按当轮探针重写，不直接沿用更早轮次的旧结论
- 当前补充 probe：

```bash
.venv/bin/python tmp_tests/verify_bt_transmission_rpc_probe.py
```

- 截至 `2026-04-26` 本轮，`bash -lc 'timeout 5 curl -si http://127.0.0.1:19092/transmission/rpc'` 已返回 `409 + X-Transmission-Session-Id`
- 当前 BT Transmission 成人归档 smoke：

```bash
bash -lc 'cd /home/alex/projects/luminarr && .venv/bin/python tmp_tests/verify_adult_archive_bt_real_smoke.py'
```

- 截至 `2026-04-26` 本轮，这条脚本当前通过，并把证据写到 `/tmp/luminarr_adult_archive_bt_real_smoke/evidence.json`。
- 当前通过态证据包含：
  - `session_snapshot.download_dir=/downloads/complete`
  - `archive_reply=成人资源归档成功`
  - `cleanup_reply=成人资源保留期清理完成`
  - `registry_statuses.after_archive=archived_present`
  - `registry_statuses.after_cleanup=archived_deleted`
- 脚本当前会先清理同 info hash 的旧任务，再用 `dispatch_download_dir=/downloads/complete` 投递，并在归档/清理阶段恢复 host `download_dir=/data/downloads/tr-bt`。

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

## qBittorrent（下载器辅助测试实例）

| 项目 | 值 |
|---|---|
| WSL 访问地址 | `http://127.0.0.1:18098` |
| Web API 基础路径 | `/api/v2` |
| 登录方式 | 当前 `2026-04-24` 本机 probe 已确认 `/api/v2/torrents/info` 返回 `200 OK`；本地协议验证可留空用户名密码 |
| 下载目录（宿主机） | `/data/downloads/qb` |
| 下载目录（容器内） | `/data/downloads/qb` |
| incomplete 目录（宿主机） | `/data/downloads/incomplete-qb` |
| incomplete 目录（容器内） | `/data/downloads/incomplete-qb` |
| 配置目录（宿主机） | `/home/alex/projects/luminarr/docker/test/qbittorrent` |
| WebUI 端口约束 | `WEBUI_PORT=18098` 且 `ports: 18098:18098` |

健康检查：

```bash
curl -si http://127.0.0.1:18098/api/v2/torrents/info | grep -q "200 OK" && echo "qB up" || echo "qB down"
```

协议探针：

```bash
curl -si http://127.0.0.1:18098/api/v2/torrents/info
```

成人归档 smoke：

```bash
.venv/bin/python tmp_tests/verify_adult_archive_qb_real_smoke.py
```

说明：
- 这条脚本当前会用真实 qB Web API、真实 torrent/webseed 和真实 adult archive sidecar 验证“归档 -> 保留期清理”链路。
- 截至 `2026-04-26` 本轮 probe，脚本已通过，并把证据写到 `/tmp/luminarr_adult_archive_qb_real_smoke/evidence.json`。
- 当前通过态证据包含：
  - `archive_reply=成人资源归档成功`
  - `cleanup_reply=成人资源保留期清理完成`
  - `registry_statuses.after_archive=archived_present`
  - `registry_statuses.after_cleanup=archived_deleted`
  - `qb_removed=true`
  - `source_path_removed=true`
- 这轮通过前，宿主机上需要先把 `/data/downloads/qb` 与 `/data/downloads/incomplete-qb` 的 owner 修到 `1000:1000`；单纯 `chmod` 不足以让 qB 容器按 `PUID/PGID` 正常落盘。

---

## 路径约束（硬链接必须满足）

下载目录和库目录**必须在同一 WSL 文件系统**上：

```text
/data/downloads/tr
/data/downloads/tr-bt
/data/downloads/qb
/data/library/movies
```

验证是否同一文件系统：

```bash
stat -c "%d %n" /data/downloads/tr /data/downloads/tr-bt /data/downloads/qb /data/library/movies
```

这些路径的设备号相同，才表示 PT / BT Transmission 与 qBittorrent 到媒体库都满足硬链接前提。

当前 `2026-04-24` 本机 probe 中，上述四条路径设备号都为 `2096`。

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
# 当前第 5 段 dispatch_download_dir 供下载器 API 投递使用；第 4 段 download_dir 仍是宿主机导入/归档路径
DOWNLOADER_INSTANCES="tr-pt|transmission|http://127.0.0.1:19091|/data/downloads/tr|/downloads/complete;tr-bt|transmission|http://127.0.0.1:19092|/data/downloads/tr-bt|/downloads/complete"
PT_DOWNLOADER=tr-pt
BT_DOWNLOADER=tr-bt

# 可选：如果你要顺手验证 qBittorrent 协议
DOWNLOADER_INSTANCES="tr-pt|transmission|http://127.0.0.1:19091|/data/downloads/tr|/downloads/complete;tr-bt|transmission|http://127.0.0.1:19092|/data/downloads/tr-bt|/downloads/complete;qb-smoke|qbittorrent|http://127.0.0.1:18098|/data/downloads/qb"

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
- 如果你准备直接用 `set -a && . ./.env && set +a` 导入环境，`DOWNLOADER_INSTANCES` 这种带 `;` 的值要整个包进引号；否则 shell 会把后半段当成新命令执行
- `DOWNLOADER_INSTANCES` 当前可选第 5 段 `dispatch_download_dir`；如果是本地 Docker 里的 Transmission，这一段应写容器内路径 `/downloads/complete`
- 如果你要验证 PT / BT 双 Transmission 分流，当前代码要靠 `DOWNLOADER_INSTANCES + PT_DOWNLOADER + BT_DOWNLOADER` 明确绑定；只填 `TRANSMISSION_BASE_URL` 时，两条链都会落回默认 Transmission
- 如果你要验证 qBittorrent 协议，当前测试栈的 `qb-smoke` 实例可以直接写进 `DOWNLOADER_INSTANCES`；截至 `2026-04-24` 本机 probe，`18098/api/v2/torrents/info` 已返回 `200 OK`
- 当前代码读取的是 `LIBRARY_TARGET_DIR`，不是 `LIBRARY_MOVIES_PATH`
- 当前测试栈 Transmission 关闭了 RPC 认证，所以用户名和密码可留空

---

## Codex 使用规范

1. 执行涉及 `import_to_library` / `refresh_media_server` / `add_to_downloader` 的端到端验证前，必须先做健康检查。
2. 如果健康检查失败，不要继续执行，先让用户启动测试栈。
3. 后续联调默认把 `PT Transmission(http://127.0.0.1:19091)`、`BT Transmission(http://127.0.0.1:19092)`、`qBittorrent(http://127.0.0.1:18098)` 和 `Emby(http://127.0.0.1:18096)` 视为固定地址；但每轮可达性仍要以当轮探针为准，不要直接沿用旧结论。
4. 不要把测试栈真实凭据硬编码进仓库代码，始终从本地 config / `.env` 读取。
5. 测试完成后，Transmission 中的测试任务和 Emby 中的测试媒体条目可以手动清理，不要求仓库代码自动清理。
