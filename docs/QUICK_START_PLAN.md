# docs/QUICK_START_PLAN.md (v1)

> 目的：把 `docs/NEXT_STEP.md` 的 `After this step` "最小人类可用入口" 主线提前设计到位。
>
> **定位**：Luminarr 是自用项目，本文档面向**部署者**（你自己 + 可能的第二部署者），**不是**给最终用户看的。最终用户只管跟机器人对话。
>
> 上游决策：`docs/DECISIONS.md` D-001 / D-018 / D-019 / D-035。

## 1. 谁会读这份文档，谁不会

**会读：**
- 项目作者本人半年后想重新部署
- 作者的 1-2 个朋友想在自己家里自建一份
- 未来给作者接手维护的人

**假设**：读者懂命令行、懂 Docker、能读中文技术文档、能自己搭 Transmission / Emby / Prowlarr 和准备 API key。**不假设**他懂 Python / SQLite / Telegram Bot API 内部。

**不会读：**
- 最终通过私聊和 bot 交互的用户（他们只发"我想看 X"就够了，不需要部署知识）

所以这份文档**不需要**覆盖：
- 对 Docker / Linux / 命令行的入门教学
- 对 Telegram Bot / Feishu / WeCom 注册流程的完整手把手
- 多语言

需要覆盖：
- 从零到 10 分钟跑通的最短路径
- 半年后自己唤醒记忆的能力
- 部署时最容易踩的坑速查表

## 2. 预期交付物

本主线不一定要新增大文档，而是**整合 + 精简已有内容**：

| 文档 | 当前状态 | 本主线要做的 |
|---|---|---|
| `docs/GETTING_STARTED.md` | 已有约 300 行，覆盖 bring-up | 精简 §3 重复说明；§5 方案 B 已于 `7563c3c` 补齐 |
| `.env.example` | 模板文件 | 按"分组 + 每组注释"重构；每条 env 标清"必填 / 条件必填 / 可选" |
| `docs/DEPLOY_CHECKLIST.md`（**新文件**） | 不存在 | 一页部署前 checklist + 首次跑通 5 步脚本 + 半年后唤醒复盘 |

核心新增只有一份 `DEPLOY_CHECKLIST.md`，不搞大改造。

## 3. `DEPLOY_CHECKLIST.md` 的目标结构

```markdown
# Luminarr 部署 checklist (v1)

## Phase 0：外部依赖就绪（你准备）

- [ ] Docker / docker compose 已装好
- [ ] 一台能长期开机的机器（WSL / VPS / NAS 均可）
- [ ] Transmission 或 qBittorrent：已在某处跑着，RPC 地址记下
- [ ] Prowlarr：已跑着，API Key 准备好
- [ ] Emby：已跑着，API Key 准备好
- [ ] 注册账号拿 Key：
  - [ ] Telegram Bot Token（BotFather）
  - [ ] TMDB API Key（tmdb.org 开发者设置）
  - [ ] Fanart.tv API Key（可选）
- [ ] 下载盘和媒体库盘**在同一文件系统**（硬链接要求）

## Phase 1：拉仓库 + 配 `.env`

```bash
git clone <repo> luminarr
cd luminarr
cp .env.example .env
# 编辑 .env，按分组填
```

`.env` 关键分组（具体条目见 `.env.example`）：

1. **必填最小集**：`TELEGRAM_BOT_TOKEN`、`PROWLARR_BASE_URL`、`PROWLARR_API_KEY`、`TRANSMISSION_BASE_URL`
2. **入库和刷新**：`LIBRARY_TARGET_DIR`、`EMBY_BASE_URL`、`EMBY_API_KEY`
3. **TMDB 增强**（可选）：`TMDB_API_KEY`、`FANART_API_KEY`
4. **出站代理**（按需）：`OUTBOUND_PROXY_URL`
5. **Feishu 三元组**（按需）：`FEISHU_APP_ID` + `FEISHU_APP_SECRET` + `FEISHU_ENCRYPT_KEY`
6. **WeCom 三元组**（按需）：`WECOM_TOKEN` + `WECOM_ENCODING_AES_KEY` + `WECOM_RECEIVE_ID`

## Phase 2：容器网络自检

如果 Transmission / Emby / Prowlarr 在宿主机上跑，`.env` 里**不要**写 `http://127.0.0.1:...`；改成宿主机局域网 IP。详见 `docs/GETTING_STARTED.md §5`。

