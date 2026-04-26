# docs/GETTING_STARTED.md (v11)

> 目的：让一个不会写代码、但能用命令行的人，也能把仓库在本机跑起来并完成第一次验证。

开始前先看：

1. `docs/HUMAN_START_HERE.md`
2. `docs/STATUS.md`
3. `docs/OPERATOR_RUNBOOK.md`（如果你准备让 AI 连续推进）

## 1. 你需要先准备什么

- Debian / Ubuntu / WSL 环境
- `python3`
- `make`（可选；没有也能直接跑下面的一行命令）
- `docker` / `docker compose`（可选；想走容器启动时需要）
- 一份可用的 `.env`
- 如果要在**没有外挂字幕**时自动检查/提取视频内嵌字幕：
  `ffmpeg` 需要在当前 shell 的 `PATH` 里可执行；`ffprobe` 若存在会优先用于探测
- 当前最少要能访问：
  - Telegram Bot
  - Prowlarr
  - Transmission 或 qBittorrent
- 如果要跑真实 import / refresh：
  - Transmission / qBittorrent 本地测试栈
  - Emby 本地测试栈

如果你要补**当前 cleanup 验证窗口**里的“四渠道真实私聊 smoke”退出条件，还要额外满足：

- `.env` 里至少有可用的 `TELEGRAM_BOT_TOKEN`、`FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_ENCRYPT_KEY`、`WECOM_TOKEN`、`WECOM_ENCODING_AES_KEY`、`WECOM_RECEIVE_ID`
- personal WeChat 需要本地已有可用登录态；它不靠 `.env` 三元组启动
- 只跑 `pytest` 只能证明 shared runtime 协议没回退，不能替代四渠道真实私聊 smoke 证据

## 2. 第一次安装依赖

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## 3. 生成本地配置

`.env.example` 是模板，不是自动加载文件。

先复制：

```bash
cp .env.example .env
```

然后手动编辑 `.env`。

如果你只想走最短路径，不要在这里重复抄配置清单，直接看 `docs/DEPLOY_CHECKLIST.md` 的 `Phase 0-3`，再按 `.env.example` 分组填值。

这里只补几个最容易忘的约束：

- 当前启动硬必填仍是 `TELEGRAM_BOT_TOKEN`、`PROWLARR_BASE_URL`、`PROWLARR_API_KEY`、`TRANSMISSION_BASE_URL`
- 如果你还要跑 import / refresh 联调，再补 `LIBRARY_TARGET_DIR`、`EMBY_BASE_URL`、`EMBY_API_KEY`
- 如果你要跑当前成人 BT 专线，再补 `ADULT_ARCHIVE_DESTINATIONS`；统一保留窗口可选 `ADULT_BT_RETENTION_HOURS`，默认 `96`
- 如果 WSL 机器不能直连 Telegram / TMDB / Fanart / OpenAI / BT 外站，可以额外填写 `OUTBOUND_PROXY_URL`；Transmission / Emby / Prowlarr 这类本地或内网地址继续直连
- `DOWNLOADER_INSTANCES` 不能替代 `TRANSMISSION_BASE_URL`；如果你填了多实例但没填 `PT_DOWNLOADER` / `BT_DOWNLOADER`，当前代码会默认取第一个实例名
- direct magnet 入口当前仍会先问“观影 PT 链 / BT 成人链”；不会因为你配置了成人 BT 站点就自动走成人链
- Feishu / WeCom 三元组都必须“要么都空、要么都填”；personal WeChat 继续依赖本地登录态，不靠 `.env` 专用键启动

补 WeCom 真实私聊 smoke 前，可以先在 `app.main` 已运行的前提下，用 `curl -si http://127.0.0.1:18889/wecom/callback` 确认本地 callback 已经监听；这条地址来自当前本地已验证 `.env`，不是 `.env.example` 里的默认端口/路径。当前无校验参数时返回 `400 missing echostr` 属于入口已就绪，不等于真实私聊 smoke 已完成；如果直接拿到 `connection refused`，先回头确认应用是否真的已启动。若你本地改过 `WECOM_WEBHOOK_HOST` / `WECOM_WEBHOOK_PORT` / `WECOM_WEBHOOK_PATH`，探针地址也要跟着当前 `.env` 改，不要死抄这里的样例。

