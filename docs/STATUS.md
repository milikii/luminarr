# Current status (v200)

## Project position

Luminarr 当前是一个同时服务 **Telegram + personal WeChat + Feishu + WeCom** 四个私聊入口的垂直影视自动化 Harness。

当前固定主线：
- Telegram + personal WeChat + Feishu + WeCom（最小私聊文本基线）
- TMDB
- Prowlarr（当前主来源）+ 最小 BT WebSource（仅 BT 使用）
- Transmission + qBittorrent
- Emby
- SQLite
- Docker Compose
- 单实例 / 单进程 / 单机
- movie-first

## Knowledge entrypoints

- `README.md`：项目入口
- `docs/INDEX.md`：文档地图
- `docs/GETTING_STARTED.md`：从零到跑通
- `docs/ARCHITECTURE.md`：系统结构说明
- `.env.example`：配置模板
- `Makefile`：常用命令入口
- `Dockerfile` / `docker-compose.yml`：最小容器启动入口
- 详细 cleanup 窗口台账：`docs/CLEANUP_VERIFICATION_WINDOW.md`

## What is implemented now

- 控制层：
  - `shared private-chat text runtime`
  - Telegram / personal WeChat / Feishu / WeCom 四个正式私聊入口
  - `telegram_updates` 去重、`jobs` 执行所有权、approval timeout、confirm wake rebuild
  - cleanup service 未注入时，`cleanup` / `cleanup inspect` 现在也会打印红色中文 `[cleanup 服务未就绪]` 日志、`动作=cleanup/cleanup_inspect`、`查询=` 和 `[处理建议]` 修复提示
- 媒体主链：
  - `search -> select -> downloader approval -> confirm -> dispatch -> status`
  - `import approval -> confirm -> hardlink import`
  - copy fallback、completion-monitor、post-download auto import
  - cleanup 最小闭环：inspect / cleanup / discoverability / rejection guidance / success follow-up / failure observability / `chat-scoped task_ref`
  - `chat-scoped task_ref` 命中 jobs 但 import 关联缺失时，inspect / cleanup 会继续回显解析出的 `task_id/task_hash`
  - 普通 correlation-missing inspect 在没有真实解析结果时继续显示 `任务 ID/Hash: -`，不把用户原始输入伪装成真实身份
  - `chat-scoped task_ref` 已解析成功但 `job_event` 关联查询失败时，日志继续保留 resolved `lookup_task_ref/task_id/task_hash`
  - `chat-scoped task_ref` 命中旧 `import.succeeded` 但缺结构化 `source_path/target_path` 时，inspect / cleanup 继续回显 resolved identity
  - `chat-scoped task_ref` 执行 cleanup 删除失败时，`cleanup.failed` 事件和红色日志继续落到真实关联任务身份
  - `chat-scoped task_ref` cleanup 成功但 `cleanup.succeeded` 事件写入失败时，成功文本照常返回，日志继续保留真实关联任务身份
  - `chat-scoped task_ref` 命中 `source_type_unsupported` guardrail 时，阻断日志继续落到真实关联任务身份
  - metadata scraping、subtitle auto-translation、Emby refresh
- BT 主链：
  - PT / BT split、processing-path inquiry、BT classification、TMDB association
  - BT shared source adapter（`Prowlarr + WebSource`）
  - pure BT ranking、BT helper、`manage_bt_subscription`
- 其他：
  - `manage_watchlist` 手动持久化基线
  - 最小本地 Python / Docker Compose 启动入口

## Current focus