## Phase 3：首次启动 + 5 步冒烟

```bash
docker compose up -d
docker compose logs -f luminarr    # 确认没有红色 [错误]
```

在 Telegram 私聊里（或你选定的渠道）依次发：

1. `我想看 Dune 2021` → 期望：看到候选列表
2. `select 1` → 期望：看到审批提示
3. `confirm 1` → 期望：看到"已投递到下载器"
4. 等几分钟后发 `status 1` → 期望：看到下载进度
5. 下载完成后发 `import 1`（或等自动导入）→ 期望：看到"已入库"

任一步失败见 Phase 5 速查。

## Phase 4：personal WeChat 扫码（首次，可选）

... (如果用 personal WeChat) ...

## Phase 5：常见部署坑速查

| 症状 | 排查 | 指引 |
|---|---|---|
| 容器连不上 Transmission / Emby / Prowlarr | `.env` 写 `127.0.0.1` 了？ | 改宿主机 IP |
| 硬链接失败、一直进 copy-fallback | 下载盘和库盘不同分区？ | 挪到同分区，或接受 copy-fallback |
| Telegram 发不出消息 | 公网能通吗？ | 配 `OUTBOUND_PROXY_URL` |
| Feishu webhook 一直 403 | 签名错了 | 核对 `FEISHU_ENCRYPT_KEY` |
| personal WeChat 重启丢登录 | 登录态没持久化 | 设 `OPENCLAW_STATE_DIR=/app/state/openclaw` |
| SQLite locked | 多进程起了多个实例？ | 保证单实例（D-003） |

## Phase 6：半年后唤醒自己

- 应用在哪儿：`docker compose ps` / `docker inspect luminarr`
- 日志在哪儿：`./logs/trace.log`（关键节点）+ `docker compose logs luminarr`（全量）
- 数据在哪儿：`./data/luminarr.db`（SQLite）+ `./data/openclaw/`（personal WeChat 登录态）+ `$SHARED_MEDIA_ROOT`（媒体）
- 更新版本：`git pull && docker compose up -d --build`
- 备份最少三份：`./data/luminarr.db` + `.env` + `./data/openclaw/`
```

## 4. `.env.example` 重构方向

把现有 `.env.example` 按 §3 Phase 1 的 6 组重新排序，每组开头加一行说明：

```
# =============================================
# [1] 必填最小集（应用启动硬必填）
# =============================================
TELEGRAM_BOT_TOKEN=
PROWLARR_BASE_URL=
PROWLARR_API_KEY=
TRANSMISSION_BASE_URL=

# =============================================
# [2] 入库和刷新（要跑 import / refresh 时必填）
# =============================================
LIBRARY_TARGET_DIR=/data/library/movies
EMBY_BASE_URL=
EMBY_API_KEY=

...
```

## 5. 分阶段落地

- **Phase 1**：写 `docs/DEPLOY_CHECKLIST.md` 骨架（按 §3 结构填完整）。
- **Phase 2**：重构 `.env.example`（按 §4 分组）。
- **Phase 3**：精简 `docs/GETTING_STARTED.md`（删除和新 checklist 重复的内容；保留 bring-up 方案 A / B 的详细命令）。
- **Phase 4**：README §0 加一行指向 checklist：`想直接部署，看 docs/DEPLOY_CHECKLIST.md`。

## 6. 可测量退出条件（任一触发即停）

1. `docs/DEPLOY_CHECKLIST.md` 存在且覆盖 Phase 0-6 六个段，`.env.example` 已按分组重构，README §0 已加 checklist 指针。
2. 或 Phase 1-4 已完成 3 个，剩余是精调文案（停机规则）。
3. 或从 `git clone` 到 "Telegram 私聊能跑通" 走一遍，用时 ≤ 15 分钟且无阻塞（手工验证）。

## 7. 不做清单

- 不做"新手 tutorial"（读者懂命令行）
- 不做 Web UI / 安装向导
- 不做多语言（中文）
- 不做 Windows 原生部署（WSL 即可）
- 不做自动 env 生成脚本
- 不做云一键部署模板（Heroku / fly.io 等）
- 不做备份 / 监控 / 告警方案（那属于运维主线，目前不在范围）