如果你要跑 Feishu，但不想额外折腾公网 HTTPS 回调，可以把 `FEISHU_INBOUND_MODE=long_connection`；这时 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 仍然必填，但 `FEISHU_ENCRYPT_KEY` 可以留空。

## 4. 启动本地测试栈（需要真实 import / refresh 时）

```bash
docker compose -f /home/alex/projects/luminarr/docker-compose.test.yml up -d
```

如果当前 WSL shell 直接报 `/var/run/docker.sock` `permission denied`，就在宿主机可用的 sudo 环境里改用：

```bash
sudo docker compose -f /home/alex/projects/luminarr/docker-compose.test.yml up -d
```

启动后先做健康检查：

```bash
curl -si http://127.0.0.1:19091/transmission/rpc | grep -q "X-Transmission-Session-Id" && curl -s http://127.0.0.1:18096/System/Info/Public | grep -q "ServerName"
```

说明：

- compose 文件在仓库里：`/home/alex/projects/luminarr/docker-compose.test.yml`
- Transmission / Emby 的配置目录仍然落在 `/home/alex/luminarr-test/config/...`
- 上面这条默认健康检查只覆盖当前保守首版发布矩阵里的 `19091 PT Transmission + 18096 Emby`
- 如果你还要额外确认 BT / qB 测试栈，再单独跑：`curl -si http://127.0.0.1:19092/transmission/rpc | grep -q "X-Transmission-Session-Id" && curl -si http://127.0.0.1:18098/api/v2/torrents/info >/dev/null`
- 截至 `2026-04-23` 本轮复验：`19091` RPC 返回 `409 + X-Transmission-Session-Id`，`18096` 返回 `ServerName`，`18098/api/v2/torrents/info` 返回 `200 OK`
- 同日当前 shell 下，`curl -si http://127.0.0.1:19092/transmission/rpc` 连续两次退出码 `7`；但 `ss -ltnp | rg ":19091|:19092|:18096|:18098"` 仍能看到 `19092` 在监听，所以 BT Transmission 要按当轮探针单独判断，不要直接沿用旧的“可达 / 不可达”结论
- qBittorrent 的固定测试配置落在仓库内 `docker/test/qbittorrent`；当前必须保持 `WEBUI_PORT=18098` 与 `18098:18098` 同步，不要回退成 `18098:8080`
- 如果这里只想跑纯单元测试，不做真实导入和刷新，可以先跳过这一步

## 5. 运行应用

### 方案 A：直接用本地 Python 运行

当前代码不会自动读取 `.env`，所以启动前要先把 `.env` 导入当前 shell：

```bash
set -a && . ./.env && set +a && .venv/bin/python -m app.main
```

如果你更习惯 Makefile，可以直接：

```bash
make run
```

说明：

- `make run` 现在会先检查 `ENV_FILE` 指向的环境文件是否存在
- 如果缺少 `.env`，会打印红色中文 `[环境文件缺失]` 和 `[处理建议]`
- 如果你想临时改用别的环境文件，可以直接运行：

```bash
ENV_FILE=/绝对路径/你的.env make run
```

### 方案 B：用 Docker Compose 运行

当前仓库已经提供：

- `Dockerfile`
- `docker-compose.yml`

容器启动前也需要先准备 `.env`。

默认读取 `.env`；如果你想临时改用别的文件，可以在命令前加：

```bash
LUMINARR_ENV_FILE=.env.example docker compose config
```

启动：

```bash
docker compose up -d
```

看日志：

```bash
docker compose logs -f luminarr
```

说明：

- 容器内应用代码目录是 `/app`
- Docker Compose 会强制把 `SQLITE_DB_PATH` 覆盖成 `/app/state/luminarr.db`，并落到宿主机 `./data`
- `SHARED_MEDIA_ROOT` 默认映射为宿主机 `/data` 到容器内 `/data`，用来保持 downloader / library 路径语义一致