- 当前唯一主线仍然是 cleanup 四渠道验证窗口。
- 详细规则、退出条件、证据和渠道进度统一看 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- 入口文档快照：`README.md` 已同步 cleanup 窗口、personal WeChat / WeCom 回复边界、PT 做种风险、mixed-case 英文 cleanup 输入、`guard-rejected` rejection guidance，以及 `make test-cleanup-smoke` / `make test-cleanup-service-not-ready` / `make test-cleanup-telegram` / `make test-cleanup-personal-wechat` / `make test-cleanup-feishu` / `make test-cleanup-wecom` / `make test-cleanup-feishu-webhook` / `make test-cleanup` / `make test-cleanup-docs-gate` / `make test-cleanup-window` 十条本地 gate 入口和无 `make` 备用命令；`README.md` / `docs/GETTING_STARTED.md` 现在也显式补齐了 `test-cleanup-service-not-ready`、`test-cleanup-telegram`、`test-cleanup`、`test-cleanup-docs-gate`、`test-cleanup-window` 的等价一行 pytest 命令；`README.md` 快速启动入口也已经写清 `TELEGRAM_BOT_TOKEN`、`PROWLARR_BASE_URL`、`PROWLARR_API_KEY`、`TRANSMISSION_BASE_URL` 是硬必填，`TMDB_API_KEY` 可空，`DOWNLOADER_INSTANCES` 不能替代 `TRANSMISSION_BASE_URL`；`docs/GETTING_STARTED.md` 已额外写清“Telegram + 本地 Transmission/Emby 已启动”这条最小 `.env` 组合，并把 Feishu / WeCom 三元组 all-or-none 约束同步到当前配置真相；`.env.example` 也已按同一真相补齐中文说明；`tests/test_config.py` 相关配置回归和 docs gate 都已覆盖这些说明；`docs/TEST_ENV.md` 已同步测试栈 compose 文件真实位置；窗口细节继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- bring-up 入口快照：`Makefile` 的 `make run` 现在会先检查 `ENV_FILE` 指向的环境文件；缺失时打印红色中文 `[环境文件缺失]` 日志和 `[处理建议]`，并支持 `ENV_FILE=/绝对路径 make run`，避免当前工作区没有 `.env` 时直接掉进 shell 原始 `source` 报错。
- 知识入口快照：历史单体主文档 `Luminarr_v15.md` 已移除，当前只保留 `README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md` 这条正式入口，避免过期总纲继续和当前主线并行。
- 环境就绪快照：2026-04-12 当前 shell、提权 shell 和 Windows 环境变量都没有加载 `TELEGRAM_BOT_TOKEN` / `PROWLARR_BASE_URL` / `PROWLARR_API_KEY` / `TRANSMISSION_BASE_URL` / `EMBY_BASE_URL` / `EMBY_API_KEY` / `FEISHU_*` / `WECOM_*`；仓库根目录与 `/home/alex/luminarr-test` 也未发现可直接启动 Luminarr 的 `.env`；当前没有运行中的 Luminarr 进程；`data/luminarr.db` 与 `logs/` 里的最新记录仍停在 2026-04-02，所以当前仓库内没有可回填的窗口期真实私聊 smoke 证据。
- 窗口活性快照：已到最早可结束日期，待补退出条件
- 当前状态快照：进行中
- 当前结论快照：验证窗口仍在进行中；截至 2026-04-12，已到最早可结束日期 2026-04-12，但四个渠道真实私聊 cleanup smoke 记录仍待补，当前 shell / 仓库内也还没有可回填的窗口期真实 smoke 证据，暂未满足退出条件。
- 聚合 smoke gate 快照：已把 `mixed-case` 英文 `cleanup / cleanup inspect` 输入、四渠道 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查` 的 service-not-ready observability，以及 `chat-scoped task_ref` 命中 `job_event` 关联查询失败、缺结构化 `source_path/target_path` 两类 identity retention / rejection guidance 补进四渠道 cleanup smoke。
- 单渠道入口快照：`tests/test_telegram_bot.py -k cleanup` 现在也单独锁住 Telegram cleanup mixed-case 英文 `cleanup / cleanup inspect` 路由，避免 Telegram 胶水层大小写回退只能从聚合 smoke 间接发现。
- Telegram chat-scoped shortcut 门禁快照：现在也单独锁住 `cleanup inspect cleanup-shortcut` 经过 Telegram handler 后仍能解析出真实 `task_id/task_hash`，避免主入口把 `cleanup-shortcut` 当成普通字符串传给 cleanup service。
- verification docs gate 快照：`mixed-case english cleanup protocol`、`NEXT_STEP current-window sync`、`correlation-query-failure observability`、`source-type-unsupported blocked-log observability`、`cleanup-service-not-ready fix-hint observability`、`success-event-append-failure observability`、`delete-failure observability`、`correlation-missing unresolved-identity blank display`、`correlation-missing inspect identity resolution`、`correlation-missing rejection guidance`、`post-cleanup cleanup inspect confirmation`、`source-type-unsupported rejection guidance`、`chat-scoped task_ref post-cleanup cleanup inspect confirmation`、`chat-scoped task_ref target-missing cleanup inspect follow-up guidance`、`chat-scoped task_ref source-missing cleanup inspect follow-up guidance`、`chat-scoped task_ref source-type-unsupported cleanup inspect follow-up guidance`、`chat-scoped task_ref guard-rejected cleanup inspect follow-up guidance`、`chat-scoped task_ref target-missing rejection guidance`、`chat-scoped task_ref source-missing rejection guidance`、`chat-scoped task_ref source-type-unsupported rejection guidance`、`chat-scoped task_ref guard-rejected rejection guidance` 已纳入窗口台账门禁，并继续卡住“窗口已完成后，`当前 cleanup 协议观察` 不得残留窗口日期阻塞或真实私聊 smoke 待补文案”，同时也校验 `test-cleanup-window` 顺序、`docs/GETTING_STARTED.md` 无 `make` 备用命令与三段 Makefile gate 保持一致、`sync-cleanup-doc-snapshots` 的 `Makefile` / `docs/GETTING_STARTED.md` 入口一致性、四个单渠道 `cleanup-shortcut` 门禁继续写在 `docs/NEXT_STEP.md` / `docs/STATUS.md`、`README.md` 入口退出条件显式覆盖 `verification docs gate`，以及 README 十条 cleanup 本地 gate 入口继续明确“不能替代四渠道真实私聊 smoke 证据”，避免 mixed-case-english-protocol / next-step-current-window-sync / query-failure / blocked-log / cleanup-service-not-ready-fix-hint / event-append-failure / delete-failure / unresolved-identity / inspect-identity-resolution / rejection-guidance / post-cleanup-confirmation / source-type-unsupported-guidance / chat-scoped-post-cleanup-confirmation / chat-scoped-target-missing-follow-up / chat-scoped-source-missing-follow-up / chat-scoped-source-type-follow-up / chat-scoped-guard-rejected-follow-up / chat-scoped-target-missing-rejection-guidance / chat-scoped-source-missing-rejection-guidance / chat-scoped-source-type-rejection-guidance / chat-scoped-guard-rejected-rejection-guidance 可观测性命名从台账里漂走，也避免窗口收口后台账还保留进行中文案或入口退出条件漂移。
- 验证快照维护快照：仓库里现在有 `make sync-cleanup-doc-snapshots` / `.venv/bin/python -m app.maintenance.cleanup_verification_docs ...`，会顺序执行固定验证命令，并把 `docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 的固定快照行连同环境就绪、仓库内真实 smoke 证据快照一起改到最新结果，减少 cleanup 窗口期间手工抄写验证结果的漂移。
- shared runtime cleanup service-not-ready 快照：`6 passed, 10 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k service_not_ready`）
- Telegram cleanup service-not-ready 快照：`8 passed, 74 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "cleanup and service_not_ready"`）
- personal WeChat cleanup service-not-ready 快照：`12 passed, 21 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_personal_wechat_text.py -k service_not_ready`）
- Feishu cleanup service-not-ready 快照：`8 passed, 26 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k service_not_ready`）
- Feishu webhook cleanup 快照：`14 passed, 24 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k "webhook_http_request and cleanup"`）
- WeCom cleanup service-not-ready 快照：`6 passed, 24 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_wecom_adapter.py -k service_not_ready`）
- shared runtime service-not-ready 门禁快照：现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免共用入口只对英文带任务引用路径保留日志可观测性。
- personal WeChat 单渠道 service-not-ready 门禁快照：现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免 personal WeChat 只对带任务引用的英文 cleanup 命令保留日志可观测性。
- personal WeChat chat-scoped shortcut 门禁快照：现在也单独锁住 `cleanup inspect cleanup-shortcut` 经过 personal WeChat 文本入口后仍能解析出真实 `task_id/task_hash`，避免这个私聊入口把 `cleanup-shortcut` 当成普通字符串传给 cleanup service。
- Feishu 私聊 service-not-ready 门禁快照：现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免 Feishu 私聊入口只对英文带任务引用路径保留日志可观测性。
- Feishu 私聊 chat-scoped shortcut 门禁快照：现在也单独锁住 `cleanup inspect cleanup-shortcut` 经过 Feishu adapter 后仍能解析出真实 `task_id/task_hash`，避免这个渠道把 `cleanup-shortcut` 当成普通字符串传给 cleanup service。
- Feishu webhook service-not-ready 门禁快照：现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免 Feishu 加密 HTTP 入口只对英文带任务引用路径保留日志可观测性。
- WeCom 私聊 service-not-ready 门禁快照：现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免 WeCom 私聊入口只对英文带任务引用路径保留日志可观测性。
- WeCom callback chat-scoped shortcut 门禁快照：现在也单独锁住 `cleanup inspect cleanup-shortcut` 经过 WeCom 加密 callback 入口后仍能解析出真实 `task_id/task_hash`，避免这个加密入站链路把 `cleanup-shortcut` 当成普通字符串传给 cleanup service。
- 四渠道聚合 service-not-ready 门禁快照：`tests/test_cleanup_cross_channel_smoke.py -k service_not_ready` 现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免跨渠道聚合 smoke 只剩英文带任务引用路径。
- 当前四个渠道真实私聊 smoke 快照（与窗口台账同步）：

