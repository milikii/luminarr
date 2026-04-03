# docs/TEST_ENV.md — 本地集成测试栈配置

> 这份文件是 WSL Docker 本地测试栈的正式说明入口。
> 它记录端点、路径、健康检查和配置占位；不要把真实凭据提交到 Git。
> 真实用户名、密码、API Key、Library ID 应保存在本地 `.env` 或本地配置覆盖中。

---

## 测试栈位置

Docker Compose 文件：

```text
/srv/luminarr-test/docker-compose.yml
```

启动测试栈：

```bash
cd /srv/luminarr-test && docker compose up -d
```

停止测试栈：

```bash
cd /srv/luminarr-test && docker compose down
```

---

## Transmission（下载器测试实例）

| 项目 | 值 |
|---|---|
| WSL 访问地址 | `http://localhost:9091` |
| RPC 路径 | `/transmission/rpc` |
| 用户名 | `admin`（按本地实际填写） |
| 密码 | `（按本地实际填写）` |
| 下载目录（宿主机） | `/srv/luminarr-test/downloads/tr` |
| 下载目录（容器内） | `/data/downloads/tr` |
| incomplete 目录（宿主机） | `/srv/luminarr-test/downloads/incomplete` |

健康检查：

```bash
curl -s http://localhost:9091/transmission/rpc | grep -q "X-Transmission-Session-Id" && echo "TR up" || echo "TR down"
```

---

## Emby（媒体服务器测试实例）

| 项目 | 值 |
|---|---|
| WSL 访问地址 | `http://localhost:8096` |
| API Key | `（按本地实际填写，在 Emby 管理后台生成）` |
| 库路径（宿主机） | `/srv/luminarr-test/library/movies` |
| 库路径（容器内） | `/data/library/movies` |
| Library ID | `（按本地实际填写，首次启动后在 Emby 后台查看）` |

健康检查：

```bash
curl -s http://localhost:8096/System/Info/Public | grep -q "ServerName" && echo "Emby up" || echo "Emby down"
```

---

## 路径约束（硬链接必须满足）

下载目录和库目录**必须在同一 WSL 文件系统**上：

```text
/srv/luminarr-test/downloads/tr
/srv/luminarr-test/library/movies
```

验证是否同一文件系统：

```bash
stat -c "%d" /srv/luminarr-test/downloads/tr && stat -c "%d" /srv/luminarr-test/library/movies
```

两个数字相同，才表示硬链接可用。

---

## 对应的 app 配置（.env 或本地 config）

```env
# Transmission
TRANSMISSION_HOST=http://localhost:9091
TRANSMISSION_USER=admin
TRANSMISSION_PASS=（按本地实际填写）
TRANSMISSION_DOWNLOAD_DIR=/data/downloads/tr

# Emby
EMBY_BASE_URL=http://localhost:8096
EMBY_API_KEY=（按本地实际填写）
EMBY_LIBRARY_ID=（按本地实际填写）

# 本地库路径（宿主机视角，供 import hardlink 使用）
LIBRARY_MOVIES_PATH=/srv/luminarr-test/library/movies
```

---

## Codex 使用规范

1. 执行涉及 `import_to_library` / `refresh_media_server` / `add_to_downloader` 的端到端验证前，必须先做健康检查。
2. 如果健康检查失败，不要继续执行，先让用户启动测试栈。
3. 不要把测试栈真实凭据硬编码进仓库代码，始终从本地 config / `.env` 读取。
4. 测试完成后，Transmission 中的测试任务和 Emby 中的测试媒体条目可以手动清理，不要求仓库代码自动清理。