**外部依赖：必须你自己先把这些备齐**

这个项目是自用部署，主 `docker-compose.yml` 只启 Luminarr 本体；Transmission / qBittorrent、Emby、Prowlarr 这三项**不**内置，请你自己在宿主机或其他机器上先跑起来。以下是部署前必须准备好的外部资源：

- **Transmission 或 qBittorrent**：至少一个能正常接受 RPC 投递的实例。如果用 Transmission，记下它的 RPC 地址（如 `http://宿主机 IP:19091`）和用户名密码（如果开了鉴权）。
- **Prowlarr**：当前 PT 主来源，需要一个能正常返回搜索结果的实例，以及一把可读取的 API Key。
- **Emby**：入库刷新目标，需要 `EMBY_BASE_URL` 和 `EMBY_API_KEY`。
- **TMDB API Key**：不填会关闭 metadata 增强，但不阻塞启动。
- **Fanart.tv API Key**：不填会关闭 fanart 抓取，不阻塞启动。
- **Telegram Bot Token**：当前是启动硬必填。Telegram 私聊入口无论你用不用都必须先有 token。
- **可选：OpenAI / 字幕翻译 Key**：仅影响 `.srt` 字幕自动翻译。
- **可选：`ffmpeg`（`ffprobe` 可选）**：只有在导入目标里没有外挂字幕、需要继续检查或提取视频内嵌字幕时才需要；当前代码默认直接从 `PATH` 调用，若缺少 `ffprobe` 会自动回退到 `ffmpeg -i` 做探测。
- **可选：Feishu / WeCom webhook 三元组**：只有你真的要用这两个渠道才填；当前都是"要么都空、要么都填"。

如果这台机器不能直连公网（Telegram / TMDB / Fanart / BT 外站），再加一条 `OUTBOUND_PROXY_URL=http://192.168.2.110:7890` 走宿主机或旁路由代理；Transmission / Emby / Prowlarr 这类本地地址仍然直连，不吃代理。

**容器网络：`127.0.0.1` 坑点**

如果你的 Transmission / Emby / Prowlarr 在**宿主机上直接跑**（不是在同一个 compose 里），`.env` 里**不要**继续写 `http://127.0.0.1:19091`。容器里的 `127.0.0.1` 指容器自身，不是宿主机。两种可选方案：

- **推荐**：用宿主机在局域网里的 IP，例如 `http://192.168.2.110:19091`。这个 IP 在 WSL2、纯 Linux Docker、Docker Desktop 环境下都能直接工作，而且和 `OUTBOUND_PROXY_URL` 的一贯写法一致。
- 也可以在 `docker-compose.yml` 的 `luminarr` service 下补一行 `extra_hosts: ["host.docker.internal:host-gateway"]`，然后 `.env` 里把地址改成 `http://host.docker.internal:19091`；Docker Desktop 下这条主机名默认已可用，纯 Linux Docker 则必须补 `host-gateway` 映射才生效。

如果你把依赖服务和 Luminarr 放进**同一个 compose** 里（本项目当前不推荐，见 `docs/DECISIONS.md` D-019），那就用 service 名而不是 IP：例如 `http://transmission:9091`。

Feishu / WeCom webhook 的入站端口（默认 `18095` / `18097`）已经在 compose 里映射出来；想让外部能回调，还要自己在路由器 / 反代上开好这两个端口的公网入口。

**硬链接 / `SHARED_MEDIA_ROOT` 具体是什么意思**

媒体入库当前默认走**硬链接**（跨文件系统会进显式 `copy-fallback pending`，走人工确认）。硬链接要求"同一个文件系统上的同一个目录视图"，所以：

- 下载器容器（Transmission）看到的下载目录、Luminarr 容器看到的下载目录，**必须映射到宿主机的同一个物理路径**。
- 例如宿主机用 `/data/downloads` 存下载、`/data/library` 存媒体库，两者都在同一块盘上：
  - Transmission 容器里 `/downloads/complete` → 宿主机 `/data/downloads/tr`
  - Luminarr 容器里 `/data` → 宿主机 `/data`（当前 compose 默认已这么做）
  - Emby 容器里 `/data/library` → 宿主机 `/data/library`