| 渠道 | 状态 | 最近一次日期 |
| --- | --- | --- |
| Telegram | 待验证 | - |
| personal WeChat | 待验证 | - |
| Feishu | 待验证 | - |
| WeCom | 待验证 | - |

## Main risks and gaps

- `series / anime` 独立名称解析还没实现；当前最稳的是 movie-first。
- 当前“给别人用”的体验还偏工程向：私聊返回仍缺更美观的图片/信息卡片/字符排版。
- 当前虽然已经有最小 `Dockerfile` / `docker-compose.yml`，但还没有把 Transmission / Emby / Prowlarr 整套依赖一起内置到主 compose。
- 四个渠道都在真用，最大的维护风险是渠道适配层和 shared runtime 漂移，导致同一协议在四处长出不同分支。
- `shared private-chat runtime` 入口当前仍通过 `app/bot/private_chat_runtime.py -> app/bot/telegram_bot.py.handle_private_chat_query_text` 反向依赖 Telegram；大多数文本路径虽然已经可以在无 Telegram update 的前提下直跑，但 `微信登录` 仍直接依赖 Telegram 的二维码/文本回传能力。这条结构债已记录为 cleanup 窗口后的最小抽离项：把 shared runtime 入口从 `telegram_bot.py` 独立出来，并把 Telegram-only 媒资回传收口成显式注入能力，不在当前 cleanup 验证窗口内展开。
- personal WeChat 仍然仅限单账号私聊文本，每次回复依赖最新消息里的 `context_token`；一旦用户长时间不发言旧 token 会过期，当前没有可靠的 personal WeChat 主动推送闭环；登录成功后仍需下次启动才能开始轮询。
- Feishu / WeCom 当前只支持最小私聊文本，不支持群聊、图片、卡片、按钮回调；WeCom 也还没有主动发消息客户端。
- cleanup inspect / execution 当前只对带结构化 `source_path + target_path` 的导入任务可用；更早历史任务仍需人工甄别。
- PT 做种 guardrail 评估已记录到 `docs/CLEANUP_VERIFICATION_WINDOW.md`；当前 cleanup guardrail 还没读取下载器 seeding 状态，`pt_min_seed_hours` 也未进入 cleanup 阻断判断，因此删源前仍无法确认 PT 任务是否仍在做种。
- completion truth 仍主要依赖当前 runtime 观察，不是完整独立后台轮询平台。
- metadata scraping、subtitle auto-translation（当前仅 `.srt`）、Emby refresh 失败时不会回滚 import success；缺配置时会显式失败。
- BT shared source adapter、BT external web-source、pure BT ranking、`btsub` 选源都已可用，但还不是共享确定性评分器。
- 当前主线只支持 Emby；Jellyfin / Plex 仍是后续扩展，不在 cleanup 窗口这一步混入。
- 通用 plugin / skill / MCP 平台化仍然继续后置，不是当前收口目标。
- 2026-04-12 当前 shell、提权 shell 和 Windows 环境变量都没有加载 `.env` 或等价凭据；`TELEGRAM_BOT_TOKEN` / `PROWLARR_BASE_URL` / `PROWLARR_API_KEY` / `TRANSMISSION_BASE_URL` / `EMBY_BASE_URL` / `EMBY_API_KEY` / `FEISHU_*` / `WECOM_*` 仍是缺失状态，仓库根目录与 `/home/alex/luminarr-test` 也未发现可直接启动 Luminarr 的 `.env`，所以今天还不能从这个 shell 直接启动任一渠道去补真实私聊 smoke。
- 2026-04-12 本地仓库内也没有可回填的窗口期真实 smoke 证据：`data/luminarr.db` 的 `jobs` / `job_event` / `telegram_updates` 最新时间仍停在 2026-04-02，`logs/` 下也没有 2026-04-05 到 2026-04-12 的 Luminarr 运行日志，所以当前四渠道待验证状态不是漏记，而是仓库里确实还缺真实渠道证据。
- 2026-04-12 提权 `curl` 已确认 Transmission 返回 `409 Conflict + X-Transmission-Session-Id`、Emby `/System/Info/Public` 正常返回 JSON，`stat -c "%d %n" /data/downloads/tr /data/library/movies` 也确认两条路径仍在同一设备上；当前剩余环境 blocker 还包括 Docker socket / `sudo docker ps` 仍需要密码，无法从当前 shell 继续补容器列表快照。

