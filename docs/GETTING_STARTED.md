# docs/GETTING_STARTED.md (v4)

> 目的：让一个不会写代码、但能用命令行的人，也能把仓库在本机跑起来并完成第一次验证。

## 1. 你需要先准备什么

- Debian / Ubuntu / WSL 环境
- `python3`
- `make`（可选；没有也能直接跑下面的一行命令）
- `docker` / `docker compose`（可选；想走容器启动时需要）
- 一份可用的 `.env`
- 当前最少要能访问：
  - Telegram Bot
  - Prowlarr
  - Transmission 或 qBittorrent
- 如果要跑真实 import / refresh：
  - Transmission 本地测试栈
  - Emby 本地测试栈

如果你要补**当前 cleanup 验证窗口**里的“四渠道真实私聊 smoke”退出条件，还要额外满足：

- `.env` 里至少有可用的 `TELEGRAM_BOT_TOKEN`、`FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_ENCRYPT_KEY`、`WECOM_TOKEN`、`WECOM_ENCODING_AES_KEY`、`WECOM_RECEIVE_ID`
- personal WeChat 需要本地已有可用登录态；它不靠 `.env` 三元组启动
- 只跑 `pytest` 只能证明 shared runtime 协议没回退，不能替代四渠道真实私聊 smoke 证据

本地测试栈端点见 `docs/TEST_ENV.md`。

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

如果你只想让应用先跑起来并做最小本地测试，至少填这些：

- `TELEGRAM_BOT_TOKEN`
- `PROWLARR_BASE_URL`
- `PROWLARR_API_KEY`
- `TRANSMISSION_BASE_URL`

说明：

- 当前 `TELEGRAM_BOT_TOKEN` 是启动硬必填，不是“只在你要用 Telegram 时才需要”
- 如果你在 WSL 里启动，但 Telegram / TMDB / Fanart / OpenAI / BT 外站 这类公网请求不能直连，可以额外填写 `OUTBOUND_PROXY_URL`
- `OUTBOUND_PROXY_URL` 当前支持 `http://...`、`https://...`、`socks5://...`；例如 `http://192.168.2.110:7890`
- 这条代理当前只给 Telegram 和公网 HTTP client 使用；Transmission / Emby / Prowlarr 这类本地或内网地址继续直连
- 当前 `TMDB_API_KEY` 不是启动硬必填；不填时只会关闭 TMDB 相关增强能力
- 当前 `DOWNLOADER_INSTANCES` 不能替代 `TRANSMISSION_BASE_URL`；它只是多实例路由补充配置
- 如果你配置了 `DOWNLOADER_INSTANCES` 但没填 `PT_DOWNLOADER` / `BT_DOWNLOADER`，当前代码会默认取第一个实例名

如果你还要跑 import / refresh 联调，再补这些：

- `LIBRARY_TARGET_DIR`
- `EMBY_BASE_URL`
- `EMBY_API_KEY`

如果你还要用 Telegram 私聊入口，再补：

- `TELEGRAM_BOT_TOKEN`

如果你现在的本机状态就是：

- Transmission 已在 `http://127.0.0.1:19091` 跑着
- Emby 已在 `http://127.0.0.1:18096` 跑着
- 你只想先打通 Telegram 私聊最小链路

那 `.env` 最小组合就是：

- `TELEGRAM_BOT_TOKEN`
- `PROWLARR_BASE_URL`
- `PROWLARR_API_KEY`
- `TRANSMISSION_BASE_URL=http://127.0.0.1:19091`

如果这台 WSL 机器不能直接连 Telegram Bot API，但你宿主机或旁路由已经提供了 HTTP / SOCKS5 代理，再额外补：

- `OUTBOUND_PROXY_URL=http://192.168.2.110:7890`

如果你还想顺手验证 import / refresh，再在上面补：

- `LIBRARY_TARGET_DIR=/data/library/movies`
- `EMBY_BASE_URL=http://127.0.0.1:18096`
- `EMBY_API_KEY`

如果你要补 Feishu / WeCom 真实私聊 smoke，再补各自 webhook 三元组。
这两组三元组都必须“要么都空，要么都填”，不能只填一部分。
personal WeChat 继续依赖本地登录态，不靠 `.env` 专用键启动。
补 WeCom 真实私聊 smoke 前，可以先在 `app.main` 已运行的前提下，用 `curl -si http://127.0.0.1:18889/wecom/callback` 确认本地 callback 已经监听；这条地址来自当前本地已验证 `.env`，不是 `.env.example` 里的默认端口/路径。当前无校验参数时返回 `400 missing echostr` 属于入口已就绪，不等于真实私聊 smoke 已完成；如果直接拿到 `connection refused`，先回头确认应用是否真的已启动。若你本地改过 `WECOM_WEBHOOK_HOST` / `WECOM_WEBHOOK_PORT` / `WECOM_WEBHOOK_PATH`，探针地址也要跟着当前 `.env` 改，不要死抄这里的样例。