- 这样 Luminarr 在容器里看到的 `/data/downloads/tr/xxx.mkv` 和宿主机上是同一个 inode，硬链接到 `/data/library/movies/xxx.mkv` 才能成功。

如果你把下载盘和入库盘放在**两块物理盘**上，硬链接会失败，系统会改走 copy-fallback 待确认——这是有意的 fail-closed，不是 bug。

**两个 compose 文件的职责不要搞混**

- `docker-compose.yml`：**部署本体**，只启 Luminarr。你想"让项目跑起来给自己用"就用这个。
- `docker-compose.test.yml`：**本地联调测试栈**，启 Transmission + BT Transmission + qBittorrent + Emby 四个容器；其中 `qBittorrent` 是下载器协议辅助实例，`Emby` 仍是当前真实 refresh 固定入口。**不要拿来做正式部署**——它的端口、配置路径、卷映射都是测试约定，不是给长期运行用的。

**personal WeChat 在容器里的限制**

- personal WeChat 依赖 `wechat-clawbot`，首次启动需要扫码登录。当前 `docker-compose.yml` 没有为 personal WeChat 单独处理 QR 交互。
- 如果你要在容器部署 personal WeChat，建议先在**本地 Python**（`make run` / `set -a && . ./.env && set +a && .venv/bin/python -m app.main`）里完成一次扫码登录，让 `wechat-clawbot` 的登录态文件落到磁盘；然后在 `docker-compose.yml` 里**把登录态目录也挂进容器**（当前默认没有这条挂载，需要你自己补）。
- 容器重启时 `context_token` 可能已失效，personal WeChat 主动推送会降级到 Telegram（这个降级路径由代码自己处理）。

## 6. 第一条人工验证怎么做

### Telegram 最小 smoke

1. 启动服务。
2. 在 Telegram 私聊里给 bot 发：

```bash
我想看 Dune 2021
```

3. 看到搜索结果返回，说明“消息进来 -> runtime -> 文本回去”已经通了。

### cleanup 相关回归

如果你想看当前 cleanup 文本协议是否还稳，直接跑：

```bash
make test-cleanup-smoke
```

如果你的环境没有 `make`，就直接跑：

```bash
.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py
```

## 7. 常用命令

仓库根目录已经提供 `Makefile`：

```bash
make help
```

最常用的是：

- `make test`：跑全量 pytest
- `make quality`：跑当前仓库级快速质量入口（compile + pyflakes + Makefile/docs gate）
- `make lint`：跑最小静态检查（当前为 `pyflakes app tests`）
- `make verify-mainline`：跑当前主线 focused 验证入口
- `make test-cleanup-smoke`：跑四渠道 cleanup smoke gate
- `make test-cleanup`：跑 cleanup 聚合回归
- `make test-docs`：跑文档一致性 gate
- `make test-cleanup-docs-gate`：跑 cleanup verification docs gate
- `make test-cleanup-window`：连续跑当前 cleanup 验证窗口需要的 smoke gate、cleanup 聚合回归和 verification docs gate
- `make sync-cleanup-doc-snapshots`：顺序执行固定的 cleanup 验证命令，并把 `docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 里的固定快照行同步到最新结果；现在也会一起刷新环境就绪、Telegram Bot API 就绪、当前运行进程和仓库内真实 smoke 证据快照
- 应用通过 `make run` 或 `.venv/bin/python -m app.main` 启动后，会把最小可追溯 trace 追加到 `logs/trace.log`；当前 trace 会覆盖 shared private-chat 入站/回包，以及下载/导入待确认与 confirm 执行关键节点
- 真实私聊里的 `cleanup` / `cleanup inspect` 回复也会继续把 `[cleanup 私聊 smoke]` 追加到 `logs/cleanup-private-chat-smoke.log`，`make sync-cleanup-doc-snapshots` 就靠这份日志识别窗口内真实 smoke 证据
- 没有 `make` 时，`make test-cleanup` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`
- 没有 `make` 时，`make test-cleanup-docs-gate` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`
- 没有 `make` 时，`make test-cleanup-window` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py && .venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup && .venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`
- 没有 `make` 时，`make sync-cleanup-doc-snapshots` 的等价一行命令是：`.venv/bin/python -m app.maintenance.cleanup_verification_docs full_suite cleanup_service smoke_gate focused_cleanup docs_gate focused_config makefile_env_guard compile_check docs_consistency env_readiness telegram_bot_api local_smoke_evidence runtime_process`
- 没有 `make` 时，`make quality` 的等价一行命令是：`python3 -m compileall app tests && .venv/bin/python -m pyflakes app tests && .venv/bin/python -m pytest -q tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py`
- 没有 `make` 时，`make lint` 的等价一行命令是：`.venv/bin/python -m pyflakes app tests`
- 没有 `make` 时，`make verify-mainline` 不再维护为一条超长等价一行命令；直接按 `Makefile` 里的 `verify-mainline-status-and-channels`、`verify-mainline-bt-paths`、`verify-mainline-execution-paths`、`verify-mainline-user-intents` 4 组顺序逐组执行即可。
- `make compile`：跑 `compileall`
- `make run`：读取 `.env` 后启动应用
- `make docker-build`：构建镜像
- `make docker-up`：启动 compose
- `make docker-logs`：看容器日志

