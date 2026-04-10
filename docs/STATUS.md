# Current status (v181)

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
  - cleanup service 未注入时，shared runtime 现在也会打印红色中文 `[cleanup 服务未就绪]` 日志、`动作=` 和 `[处理建议]` 修复提示
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
- 入口文档快照：`README.md` 已同步 cleanup 窗口、personal WeChat / WeCom 回复边界、PT 做种风险、mixed-case 英文 cleanup 输入、`guard-rejected` rejection guidance，以及 `make test-cleanup-window` / `make test-cleanup-smoke` 两条本地 gate 入口和无 `make` 备用命令；`docs/GETTING_STARTED.md` 已补当前 cleanup 窗口真实私聊 smoke 需要 `.env` 四渠道凭据和 personal WeChat 登录态，并把测试栈启动命令同步到仓库内 `docker-compose.test.yml`；`.env.example` 已改成中文详细注释并标出最少必填变量；`docs/TEST_ENV.md` 已同步测试栈 compose 文件真实位置；窗口细节继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- 知识入口快照：历史单体主文档 `Luminarr_v15.md` 已移除，当前只保留 `README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md` 这条正式入口，避免过期总纲继续和当前主线并行。
- 窗口活性快照：未到最早可结束日期
- 当前状态快照：进行中
- 当前结论快照：验证窗口仍在进行中；截至 2026-04-11，尚未到最早可结束日期 2026-04-12，四个渠道真实私聊 cleanup smoke 记录仍待补，暂未满足退出条件。
- 聚合 smoke gate 快照：已把 `mixed-case` 英文 `cleanup / cleanup inspect` 输入，以及 `chat-scoped task_ref` 命中 `job_event` 关联查询失败、缺结构化 `source_path/target_path` 两类 identity retention / rejection guidance 补进四渠道 cleanup smoke。
- verification docs gate 快照：`mixed-case english cleanup protocol`、`NEXT_STEP current-window sync`、`correlation-query-failure observability`、`source-type-unsupported blocked-log observability`、`success-event-append-failure observability`、`delete-failure observability`、`correlation-missing unresolved-identity blank display`、`correlation-missing inspect identity resolution`、`correlation-missing rejection guidance`、`post-cleanup cleanup inspect confirmation`、`source-type-unsupported rejection guidance`、`chat-scoped task_ref post-cleanup cleanup inspect confirmation`、`chat-scoped task_ref target-missing cleanup inspect follow-up guidance`、`chat-scoped task_ref source-missing cleanup inspect follow-up guidance`、`chat-scoped task_ref source-type-unsupported cleanup inspect follow-up guidance`、`chat-scoped task_ref guard-rejected cleanup inspect follow-up guidance`、`chat-scoped task_ref target-missing rejection guidance`、`chat-scoped task_ref source-missing rejection guidance`、`chat-scoped task_ref source-type-unsupported rejection guidance`、`chat-scoped task_ref guard-rejected rejection guidance` 已纳入窗口台账门禁，避免 mixed-case-english-protocol / next-step-current-window-sync / query-failure / blocked-log / event-append-failure / delete-failure / unresolved-identity / inspect-identity-resolution / rejection-guidance / post-cleanup-confirmation / source-type-unsupported-guidance / chat-scoped-post-cleanup-confirmation / chat-scoped-target-missing-follow-up / chat-scoped-source-missing-follow-up / chat-scoped-source-type-follow-up / chat-scoped-guard-rejected-follow-up / chat-scoped-target-missing-rejection-guidance / chat-scoped-source-missing-rejection-guidance / chat-scoped-source-type-rejection-guidance / chat-scoped-guard-rejected-rejection-guidance 可观测性命名从台账里漂走。
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
- personal WeChat 仍然仅限单账号私聊文本，每次回复依赖最新消息里的 `context_token`；一旦用户长时间不发言旧 token 会过期，当前没有可靠的 personal WeChat 主动推送闭环；登录成功后仍需下次启动才能开始轮询。
- Feishu / WeCom 当前只支持最小私聊文本，不支持群聊、图片、卡片、按钮回调；WeCom 也还没有主动发消息客户端。
- cleanup inspect / execution 当前只对带结构化 `source_path + target_path` 的导入任务可用；更早历史任务仍需人工甄别。
- PT 做种 guardrail 评估已记录到 `docs/CLEANUP_VERIFICATION_WINDOW.md`；当前 cleanup guardrail 还没读取下载器 seeding 状态，`pt_min_seed_hours` 也未进入 cleanup 阻断判断，因此删源前仍无法确认 PT 任务是否仍在做种。
- completion truth 仍主要依赖当前 runtime 观察，不是完整独立后台轮询平台。
- metadata scraping、subtitle auto-translation（当前仅 `.srt`）、Emby refresh 失败时不会回滚 import success；缺配置时会显式失败。
- BT shared source adapter、BT external web-source、pure BT ranking、`btsub` 选源都已可用，但还不是共享确定性评分器。
- 当前主线只支持 Emby；Jellyfin / Plex 仍是后续扩展，不在 cleanup 窗口这一步混入。
- 通用 plugin / skill / MCP 平台化仍然继续后置，不是当前收口目标。
- 当前会话里 `docker compose -f /home/alex/projects/luminarr/docker-compose.test.yml up -d` 已确认命中文件，但 Docker API 访问仍被本机权限阻塞；在 `docker.sock` 权限或 `sudo` 密码问题解决前，无法替本机真正拉起 Transmission / Emby 测试栈。

## Latest verification

- tests：2026-04-11，`716 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）
- four-channel cleanup smoke tests：`352 passed`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- cleanup service tests：2026-04-11，`38 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`）
- focused cleanup tests：`460 passed, 91 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- cleanup verification docs gate：`360 passed`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`）
- compile check：2026-04-11，`passed`（`python3 -m compileall app tests`）
- docs consistency check：2026-04-11，`passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`）
- cleanup service-not-ready smoke tests：`4 passed, 352 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py -k service_not_ready`）
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
