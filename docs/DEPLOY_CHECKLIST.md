# Luminarr 部署 checklist (v1)

> 目的：给部署者一页最短路径。你只需要用它确认“外部依赖备齐了没有、第一次怎么跑、失败先查哪里、半年后怎么把记忆找回来”。

## Phase 0：外部依赖就绪

- [ ] 一台能长期开机的机器已经准备好：WSL / Linux 主机 / VPS / NAS 均可
- [ ] `git`、`docker`、`docker compose` 已可用
- [ ] Prowlarr 已跑起来，并且 API Key 已记下
- [ ] Transmission 或 qBittorrent 至少有一个实例已跑起来，并且 RPC 地址已记下
- [ ] 如果要走导入和刷新链，Emby 已跑起来，并且 API Key 已记下
- [ ] Telegram Bot Token 已拿到
- [ ] 如果要补元数据增强，TMDB API Key 已拿到
- [ ] 如果要补 fanart，Fanart.tv API Key 已拿到
- [ ] 如果要补 Feishu / WeCom 真实私聊 smoke，对应三元组已经拿到
- [ ] 下载目录和媒体库目录在同一文件系统上；否则硬链接会失败并进入 copy-fallback 待确认

## Phase 1：拉仓库并准备 `.env`

```bash
git clone <repo> luminarr
```

```bash
cd luminarr
```

```bash
cp .env.example .env
```

然后按 `.env.example` 的分组填写。当前最常见的最小组合是：

- 启动硬必填：`TELEGRAM_BOT_TOKEN`、`PROWLARR_BASE_URL`、`PROWLARR_API_KEY`、`TRANSMISSION_BASE_URL`
- 导入和刷新：`LIBRARY_TARGET_DIR`、`EMBY_BASE_URL`、`EMBY_API_KEY`
- 出站代理：如果这台 WSL / Linux 机器不能直连 Telegram / TMDB / Fanart / BT 外站，再补 `OUTBOUND_PROXY_URL`
- 多下载器路由：只有你真的在用多个实例时，才补 `DOWNLOADER_INSTANCES`、`PT_DOWNLOADER`、`BT_DOWNLOADER`

## Phase 2：网络与路径自检

- 如果 Luminarr 走 Docker Compose，而 Transmission / Emby / Prowlarr 跑在宿主机上，`.env` 里不要继续写 `http://127.0.0.1:...`
- 容器内的 `127.0.0.1` 指容器自己，不是宿主机；优先改成宿主机局域网 IP，例如 `http://192.168.2.110:19091`
- `SHARED_MEDIA_ROOT`、下载目录、媒体库目录要能在下载器和 Luminarr 看到同一套物理路径；否则 hardlink / import / cleanup 语义会变掉
- 如果你只做本地 Python 运行，不走容器，当前仓库代码不会自动加载 `.env`；启动前必须先 `set -a && . ./.env && set +a`

## Phase 3：首次启动与 5 步冒烟

先装依赖：

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

本地 Python 运行：

```bash
set -a && . ./.env && set +a && .venv/bin/python -m app.main
```

或者用容器运行：

```bash
docker compose up -d
```

冒烟顺序固定为 5 步：

1. 在 Telegram 私聊里发 `我想看 Dune 2021`，期望看到候选列表
2. 发 `select 1`，期望看到下载审批提示
3. 发 `confirm 1`，期望看到“已投递到下载器”
4. 几分钟后发 `status 1`，期望看到下载进度
5. 下载完成后发 `import 1`，期望看到“已入库”；如果自动导入已完成，也可以直接看 Emby 是否刷新成功

## Phase 4：渠道补齐入口

- 只想先跑最小闭环：Telegram 就够了
- 要补 Feishu：默认走 webhook；如果不想折腾公网 HTTPS，可以把 `FEISHU_INBOUND_MODE=long_connection`
- 要补 WeCom：确认 `WECOM_TOKEN`、`WECOM_ENCODING_AES_KEY`、`WECOM_RECEIVE_ID` 三项要么都空、要么都填
- 要补 personal WeChat：先在本地 Python 运行里完成扫码登录，再考虑容器化；它依赖本地登录态，不靠 `.env` 里的 webhook 三元组启动

## Phase 5：常见部署坑速查

| 症状 | 先查什么 | 处理建议 |
| --- | --- | --- |
| 容器里连不上 Transmission / Emby / Prowlarr | `.env` 是否还写着 `127.0.0.1` | 改成宿主机局域网 IP 或 `host.docker.internal` |
| Telegram 搜索一直没回包 | 机器是否不能直连公网 | 补 `OUTBOUND_PROXY_URL` |
| `make run` 直接报环境文件缺失 | `.env` 是否真的存在 | 复制 `.env.example` 为 `.env`，或用 `ENV_FILE=/绝对路径/xxx.env make run` |
| 导入一直进 copy-fallback | 下载盘和媒体库盘是否同一文件系统 | 调整到同一文件系统，或接受显式 copy-fallback |
| Emby 不刷新 | `EMBY_BASE_URL` / `EMBY_API_KEY` 是否可达 | 先用本地测试栈地址做通路验证 |
| personal WeChat 重启后不可用 | 登录态目录是否持久化 | 先在本地 Python 运行完成登录，再挂载状态目录 |

## Phase 6：半年后唤醒自己

- 项目入口先读：`README.md` -> `docs/INDEX.md` -> `docs/GETTING_STARTED.md`
- 当前主线和退出条件：`docs/NEXT_STEP.md`
- 当前状态快照：`docs/STATUS.md`
- 当前 quick start 蓝图：`docs/QUICK_START_PLAN.md`
- 应用日志：`docker compose logs -f luminarr` 或 `logs/trace.log`
- 数据真相：`data/luminarr.db`
- 更新版本：`git pull` 后重新 `docker compose up -d --build`
- 最小备份集：`.env`、`data/luminarr.db`、personal WeChat 登录态目录
