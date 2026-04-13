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
- 环境就绪快照：2026-04-13 当前 shell、提权 shell 和 Windows 环境变量仍没有直接加载 `TELEGRAM_BOT_TOKEN` / `PROWLARR_BASE_URL` / `PROWLARR_API_KEY` / `TRANSMISSION_BASE_URL` / `EMBY_BASE_URL` / `EMBY_API_KEY` / `FEISHU_*` / `WECOM_*`；但仓库根目录已经有可直接 `make run` 的 `.env`，其中 `TELEGRAM_BOT_TOKEN` / `PROWLARR_BASE_URL` / `PROWLARR_API_KEY` / `TRANSMISSION_BASE_URL` / `EMBY_BASE_URL` / `EMBY_API_KEY` / `TMDB_API_KEY` / `FANART_API_KEY` 已就位，`/home/alex/luminarr-test` 下没有额外的 Luminarr `.env`；Feishu / WeCom 三元组仍缺，当前也没有运行中的 Luminarr 进程；`logs/` 里仍没有窗口期 `[cleanup 私聊 smoke]` 行，`data/luminarr.db` 的最新记录也还停在 2026-04-02，所以当前仓库内没有可回填的窗口期真实私聊 smoke 证据。
- `.env` 取值归一化快照：`sync-cleanup-doc-snapshots` 现在会先去掉仓库 `.env` 值首尾成对的单/双引号，再参与 `telegram_bot_api` 和 `env_readiness` 判断，避免 `"token"` 这类配置被误当成带引号字面量。
- 当前 shell env 值归一化快照：`sync-cleanup-doc-snapshots` 现在也会先去掉当前 shell 环境变量值首尾成对的单/双引号，避免当前会话里的 `\"token\"` 直接盖过后面的 `.env` / Windows env 真值。
- Windows env 读取归一化快照：`sync-cleanup-doc-snapshots` 现在会按大小写不敏感读取 `cmd.exe /c set` 输出里的键名，避免 `telegram_bot_token=...` 这类 Windows 环境变量被误写成缺失。
- Windows env 值归一化快照：`sync-cleanup-doc-snapshots` 现在也会先去掉 `cmd.exe /c set` 输出值首尾成对的单/双引号，避免 `\"token\"` 这类 Windows 环境变量继续被误当成带引号字面量。
- docs command display 同步快照：`sync-cleanup-doc-snapshots` 现在写回 `env readiness snapshot` / `telegram bot api snapshot` 时，也会同步展示“当前 shell / .env / Windows env 值去首尾引号、Windows env 键名大小写不敏感、env readiness 里的 Windows 值级判定”这组当前实现真相，避免状态页命令示例和总述快照落后于真实逻辑。
- docs command display 转义快照：`sync-cleanup-doc-snapshots` 现在写回 `env_readiness` / `telegram_bot_api` 命令示例时，也会稳定保留 `strip('\"\'')` 这类去引号转义片段，避免状态页把可执行命令写坏成错误引号组合。
- telegram bot api command display 快照：`sync-cleanup-doc-snapshots` 现在写回 `telegram bot api snapshot` 时，也会展示“当前 shell / .env / Windows env 值去首尾引号 + Windows env 键名大小写不敏感”这整条 token 解析真相，避免状态页仍显示旧的 token 读取路径。
- env readiness command display 快照：`sync-cleanup-doc-snapshots` 现在写回 `env readiness snapshot` 时，也会显式展示“当前 shell 环境变量值先去首尾引号再判空”这条实现真相，避免状态页仍显示旧的 shell 判空逻辑。
- env readiness Windows 判定快照：`sync-cleanup-doc-snapshots` 现在写回 `env readiness snapshot` 时，也会把 Windows env 这段展示成“大小写不敏感键名 + 去首尾引号后的非空值才算 set”，避免状态页把空值环境变量误读成已就绪。
- env readiness 缺口展示快照：`sync-cleanup-doc-snapshots` 现在在 local runtime/import 已就绪但四渠道 smoke 环境未齐时，会直接写出 `missing channels: ...`，避免状态页只留 `four-channel cleanup smoke env incomplete` 这种笼统 blocker。
- env readiness personal WeChat 边界快照：`sync-cleanup-doc-snapshots` 现在也会显式写出 `personal_wechat login state not checked`，提醒当前 env readiness 不会把 personal WeChat 本地登录态误记成已验证。
- Telegram Bot API 就绪快照：2026-04-13 提权 `getMe` 已确认当前仓库 `.env` 里的 `TELEGRAM_BOT_TOKEN` 可用；当前 Telegram 渠道剩余缺口不是 bot 凭据不可用，而是窗口内真实私聊 cleanup 输入和回复证据仍未落仓库。
- Telegram Bot API 错误分类快照：`sync-cleanup-doc-snapshots` 现在也把 Telegram `getMe` 的 401/403 稳定归类为 `telegram bot api rejected token`，不再和网络不可达混写成 `unreachable`，避免 cleanup 窗口快照误判凭据状态。
- 窗口活性快照：已到最早可结束日期，待补退出条件
- 当前状态快照：进行中
- 当前结论快照：验证窗口仍在进行中；截至 2026-04-13，已到最早可结束日期 2026-04-12，但四个渠道真实私聊 cleanup smoke 记录仍待补，当前仓库内也还没有可回填的窗口期真实 smoke 证据，暂未满足退出条件。
- 聚合 smoke gate 快照：已把 `mixed-case` 英文 `cleanup / cleanup inspect` 输入、四渠道 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查` 的 service-not-ready observability，以及 `chat-scoped task_ref` 命中 `job_event` 关联查询失败、缺结构化 `source_path/target_path` 两类 identity retention / rejection guidance 补进四渠道 cleanup smoke。
- 单渠道入口快照：`tests/test_telegram_bot.py -k cleanup` 现在也单独锁住 Telegram cleanup mixed-case 英文 `cleanup / cleanup inspect` 路由，避免 Telegram 胶水层大小写回退只能从聚合 smoke 间接发现。
- Telegram cleanup smoke 日志快照：Telegram 入口现在会在 cleanup / cleanup inspect 文本成功回出后，按统一协议追加绿色 `[cleanup 私聊 smoke]` 日志，并带上 `date/channel/action/query/reply_head`，方便后续把真实私聊证据回填到窗口台账。
- Telegram chat-scoped shortcut 门禁快照：现在也单独锁住 `cleanup inspect cleanup-shortcut` 经过 Telegram handler 后仍能解析出真实 `task_id/task_hash`，避免主入口把 `cleanup-shortcut` 当成普通字符串传给 cleanup service。
- verification docs gate 快照：`mixed-case english cleanup protocol`、`NEXT_STEP current-window sync`、`correlation-query-failure observability`、`source-type-unsupported blocked-log observability`、`cleanup-service-not-ready fix-hint observability`、`success-event-append-failure observability`、`delete-failure observability`、`correlation-missing unresolved-identity blank display`、`correlation-missing inspect identity resolution`、`correlation-missing rejection guidance`、`post-cleanup cleanup inspect confirmation`、`source-type-unsupported rejection guidance`、`chat-scoped task_ref post-cleanup cleanup inspect confirmation`、`chat-scoped task_ref target-missing cleanup inspect follow-up guidance`、`chat-scoped task_ref source-missing cleanup inspect follow-up guidance`、`chat-scoped task_ref source-type-unsupported cleanup inspect follow-up guidance`、`chat-scoped task_ref guard-rejected cleanup inspect follow-up guidance`、`chat-scoped task_ref target-missing rejection guidance`、`chat-scoped task_ref source-missing rejection guidance`、`chat-scoped task_ref source-type-unsupported rejection guidance`、`chat-scoped task_ref guard-rejected rejection guidance` 已纳入窗口台账门禁，并继续卡住“窗口已完成后，`当前 cleanup 协议观察` 不得残留窗口日期阻塞或真实私聊 smoke 待补文案”，同时也校验 `test-cleanup-window` 顺序、`docs/GETTING_STARTED.md` 无 `make` 备用命令与三段 Makefile gate 保持一致、`sync-cleanup-doc-snapshots` 的 `Makefile` / `docs/GETTING_STARTED.md` 入口一致性、四个单渠道 `cleanup-shortcut` 门禁继续写在 `docs/NEXT_STEP.md` / `docs/STATUS.md`、`README.md` 入口退出条件显式覆盖 `verification docs gate`，以及 README 十条 cleanup 本地 gate 入口继续明确“不能替代四渠道真实私聊 smoke 证据”，避免 mixed-case-english-protocol / next-step-current-window-sync / query-failure / blocked-log / cleanup-service-not-ready-fix-hint / event-append-failure / delete-failure / unresolved-identity / inspect-identity-resolution / rejection-guidance / post-cleanup-confirmation / source-type-unsupported-guidance / chat-scoped-post-cleanup-confirmation / chat-scoped-target-missing-follow-up / chat-scoped-source-missing-follow-up / chat-scoped-source-type-follow-up / chat-scoped-guard-rejected-follow-up / chat-scoped-target-missing-rejection-guidance / chat-scoped-source-missing-rejection-guidance / chat-scoped-source-type-rejection-guidance / chat-scoped-guard-rejected-rejection-guidance 可观测性命名从台账里漂走，也避免窗口收口后台账还保留进行中文案或入口退出条件漂移。
- 验证快照维护快照：仓库里现在有 `make sync-cleanup-doc-snapshots` / `.venv/bin/python -m app.maintenance.cleanup_verification_docs ...`，会顺序执行固定验证命令，并把 `docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 的固定快照行连同环境就绪、Telegram Bot API 就绪、仓库内真实 smoke 证据快照一起改到最新结果，减少 cleanup 窗口期间手工抄写验证结果的漂移。
- 仓库证据快照能力快照：`local_smoke_evidence` 现在在命中窗口期 `[cleanup 私聊 smoke]` 日志时会直接带出 `found channels + missing channels`，四渠道齐全后会改成 `all channels covered`，没命中时也会显式列出缺失渠道；当前结果是 `no in-window cleanup smoke evidence in repo; missing channels: telegram,personal_wechat,feishu,wecom`，说明四个渠道的窗口内仓库证据都还没落下。
- 仓库证据日期聚合快照：cleanup 文档同步工具现在也会按渠道保留“窗口内最近一次真实 smoke 日期”，后续要把日志证据接到 `Channel progress` 表时不需要重新解析一遍原始日志。
- Channel progress 同步快照：`docs/CLEANUP_VERIFICATION_WINDOW.md` 里的四渠道进度表现在也会由同步工具按固定顺序自动重写；由于当前仓库仍无窗口内真实 smoke 证据，表格状态继续保持四个 `待验证`。
- Channel progress 截断保护快照：同步工具现在在重写四渠道进度表时也会保留 `Verification evidence`、`PT 做种 guardrail 评估` 和 `Update rule` 后续章节，不会再把窗口台账截断成只剩表格。
- Channel progress 整链路门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也直接跑最小 `sync_documents()` 回写样例，锁住真实文档同步路径在重写进度表后仍保留 `Verification evidence`、`PT 做种 guardrail 评估` 和 `Update rule` 标题。
- Channel progress 固定顺序门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也直接锁住 `sync_documents()` 在日志乱序时仍按 Telegram / personal WeChat / Feishu / WeCom 的固定顺序输出完成行，避免窗口台账顺序随日志抖动。
- Channel progress 最近日期门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也直接锁住 `sync_documents()` 在同一渠道命中多条窗口期真实 smoke 日志时会把该渠道更新为最近绝对日期，避免已完成渠道回填旧日期。
- Channel progress 待验证锚点门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也直接锁住 `sync_documents()` 在只有部分渠道完成时仍保留其他渠道的 `待验证`、`-` 和窗口开始日锚点备注，避免窗口台账把剩余缺口写成空白或漂移文案。
- Channel progress 文档顺序门禁快照：`tests/test_cleanup_verification_window_doc.py` 现在也直接校验窗口台账里的四渠道行顺序固定为 Telegram / personal WeChat / Feishu / WeCom，避免手工编辑文档时绕过同步器顺序保护。
- cleanup 私聊 smoke 日志协议快照：仓库里现在也有统一的 `app/bot/cleanup_smoke_logging.py`，先把 `date/channel/action/query/reply_head` 这组最小日志格式锁住；`app/main.py` 启动后也会把真实私聊 cleanup smoke 自动追加到 `logs/cleanup-private-chat-smoke.log`，让 `sync-cleanup-doc-snapshots` 能直接从仓库日志回填窗口证据，避免窗口证据重新分叉或只留在 stdout。
- shared runtime cleanup service-not-ready 快照：`6 passed, 10 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k service_not_ready`）
- Telegram cleanup service-not-ready 快照：`8 passed, 74 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "cleanup and service_not_ready"`）
- personal WeChat cleanup service-not-ready 快照：`12 passed, 21 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_personal_wechat_text.py -k service_not_ready`）
- Feishu cleanup service-not-ready 快照：`8 passed, 26 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k service_not_ready`）
- Feishu webhook cleanup 快照：`14 passed, 24 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k "webhook_http_request and cleanup"`）
- WeCom cleanup service-not-ready 快照：`6 passed, 24 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_wecom_adapter.py -k service_not_ready`）
- shared runtime service-not-ready 门禁快照：现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免共用入口只对英文带任务引用路径保留日志可观测性。
- personal WeChat 单渠道 service-not-ready 门禁快照：现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免 personal WeChat 只对带任务引用的英文 cleanup 命令保留日志可观测性。
- personal WeChat cleanup smoke 日志快照：personal WeChat 私聊入口现在也会在 cleanup / cleanup inspect 文本成功回出后，复用同一条绿色 `[cleanup 私聊 smoke]` 日志协议，并继续带上 `date/channel/action/query/reply_head`，方便后续窗口台账按同一规则识别这个渠道的真实 smoke 证据。
- personal WeChat chat-scoped shortcut 门禁快照：现在也单独锁住 `cleanup inspect cleanup-shortcut` 经过 personal WeChat 文本入口后仍能解析出真实 `task_id/task_hash`，避免这个私聊入口把 `cleanup-shortcut` 当成普通字符串传给 cleanup service。
- Feishu 私聊 service-not-ready 门禁快照：现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免 Feishu 私聊入口只对英文带任务引用路径保留日志可观测性。
- Feishu cleanup smoke 日志快照：Feishu 私聊入口现在也会在 cleanup / cleanup inspect 文本成功回出后，复用同一条绿色 `[cleanup 私聊 smoke]` 日志协议，并继续带上 `date/channel/action/query/reply_head`，方便后续窗口台账按同一规则识别这个渠道的真实 smoke 证据。
- Feishu 私聊 chat-scoped shortcut 门禁快照：现在也单独锁住 `cleanup inspect cleanup-shortcut` 经过 Feishu adapter 后仍能解析出真实 `task_id/task_hash`，避免这个渠道把 `cleanup-shortcut` 当成普通字符串传给 cleanup service。
- Feishu webhook service-not-ready 门禁快照：现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免 Feishu 加密 HTTP 入口只对英文带任务引用路径保留日志可观测性。
- WeCom 私聊 service-not-ready 门禁快照：现在也单独锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查`，避免 WeCom 私聊入口只对英文带任务引用路径保留日志可观测性。
- WeCom cleanup smoke 日志快照：WeCom 私聊入口现在也会在 cleanup / cleanup inspect 文本成功回出后，复用同一条绿色 `[cleanup 私聊 smoke]` 日志协议，并继续带上 `date/channel/action/query/reply_head`，方便后续窗口台账按同一规则识别这个渠道的真实 smoke 证据。
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
- 2026-04-13 当前 shell、提权 shell 和 Windows 环境变量仍没有直接加载 `.env` 或等价凭据；但仓库根目录已经有可直接启动 Telegram + downloader/import 基线的 `.env`，`/home/alex/luminarr-test` 下没有额外的 Luminarr `.env`，Feishu / WeCom 三元组仍缺，当前也没有运行中的 Luminarr 进程，所以今天还不能从这个 shell 直接补齐四渠道真实私聊 smoke。
- 2026-04-13 本地仓库内也没有可回填的窗口期真实 smoke 证据：`logs/` 下还没有 2026-04-05 到 2026-04-12 的 `[cleanup 私聊 smoke]` 日志行，`data/luminarr.db` 的 `jobs` / `job_event` / `telegram_updates` 最新时间仍停在 2026-04-02，所以当前四渠道待验证状态不是漏记，而是仓库里确实还缺真实渠道证据。
- 2026-04-13 `curl` 已确认 Transmission 返回 `409 Conflict + X-Transmission-Session-Id`、Emby `/System/Info/Public` 正常返回 JSON，`stat -c "%d %n" /data/downloads/tr /data/library/movies` 也确认两条路径仍在同一设备上；当前剩余环境 blocker 还包括 Docker socket 访问仍被拒绝，且 sandbox 下本地随机端口监听会返回 `Operation not permitted`，所以 Feishu / WeCom 两条 webhook server HTTP 测试在全量 pytest 中会 skip。

## Latest verification

- tests：2026-04-13，`811 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）
- four-channel cleanup smoke tests：`376 passed`（2026-04-13，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- cleanup service tests：2026-04-13，`38 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`）
- focused cleanup tests：`526 passed, 91 deselected`（2026-04-13，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- cleanup verification docs gate：`384 passed`（2026-04-13，`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`）
- focused config truth tests：`4 passed, 17 deselected`（2026-04-13，`.venv/bin/python -m pytest -q tests/test_config.py -k "requires_token or requires_transmission_base_url or defaults_role_binding_to_first_instance or reads_tmdb_settings"`）
- make run env-file guard tests：`2 passed`（2026-04-13，`.venv/bin/python -m pytest -q tests/test_makefile.py`）
- shared runtime cleanup service-not-ready tests：`6 passed, 10 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k service_not_ready`）
- Telegram cleanup service-not-ready tests：`8 passed, 74 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "cleanup and service_not_ready"`）
- personal WeChat cleanup service-not-ready tests：`12 passed, 21 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_personal_wechat_text.py -k service_not_ready`）
- Feishu cleanup service-not-ready tests：`8 passed, 26 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k service_not_ready`）
- Feishu webhook cleanup tests：`14 passed, 24 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k "webhook_http_request and cleanup"`）
- WeCom cleanup service-not-ready tests：`6 passed, 24 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_wecom_adapter.py -k service_not_ready`）
- personal WeChat cleanup tests：`16 passed, 5 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_personal_wechat_text.py -k cleanup`）
- Feishu cleanup tests：`18 passed, 12 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k cleanup`）
- WeCom cleanup tests：`18 passed, 8 deselected`（2026-04-11，`.venv/bin/python -m pytest -q tests/test_wecom_adapter.py -k cleanup`）
- local test stack endpoint health checks：`passed (TR up / Emby up)`（2026-04-13，`curl -si http://127.0.0.1:19091/transmission/rpc`；`curl -s http://127.0.0.1:18096/System/Info/Public`）
- local test stack path device check：`passed (same device)`（2026-04-13，`stat -c "%d %n" /data/downloads/tr /data/library/movies`）
- env readiness snapshot：`local runtime/import env ready; four-channel cleanup smoke env incomplete; missing channels: feishu,wecom; personal_wechat login state not checked`（2026-04-13，`bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "import os; keys=[\"TELEGRAM_BOT_TOKEN\",\"PROWLARR_BASE_URL\",\"PROWLARR_API_KEY\",\"TRANSMISSION_BASE_URL\",\"EMBY_BASE_URL\",\"EMBY_API_KEY\",\"FEISHU_APP_ID\",\"FEISHU_APP_SECRET\",\"FEISHU_ENCRYPT_KEY\",\"WECOM_TOKEN\",\"WECOM_ENCODING_AES_KEY\",\"WECOM_RECEIVE_ID\"]; print(\"\\n\".join(f\"{k}=\" + (\"set\" if os.getenv(k,\"\").strip().strip('\"\'') else \"missing\") for k in keys))"' ; python3 -c "import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; rows=dict(line.split('=', 1) for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if '=' in line); lookup={key.lower(): value.strip().strip('\"\'') for key, value in rows.items()}; print('\\n'.join(f'{k}=' + ('set' if lookup.get(k.lower(), '') else 'missing') for k in keys))" ; python3 -c "from pathlib import Path; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; data={}; env_path=Path('.env'); text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); data.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); print('\\n'.join(f'{k}=' + ('set' if data.get(k, '').strip() else 'missing') for k in keys))"`）
- telegram bot api snapshot：`telegram bot api ready`（2026-04-13，`python3 -c "import json, os, subprocess, urllib.request; from pathlib import Path; token=os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip('\"\''); env_path=Path('.env'); env_map={}; text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); env_map.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); token=token or env_map.get('TELEGRAM_BOT_TOKEN','').strip(); token=token or next((line.partition('=')[2].strip().strip('\"\'') for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if line.partition('=')[0].strip().lower() == 'telegram_bot_token'), ''); print('telegram bot token missing' if not token else ('telegram bot api ready' if json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=5)).get('ok') else 'telegram bot api rejected token'))"`）
- local smoke evidence snapshot：`no in-window cleanup smoke evidence in repo; missing channels: telegram,personal_wechat,feishu,wecom`（2026-04-13，`sqlite3 -header -column data/luminarr.db "select max(created_at) as max_created_at from jobs; select max(created_at) as max_created_at from job_event; select max(created_at) as max_created_at, count(*) as rows from telegram_updates;" ; rg -n "\[cleanup 私聊 smoke\]" logs`）
- cleanup 补证窗口快照：`sync-cleanup-doc-snapshots` 现在在窗口仍进行中时，会继续接受开始日期之后、当前快照日期之前的真实 smoke 日志，不再把 `最早可结束日期` 误当成后续补证硬截止线。
- cleanup 窗口规则同步快照：`docs/CLEANUP_VERIFICATION_WINDOW.md` 的 `Update rule` 现在也明确写出“进行中窗口的补证上界跟随当前结论快照日期”，避免台账文字和 docs sync 行为继续分叉。
- runtime process snapshot：`no luminarr process running`（2026-04-13，`python3 -c "from pathlib import Path; proc_root=Path('/proc'); matches=[]; pid_dirs=sorted((path for path in proc_root.iterdir() if path.is_dir() and path.name.isdigit()), key=lambda path: int(path.name)); for pid_dir in pid_dirs:  cmdline_path=pid_dir/'cmdline';  raw=cmdline_path.read_bytes() if cmdline_path.exists() else b'';  tokens=[token.decode('utf-8', errors='ignore') for token in raw.split(b'\\0') if token];  if tokens and 'python' in Path(tokens[0]).name and any(tokens[index] == '-m' and tokens[index + 1] == 'app.main' for index in range(len(tokens) - 1)):   matches.append(f'{pid_dir.name} ' + ' '.join(tokens)); print('\\n'.join(matches))"`）
- Telegram-only bring-up 快照：2026-04-13 提权启动 `.venv/bin/python -m app.main` 后，当前进程已进入运行态；缺少 BT 下载器角色绑定时会打印 `[BT 订阅后台扫描未启动]` 红色警告，但不会阻断最小 Telegram 入口启动。
- compile check：2026-04-13，`passed`（`python3 -m compileall app tests`）
- docs consistency check：2026-04-13，`passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`）
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