## Latest verification

- tests：2026-04-12，`794 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）
- four-channel cleanup smoke tests：`376 passed`（2026-04-12，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- cleanup service tests：2026-04-12，`38 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`）
- focused cleanup tests：`526 passed, 91 deselected`（2026-04-12，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- cleanup verification docs gate：`384 passed`（2026-04-12，`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`）
- focused config truth tests：`4 passed, 17 deselected`（2026-04-12，`.venv/bin/python -m pytest -q tests/test_config.py -k "requires_token or requires_transmission_base_url or defaults_role_binding_to_first_instance or reads_tmdb_settings"`）
- make run env-file guard tests：`2 passed`（2026-04-12，`.venv/bin/python -m pytest -q tests/test_makefile.py`）
- shared runtime cleanup service-not-ready tests：`6 passed, 10 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k service_not_ready`）
- Telegram cleanup service-not-ready tests：`8 passed, 74 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "cleanup and service_not_ready"`）
- personal WeChat cleanup service-not-ready tests：`12 passed, 21 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_personal_wechat_text.py -k service_not_ready`）
- Feishu cleanup service-not-ready tests：`8 passed, 26 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k service_not_ready`）
- Feishu webhook cleanup tests：`14 passed, 24 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k "webhook_http_request and cleanup"`）
- WeCom cleanup service-not-ready tests：`6 passed, 24 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_wecom_adapter.py -k service_not_ready`）
- personal WeChat cleanup tests：`16 passed, 5 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_personal_wechat_text.py -k cleanup`）
- Feishu cleanup tests：`18 passed, 12 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k cleanup`）
- WeCom cleanup tests：`18 passed, 8 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_wecom_adapter.py -k cleanup`）
- local test stack endpoint health checks：`passed (TR up / Emby up)`（2026-04-12，`curl -si http://127.0.0.1:19091/transmission/rpc`；`curl -s http://127.0.0.1:18096/System/Info/Public`）
- local test stack path device check：`passed (same device)`（2026-04-12，`stat -c "%d %n" /data/downloads/tr /data/library/movies`）
- current shell env readiness check：`missing required channel/runtime env`（2026-04-12，`bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "import os; keys=[\"TELEGRAM_BOT_TOKEN\",\"PROWLARR_BASE_URL\",\"PROWLARR_API_KEY\",\"TRANSMISSION_BASE_URL\",\"EMBY_BASE_URL\",\"EMBY_API_KEY\",\"FEISHU_APP_ID\",\"FEISHU_APP_SECRET\",\"FEISHU_ENCRYPT_KEY\",\"WECOM_TOKEN\",\"WECOM_ENCODING_AES_KEY\",\"WECOM_RECEIVE_ID\"]; print(\"\\n\".join(f\"{k}=\" + (\"set\" if os.getenv(k) else \"missing\") for k in keys))"' ; python3 -c "import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; out=subprocess.run(['cmd.exe','/c','set'], capture_output=True, text=True).stdout.lower(); print('\\n'.join(f'{k}=' + ('set' if f'{k.lower()}=' in out else 'missing') for k in keys))"`）
- local smoke evidence snapshot：`no in-window evidence in repo`（2026-04-12，`sqlite3 -header -column data/luminarr.db "select max(created_at) as max_created_at from jobs; select max(created_at) as max_created_at from job_event; select max(created_at) as max_created_at, count(*) as rows from telegram_updates;" ; find logs -maxdepth 1 -type f -printf '%f\n' | sort`）
- compile check：2026-04-12，`passed`（`python3 -m compileall app tests`）
- docs consistency check：2026-04-12，`passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`）
- cleanup service-not-ready smoke tests：`24 passed, 352 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py -k service_not_ready`）
- telegram cleanup tests：`16 passed, 64 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k cleanup`）
- manual verification：
  - downloader/library cleanup execution baseline passed（`.venv/bin/python tmp_tests/verify_cleanup_execution_baseline.py`）
  - qBittorrent protocol baseline passed
  - BT subscription baseline passed
  - BT subscription scheduler-tick baseline passed
  - BT subscription deterministic candidate-selection baseline passed
  - original magnet processing-path inquiry baseline passed
  - pure BT single-item ranking baseline passed
  - BT external web-source baseline passed
  - BT WebSource richer metadata extraction baseline passed
  - BT-only read-only helper baseline passed