跑完最小验证后，回到 `docs/STATUS.md` 看当前健康度，再决定要不要继续施工。

## 8. 常见问题

### `.env` 写了，但程序还是说缺配置

因为当前代码不会自动 `load_dotenv`。
你必须用：

```bash
set -a && . ./.env && set +a && .venv/bin/python -m app.main
```

或者：

```bash
make run
```

如果 `.env` 根本还没准备好，`make run` 会先打印 `[环境文件缺失]`，提醒你先复制 `.env.example` 或改用 `ENV_FILE=/绝对路径 make run`。

### 为什么 Feishu / WeCom 不配也能启动

因为这两个渠道当前是可选入口。
只要对应的三元组配置留空，启动时就不会挂 webhook server。

### 为什么 Docker Compose 里还要挂 `/data`

因为当前 cleanup / import / refresh 路径默认围绕 `/data/...` 组织。
如果容器内看不到和下载器、媒体库同一套共享路径，hardlink / import / cleanup 语义会变掉。

### 容器起来了但 Luminarr 说连不上 Transmission / Emby / Prowlarr

大概率是 `.env` 里还写的 `http://127.0.0.1:<port>`。容器里 `127.0.0.1` 指容器自身，不是宿主机。把这几个 URL 的 host 改成宿主机在局域网里的 IP（例如 `http://192.168.2.110:19091`）即可。更多细节见 §5 方案 B 里的 **容器网络：`127.0.0.1` 坑点** 段。

### 硬链接失败 / 一直进 copy-fallback 待确认

检查：
- Luminarr 容器看到的下载目录和 Transmission 容器看到的下载目录，是不是**宿主机的同一个物理路径**？
- 下载盘和入库盘是不是**同一个文件系统**？
- 两者有任何一条不满足，硬链接都会失败，系统会 fail-closed 走 copy-fallback 待确认——这是设计行为，不是 bug。具体映射约定见 §5 方案 B 的 **硬链接 / `SHARED_MEDIA_ROOT` 具体是什么意思** 段。

### 为什么 personal WeChat 没有 `.env` 配置项

因为当前 personal WeChat 入口主要依赖登录命令和本地运行态，不是靠一组固定 webhook 凭据启动。

## 9. 继续往下读

- 想理解“代码为什么这么分”：读 `docs/ARCHITECTURE.md`
- 想知道“当前正在做什么”：读 `docs/NEXT_STEP.md`
- 想知道“现在做到哪里”：先读 `docs/STATUS.md`
- 想看“最近完成了哪些闭环”：读 `docs/PERSISTENCE_CLOSURE_LOG.md`
- 想看“所有文档地图”：读 `docs/INDEX.md`