如果你要跑 Feishu，但不想额外折腾公网 HTTPS 回调，可以把：

- `FEISHU_INBOUND_MODE=long_connection`

这样 Feishu 入站会改走官方 SDK 长连接；这时 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 仍然必填，但 `FEISHU_ENCRYPT_KEY` 可以留空。

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
- `make test-cleanup-smoke`：跑四渠道 cleanup smoke gate
- `make test-cleanup-service-not-ready`：跑 cleanup service-not-ready 专项 smoke
- `make test-cleanup-telegram`：跑 Telegram cleanup 入口回归
- `make test-cleanup-personal-wechat`：跑 personal WeChat cleanup 入口回归
- `make test-cleanup-feishu`：跑 Feishu cleanup 入口回归
- `make test-cleanup-wecom`：跑 WeCom cleanup 入口回归
- `make test-cleanup-feishu-webhook`：跑 Feishu webhook cleanup 入口回归
- `make test-cleanup`：跑 cleanup 聚合回归
- `make test-docs`：跑文档一致性 gate
- `make test-cleanup-docs-gate`：跑 cleanup verification docs gate
- `make test-cleanup-window`：连续跑当前 cleanup 验证窗口需要的 smoke gate、cleanup 聚合回归和 verification docs gate
- `make sync-cleanup-doc-snapshots`：顺序执行固定的 cleanup 验证命令，并把 `docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 里的固定快照行同步到最新结果；现在也会一起刷新环境就绪、Telegram Bot API 就绪、当前运行进程和仓库内真实 smoke 证据快照
- 应用通过 `make run` 或 `.venv/bin/python -m app.main` 启动后，真实私聊里的 `cleanup` / `cleanup inspect` 回复会自动把 `[cleanup 私聊 smoke]` 追加到 `logs/cleanup-private-chat-smoke.log`，`make sync-cleanup-doc-snapshots` 就靠这份日志识别窗口内真实 smoke 证据
- 没有 `make` 时，`make test-cleanup-service-not-ready` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py -k service_not_ready`
- 没有 `make` 时，`make test-cleanup-telegram` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k cleanup`
- 没有 `make` 时，`make test-cleanup-personal-wechat` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_personal_wechat_text.py -k cleanup`
- 没有 `make` 时，`make test-cleanup-feishu` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k cleanup`
- 没有 `make` 时，`make test-cleanup-wecom` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_wecom_adapter.py -k cleanup`
- 没有 `make` 时，`make test-cleanup-feishu-webhook` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k "webhook_http_request and cleanup"`
- 没有 `make` 时，`make test-cleanup` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`
- 没有 `make` 时，`make test-cleanup-docs-gate` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`
- 没有 `make` 时，`make test-cleanup-window` 的等价一行命令是：`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py && .venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup && .venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`
- 没有 `make` 时，`make sync-cleanup-doc-snapshots` 的等价一行命令是：`.venv/bin/python -m app.maintenance.cleanup_verification_docs full_suite cleanup_service smoke_gate focused_cleanup docs_gate focused_config makefile_env_guard compile_check docs_consistency env_readiness telegram_bot_api local_smoke_evidence runtime_process`
- `make compile`：跑 `compileall`
- `make run`：读取 `.env` 后启动应用
- `make docker-build`：构建镜像
- `make docker-up`：启动 compose
- `make docker-logs`：看容器日志

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

### 为什么 personal WeChat 没有 `.env` 配置项

因为当前 personal WeChat 入口主要依赖登录命令和本地运行态，不是靠一组固定 webhook 凭据启动。

## 9. 继续往下读

- 想理解“代码为什么这么分”：读 `docs/ARCHITECTURE.md`
- 想知道“当前正在做什么”：读 `docs/NEXT_STEP.md`
- 想知道“现在做到哪里”：先读 `docs/STATUS.md`
- 想看“当前主线详细闭环”：读 `docs/PERSISTENCE_CLOSURE_LOG.md`
- 想看“所有文档地图”：读 `docs/INDEX.md`
