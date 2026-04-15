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
  - `channel_identity` 空输入现在会 fail-closed 返回 `None`，不再把缺失渠道身份折叠成共享整数 `0`
  - 状态查询和导入源查询在查不到 `downloader_name` 时现在会直接停路返回 `None`，不再把空下载器名继续喂给默认 Transmission
  - 状态查询和导入源查询在 `downloader_name` 指向不存在实例时现在也会 fail-closed 返回 `None`，不再静默回退默认 Transmission
  - 下载器名 lookup 在 task/job 未命中或 payload 缺 `downloader_name` 时，现在也会打印红色中文 `[下载器路由未命中]` 日志和 `[处理建议]`
  - 下载器名 lookup 在 `downloader_name` 指向不存在实例时，现在也会打印红色中文 `[下载器实例不存在]` 日志和 `[处理建议]`
  - `add_to_downloader.has_pending_add()` 在 `jobs` 查询异常时，现在也会打印红色中文 `[下载待确认查询失败]` 日志和 `[处理建议]`，不再把 SQLite 查询异常静默吞成“没有待确认下载”
  - `add_to_downloader.cancel_pending_add()` 在 `jobs` 查询异常时，现在也会打印红色中文 `[下载取消查询失败]` 日志和 `[处理建议]`，不再把 SQLite 查询异常静默吞成“没有待取消下载”
  - `channel_identity` 空输入现在也会打印红色中文 `[渠道身份缺失]` 日志和 `[处理建议]`
  - cleanup service 未注入时，`cleanup` / `cleanup inspect` 现在也会打印红色中文 `[cleanup 服务未就绪]` 日志、`动作=cleanup/cleanup_inspect`、`查询=` 和 `[处理建议]` 修复提示
- 媒体主链：
  - `search -> select -> downloader approval -> confirm -> dispatch -> status`
  - `import approval -> confirm -> hardlink import`
  - `search_media` 在澄清态 `clear_pending()` 删除失败、`get_pending_query()` 读取失败时，现在也会打印红色中文 `[搜索澄清态清理失败]` / `[搜索澄清态读取失败]` 日志和 `[处理建议]`，不再静默吞掉 SQLite 删除/读取异常
  - copy fallback、completion-monitor、post-download auto import
  - `post_download_auto_import` 最小后台 tick 已接入应用启动/停止链，完成态 `download_monitor` 不再只能靠用户手动 `status` 才推进一次
  - `download_monitor` 的待完成下载列表现在已支持限流读取，便于后续独立后台轮询按批次推进下载完成观察
  - 待完成下载现在已有“单次轮询 helper”，会逐条复用现有 `GetDownloadStatusService` 状态观察链，而不是另起一套下载器查询逻辑
  - 独立下载完成轮询现在已接入应用启动/停止链，应用运行时会周期轮询待完成下载并复用现有状态观察链
  - 下载完成轮询 loop 抛异常时，现在也会打印红色中文 `[下载完成状态轮询失败]` 日志和 `[处理建议]`
  - 下载完成轮询启动接线现在改用 `GetDownloadStatusService` 的显式 `download_monitor_repo` 能力，不再直接依赖私有字段名
  - 下载完成轮询现在已经和 auto-import service 启动条件解耦；即使未注入 auto-import service，也能独立启动下载完成状态轮询
  - 下载完成轮询因缺少有效 `download_monitor_repo` 无法启动时，现在也会打印红色中文 `[下载完成状态轮询未启动]` 日志和 `[处理建议]`
  - 下载完成轮询 task 在停机 await 时若失败，现在也会打印红色中文 `[下载完成状态轮询停止失败]` 日志和 `[处理建议]`
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

- cleanup 四渠道验证窗口已完成；后续最小路径按 `docs/NEXT_STEP.md` 的 cleanup 后路线推进。
- 详细规则、退出条件、证据和渠道进度统一看 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- 入口文档快照：`README.md` 已同步 cleanup 窗口、personal WeChat / WeCom 回复边界、PT 做种风险、mixed-case 英文 cleanup 输入、`guard-rejected` rejection guidance，以及 `make test-cleanup-smoke` / `make test-cleanup-service-not-ready` / `make test-cleanup-telegram` / `make test-cleanup-personal-wechat` / `make test-cleanup-feishu` / `make test-cleanup-wecom` / `make test-cleanup-feishu-webhook` / `make test-cleanup` / `make test-cleanup-docs-gate` / `make test-cleanup-window` 十条本地 gate 入口和无 `make` 备用命令；`README.md` / `docs/GETTING_STARTED.md` 现在也显式补齐了 `test-cleanup-service-not-ready`、`test-cleanup-telegram`、`test-cleanup`、`test-cleanup-docs-gate`、`test-cleanup-window` 的等价一行 pytest 命令；`README.md` 快速启动入口也已经写清 `TELEGRAM_BOT_TOKEN`、`PROWLARR_BASE_URL`、`PROWLARR_API_KEY`、`TRANSMISSION_BASE_URL` 是硬必填，`TMDB_API_KEY` 可空，`DOWNLOADER_INSTANCES` 不能替代 `TRANSMISSION_BASE_URL`；`docs/GETTING_STARTED.md` 已额外写清“Telegram + 本地 Transmission/Emby 已启动”这条最小 `.env` 组合，并把 Feishu / WeCom 三元组 all-or-none 约束同步到当前配置真相；`.env.example` 也已按同一真相补齐中文说明；`tests/test_config.py` 相关配置回归和 docs gate 都已覆盖这些说明；`docs/TEST_ENV.md` 已同步测试栈 compose 文件真实位置；窗口细节继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- 代理配置快照：当前配置已经支持 `OUTBOUND_PROXY_URL`，Telegram / TMDB / Fanart / BT 外站 / 字幕翻译会复用这条出站代理；Transmission / Emby / Prowlarr 继续走本地直连。`tests/test_config.py`、`tests/test_tmdb_client.py`、`tests/test_fanart_client.py`、`tests/test_bt_sources.py`、`tests/test_subtitle_translator.py`、`tests/test_telegram_bot.py` 已覆盖配置解析，以及 Telegram / TMDB / Fanart / WebSource / 字幕翻译的代理透传。
- Feishu 入站模式快照：当前配置已支持 `FEISHU_INBOUND_MODE=long_connection`；此模式下只要求 `FEISHU_APP_ID + FEISHU_APP_SECRET`，不再强制 `FEISHU_ENCRYPT_KEY`。Feishu 长连接收到私聊事件后仍复用 shared runtime 文本链。
- personal WeChat 二维码载体快照：当前 `微信登录` 回传已从 SVG 文件收口为 PNG 图片，Telegram 发送侧会按图片路径走 `send_photo`，避免用户拿到 SVG 后还要额外找查看器。
- 本地测试栈快照：`docker-compose.test.yml` / `docs/TEST_ENV.md` 现在都已补齐 BT Transmission（`http://127.0.0.1:19092`）和 `/data/downloads/tr-bt` 路径，PT / BT 双下载器本地联调不再只能复用同一台 TR。
- BT Transmission 配置目录切换快照：2026-04-14 已把 BT Transmission 的测试栈配置目录从旧的 `config/transmission-bt` 切到新的 `config/transmission-bt-stack`，并把容器挂载改成 LinuxServer 官方支持的 `/downloads/complete` / `/downloads/incomplete` / `/watch` 方式，避免复用先前已写入默认 `/downloads/...` 目录的脏 `settings.json`。
- bring-up 入口快照：`Makefile` 的 `make run` 现在会先检查 `ENV_FILE` 指向的环境文件；缺失时打印红色中文 `[环境文件缺失]` 日志和 `[处理建议]`，并支持 `ENV_FILE=/绝对路径 make run`，避免当前工作区没有 `.env` 时直接掉进 shell 原始 `source` 报错。
- 知识入口快照：历史单体主文档 `Luminarr_v15.md` 已移除，当前只保留 `README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md` 这条正式入口，避免过期总纲继续和当前主线并行。
- 环境就绪快照：2026-04-14 当前仓库根目录 `.env` 已补齐四渠道 cleanup smoke 所需环境键；提权启动的 `app.main` 已实际拉起 Feishu SDK 长连接、personal WeChat 文本轮询和 WeCom callback 监听，本地 `curl http://127.0.0.1:18889/wecom/callback` 也已返回 `400 missing echostr`。当前仓库文档也已显式写清这条探针只在 `app.main` 运行时成立；如果直接拿到 `connection refused`，先回查应用进程，再区分是不是真正的 WeCom 代码回归。当前剩余 blocker 已收缩到 WeCom 真实私聊 smoke 证据仍未补齐。
- Cloudflare Tunnel 环境 blocker 快照：2026-04-14 当前 shell 已确认 `/usr/bin/docker` 存在，但访问 `/var/run/docker.sock` 仍报 `permission denied`；`cloudflared` 命令也尚未安装。当前 WeCom 真实私聊 smoke 仍卡在 tunnel 运行环境，而不是本地 callback 入口未监听。
- WeCom 本地入口快照：`docs/GETTING_STARTED.md` 已显式写出“先起 `app.main`，再执行 `curl -si http://127.0.0.1:18889/wecom/callback -> 400 missing echostr`”这条本地 readiness 探针，并继续强调它不能替代真实私聊 smoke 证据。
- WeCom 本地入口门禁快照：verification docs gate 现在也显式锁住这条 `WeCom 本地入口快照` 文案，避免状态页把本地 readiness 探针写丢。
- README 入口快照：仓库首页 `README.md` 也已同步同一条 WeCom 本地 readiness 探针，避免只看仓库入口时继续把“本地 callback 已就绪”和“真实私聊 smoke 已完成”混成一个结论。
- WeCom 探针来源快照：`README.md` / `docs/GETTING_STARTED.md` 现在也显式写明 `18889/wecom/callback` 来自当前本地已验证 `.env`，不是 `.env.example` 默认值；如果本地改了 `WECOM_WEBHOOK_HOST` / `WECOM_WEBHOOK_PORT` / `WECOM_WEBHOOK_PATH`，探针地址也必须跟着当前 `.env` 走，避免把样例地址误读成固定真相。
- WeCom 探针来源门禁快照：verification docs gate 现在也显式锁住这条 `WeCom 探针来源快照` 文案，避免状态页把“当前本地已验证 `.env`”和“.env.example 默认值”的边界写丢。
- README 缺口快照：仓库首页 `README.md` 现在也已显式写出 cleanup 四渠道验证窗口已完成，避免用户只看入口时还停留在“只剩 WeCom 缺口”的旧结论。
- README 缺口门禁快照：verification docs gate 现在也显式锁住这条 `README 缺口快照` 文案，避免状态页把入口页的当前缺口总结写丢。
- NEXT_STEP 缺口快照：`docs/NEXT_STEP.md` 现在也已显式写出 cleanup 四渠道验证窗口已完成，避免主线目标页继续停留在“只剩 WeCom 待补”的旧结论。
- NEXT_STEP 缺口门禁快照：verification docs gate 现在也显式锁住这条 `NEXT_STEP 缺口快照` 文案，避免状态页把主线目标页的当前缺口总结写丢。
- WeCom 入口门禁收口快照：verification docs gate 现在已经把 `WeCom 本地入口快照`、`WeCom 探针来源快照`、`README 缺口快照`、`NEXT_STEP 缺口快照` 这四条入口/缺口文案一起锁住，避免入口真相再次分叉。
- `.env` 取值归一化快照：`sync-cleanup-doc-snapshots` 现在会先去掉仓库 `.env` 值首尾成对的单/双引号，再参与 `telegram_bot_api` 和 `env_readiness` 判断，避免 `"token"` 这类配置被误当成带引号字面量。
- 当前 shell env 值归一化快照：`sync-cleanup-doc-snapshots` 现在也会先去掉当前 shell 环境变量值首尾成对的单/双引号，避免当前会话里的 `\"token\"` 直接盖过后面的 `.env` / Windows env 真值。
- Telegram shell token 门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住当前 shell 带引号 `TELEGRAM_BOT_TOKEN` 的 end-to-end 快照路径，避免带引号 token 重新混进 Telegram Bot API URL。
- Windows env 读取归一化快照：`sync-cleanup-doc-snapshots` 现在会按大小写不敏感读取 `cmd.exe /c set` 输出里的键名，避免 `telegram_bot_token=...` 这类 Windows 环境变量被误写成缺失。
- Windows env 调用异常容错快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住 `cmd.exe /c set` 调用自身抛 `OSError` 时，会按 Windows env 缺失继续降级，而不是直接打断 cleanup 文档同步。
- Windows env 值归一化快照：`sync-cleanup-doc-snapshots` 现在也会先去掉 `cmd.exe /c set` 输出值首尾成对的单/双引号，避免 `\"token\"` 这类 Windows 环境变量继续被误当成带引号字面量。
- Telegram Windows token 门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住 Windows env 小写键名 + 带引号 token 的 end-to-end 快照路径，避免带引号 Windows token 重新混进 Telegram Bot API URL。
- docs command display 同步快照：`sync-cleanup-doc-snapshots` 现在写回 `env readiness snapshot` / `telegram bot api snapshot` 时，也会同步展示“当前 shell / .env / Windows env 值去首尾引号、Windows env 键名大小写不敏感、env readiness 里的 Windows 值级判定”这组当前实现真相，避免状态页命令示例和总述快照落后于真实逻辑。
- docs command display 转义快照：`sync-cleanup-doc-snapshots` 现在写回 `env_readiness` / `telegram_bot_api` 命令示例时，也会稳定保留 `strip('\"\'')` 这类去引号转义片段，避免状态页把可执行命令写坏成错误引号组合。
- telegram bot api command display 快照：`sync-cleanup-doc-snapshots` 现在写回 `telegram bot api snapshot` 时，也会展示“当前 shell / .env / Windows env 值去首尾引号 + Windows env 键名大小写不敏感”这整条 token 解析真相，避免状态页仍显示旧的 token 读取路径。
- env readiness command display 快照：`sync-cleanup-doc-snapshots` 现在写回 `env readiness snapshot` 时，也会显式展示“当前 shell 环境变量值先去首尾引号再判空”这条实现真相，避免状态页仍显示旧的 shell 判空逻辑。
- env readiness Windows 判定快照：`sync-cleanup-doc-snapshots` 现在写回 `env readiness snapshot` 时，也会把 Windows env 这段展示成“大小写不敏感键名 + 去首尾引号后的非空值才算 set”，避免状态页把空值环境变量误读成已就绪。
- env readiness 缺口展示快照：`sync-cleanup-doc-snapshots` 现在在 local runtime/import 已就绪但四渠道 smoke 环境未齐时，会直接写出 `missing channels: ...`，避免状态页只留 `four-channel cleanup smoke env incomplete` 这种笼统 blocker。
- env readiness 动态缺口快照：`sync-cleanup-doc-snapshots` 现在会按 Feishu / WeCom 当前真实缺口动态拼出 `missing channels: ...`，不会再把只缺一侧渠道组的环境误写成固定缺 `feishu,wecom`。
- `.env` 不可读容错快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住仓库 `.env` 存在但不可读时，`env_readiness` 会按“该来源缺失”继续降级，而不是直接抛异常打断 cleanup 文档同步。
- env readiness 完成态门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住 `four-channel cleanup smoke env ready` 分支，避免四渠道键已齐后状态页还停在 incomplete。
- env readiness import 缺口门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住 `local runtime env ready; import/refresh env incomplete` 分支，避免 Emby/import 缺口被误写成别的 blocker。
- env readiness personal WeChat 边界快照：`sync-cleanup-doc-snapshots` 现在也会显式写出 `personal_wechat login state not checked`，提醒当前 env readiness 不会把 personal WeChat 本地登录态误记成已验证。
- Telegram Bot API 就绪快照：2026-04-13 提权 `getMe` 已确认当前仓库 `.env` 里的 `TELEGRAM_BOT_TOKEN` 可用；当前 Telegram 渠道剩余缺口不是 bot 凭据不可用，而是窗口内真实私聊 cleanup 输入和回复证据仍未落仓库。
- Telegram Bot API 错误分类快照：`sync-cleanup-doc-snapshots` 现在也把 Telegram `getMe` 的 401/403 稳定归类为 `telegram bot api rejected token`，不再和网络不可达混写成 `unreachable`，避免 cleanup 窗口快照误判凭据状态。
- Telegram Bot API 网络门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住 `telegram bot api unreachable` 分支，避免 Telegram 网络故障被误写成坏 token。
- Telegram Bot API 5xx 门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住非 401/403 HTTPError 会归成 `telegram bot api unreachable`，避免 5xx / 网关异常被误写成坏 token。
- Telegram Bot API 坏 JSON 门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住坏 JSON 响应会归成 `telegram bot api unreachable`，避免异常响应体被误写成坏 token 或 ready。
- Telegram Bot API OSError 门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住底层 `OSError` 会归成 `telegram bot api unreachable`，避免 socket/SSL 级网络异常直接打断 cleanup 文档快照同步。
- Telegram Bot API 缺失态门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住 `telegram bot token missing` 分支，避免最基础的凭据缺失态从快照门禁里漂走。
- Telegram `.env` 不可读缺失态门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住仓库 `.env` 不可读且无其他 token 来源时，`telegram_bot_api` 仍返回 `telegram bot token missing`，避免 `.env` 读取容错只停在 helper 层。
- Telegram Windows env OSError 缺失态门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住 Windows env 探测抛 `OSError` 且无其他 token 来源时，`telegram_bot_api` 仍返回 `telegram bot token missing`，避免 Windows env 调用异常容错只停在 helper 层。
- 窗口活性快照：已满足退出条件
- 当前状态快照：已完成
- 当前结论快照：验证窗口已满足退出条件；截至 2026-04-14，Telegram / personal WeChat / Feishu / WeCom 四个渠道真实私聊 cleanup smoke 与其余退出证据已全部满足，窗口正式完成。
- 聚合 smoke gate 快照：已把 `mixed-case` 英文 `cleanup / cleanup inspect` 输入、四渠道 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查` 的 service-not-ready observability，以及 `chat-scoped task_ref` 命中 `job_event` 关联查询失败、缺结构化 `source_path/target_path` 两类 identity retention / rejection guidance 补进四渠道 cleanup smoke。
- 单渠道入口快照：`tests/test_telegram_bot.py -k cleanup` 现在也单独锁住 Telegram cleanup mixed-case 英文 `cleanup / cleanup inspect` 路由，避免 Telegram 胶水层大小写回退只能从聚合 smoke 间接发现。
- Telegram cleanup smoke 日志快照：Telegram 入口现在会在 cleanup / cleanup inspect 文本成功回出后，按统一协议追加绿色 `[cleanup 私聊 smoke]` 日志，并带上 `date/channel/action/query/reply_head`，方便后续把真实私聊证据回填到窗口台账。
- Telegram chat-scoped shortcut 门禁快照：现在也单独锁住 `cleanup inspect cleanup-shortcut` 经过 Telegram handler 后仍能解析出真实 `task_id/task_hash`，避免主入口把 `cleanup-shortcut` 当成普通字符串传给 cleanup service。
- verification docs gate 快照：`mixed-case english cleanup protocol`、`NEXT_STEP current-window sync`、`correlation-query-failure observability`、`source-type-unsupported blocked-log observability`、`cleanup-service-not-ready fix-hint observability`、`success-event-append-failure observability`、`delete-failure observability`、`correlation-missing unresolved-identity blank display`、`correlation-missing inspect identity resolution`、`correlation-missing rejection guidance`、`post-cleanup cleanup inspect confirmation`、`source-type-unsupported rejection guidance`、`chat-scoped task_ref post-cleanup cleanup inspect confirmation`、`chat-scoped task_ref target-missing cleanup inspect follow-up guidance`、`chat-scoped task_ref source-missing cleanup inspect follow-up guidance`、`chat-scoped task_ref source-type-unsupported cleanup inspect follow-up guidance`、`chat-scoped task_ref guard-rejected cleanup inspect follow-up guidance`、`chat-scoped task_ref target-missing rejection guidance`、`chat-scoped task_ref source-missing rejection guidance`、`chat-scoped task_ref source-type-unsupported rejection guidance`、`chat-scoped task_ref guard-rejected rejection guidance` 已纳入窗口台账门禁，并继续卡住“窗口已完成后，`当前 cleanup 协议观察` 不得残留窗口日期阻塞或真实私聊 smoke 待补文案”，同时也校验 `test-cleanup-window` 顺序、`docs/GETTING_STARTED.md` 无 `make` 备用命令与三段 Makefile gate 保持一致、`sync-cleanup-doc-snapshots` 的 `Makefile` / `docs/GETTING_STARTED.md` 入口一致性、四个单渠道 `cleanup-shortcut` 门禁继续写在 `docs/NEXT_STEP.md` / `docs/STATUS.md`、`README.md` 入口退出条件显式覆盖 `verification docs gate`，以及 README 十条 cleanup 本地 gate 入口继续明确“不能替代四渠道真实私聊 smoke 证据”，避免 mixed-case-english-protocol / next-step-current-window-sync / query-failure / blocked-log / cleanup-service-not-ready-fix-hint / event-append-failure / delete-failure / unresolved-identity / inspect-identity-resolution / rejection-guidance / post-cleanup-confirmation / source-type-unsupported-guidance / chat-scoped-post-cleanup-confirmation / chat-scoped-target-missing-follow-up / chat-scoped-source-missing-follow-up / chat-scoped-source-type-follow-up / chat-scoped-guard-rejected-follow-up / chat-scoped-target-missing-rejection-guidance / chat-scoped-source-missing-rejection-guidance / chat-scoped-source-type-rejection-guidance / chat-scoped-guard-rejected-rejection-guidance 可观测性命名从台账里漂走，也避免窗口收口后台账还保留进行中文案或入口退出条件漂移。
- 验证快照维护快照：仓库里现在有 `make sync-cleanup-doc-snapshots` / `.venv/bin/python -m app.maintenance.cleanup_verification_docs ...`，会顺序执行固定验证命令，并把 `docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 的固定快照行连同环境就绪、Telegram Bot API 就绪、仓库内真实 smoke 证据快照一起改到最新结果，减少 cleanup 窗口期间手工抄写验证结果的漂移。
- 仓库证据快照能力快照：`local_smoke_evidence` 现在在命中窗口期 `[cleanup 私聊 smoke]` 日志时会直接带出 `found channels + missing channels`，四渠道齐全后会改成 `all channels covered`，没命中时也会显式列出缺失渠道；当前结果已收口为 `found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered`，说明四个渠道的窗口内仓库证据已全部落下。
- 仓库证据坏日志容错快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住 `local_smoke_evidence` 遇到单个不可读日志文件时会跳过该文件、继续保留其余可读 smoke 证据，避免 cleanup 文档同步被一个坏日志直接打断。
- 仓库证据 non-UTF8 脏字节容错快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住 `local_smoke_evidence` 在日志文件混入 non-UTF8 脏字节时，仍能保留同文件中的有效 cleanup smoke 行，避免脏日志字节把仓库证据统计打断。
- Channel progress non-UTF8 整链路门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也直接锁住 `sync_documents()` 在 non-UTF8 脏字节日志下仍会把命中渠道写进 `Channel progress`，避免 helper 级通过但真实文档回写链丢证据。
- 仓库证据坏 payload 行容错快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住 `local_smoke_evidence` 在同一日志文件里遇到损坏的 `[cleanup 私聊 smoke]` payload 行时，会忽略坏行并保留同文件中的合法协议行，避免单条坏 payload 污染仓库证据统计。
- Channel progress 坏 payload 整链路门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也直接锁住 `sync_documents()` 在同一日志文件混入损坏 cleanup smoke payload 行时，会忽略坏行并把合法渠道写进 `Channel progress`，避免 helper 级通过但真实文档回写链丢证据。
- 仓库证据未来日期门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也单独锁住“晚于当前快照日期的 cleanup smoke 日志不会被算进 `local_smoke_evidence`”，避免未来日期日志被误回填成当前窗口证据。
- 仓库证据日期聚合快照：cleanup 文档同步工具现在也会按渠道保留“窗口内最近一次真实 smoke 日期”，后续要把日志证据接到 `Channel progress` 表时不需要重新解析一遍原始日志。
- Channel progress 同步快照：`docs/CLEANUP_VERIFICATION_WINDOW.md` 里的四渠道进度表现在也会由同步工具按固定顺序自动重写；由于当前仓库仍无窗口内真实 smoke 证据，表格状态继续保持四个 `待验证`。
- Channel progress 截断保护快照：同步工具现在在重写四渠道进度表时也会保留 `Verification evidence`、`PT 做种 guardrail 评估` 和 `Update rule` 后续章节，不会再把窗口台账截断成只剩表格。
- Channel progress 整链路门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也直接跑最小 `sync_documents()` 回写样例，锁住真实文档同步路径在重写进度表后仍保留 `Verification evidence`、`PT 做种 guardrail 评估` 和 `Update rule` 标题。
- Channel progress 固定顺序门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也直接锁住 `sync_documents()` 在日志乱序时仍按 Telegram / personal WeChat / Feishu / WeCom 的固定顺序输出完成行，避免窗口台账顺序随日志抖动。
- Channel progress 最近日期门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也直接锁住 `sync_documents()` 在同一渠道命中多条窗口期真实 smoke 日志时会把该渠道更新为最近绝对日期，避免已完成渠道回填旧日期。
- Channel progress 待验证锚点门禁快照：`tests/test_cleanup_verification_docs_sync.py` 现在也直接锁住 `sync_documents()` 在只有部分渠道完成时仍保留其他渠道的 `待验证`、`-` 和窗口开始日锚点备注，避免窗口台账把剩余缺口写成空白或漂移文案。
- Channel progress 文档顺序门禁快照：`tests/test_cleanup_verification_window_doc.py` 现在也直接校验窗口台账里的四渠道行顺序固定为 Telegram / personal WeChat / Feishu / WeCom，避免手工编辑文档时绕过同步器顺序保护。
- cleanup 私聊 smoke 日志协议快照：仓库里现在也有统一的 `app/bot/cleanup_smoke_logging.py`，先把 `date/channel/action/query/reply_head` 这组最小日志格式锁住；真实私聊 cleanup smoke 现在在未先调用 configure helper 时，也会默认追加到当前工作目录下的 `logs/cleanup-private-chat-smoke.log`，且追加链已经不再读取模块级全局路径，非默认路径必须显式通过 `log_path` 传入；configure helper 成功和失败时都只保留“返回显式 path / 打印 fix-hint”，reset helper 和模块级死变量也都已删除，让 `sync-cleanup-doc-snapshots` 能直接从仓库日志回填窗口证据，避免窗口证据重新分叉或只留在 stdout。2026-04-15 这条日志配置函数开始支持显式 `log_path` 传参，测试路径不再必须直接改私有全局变量。
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
| Telegram | 已完成 | 2026-04-14 |
| personal WeChat | 已完成 | 2026-04-14 |
| Feishu | 已完成 | 2026-04-14 |
| WeCom | 已完成 | 2026-04-14 |

## Main risks and gaps

- 2026-04-14 代码审查确认：`shared private-chat runtime` 仍通过 [app/bot/private_chat_runtime.py](/home/alex/projects/luminarr/app/bot/private_chat_runtime.py) 伪造 Telegram `context` 去调用 [app/bot/telegram_bot.py](/home/alex/projects/luminarr/app/bot/telegram_bot.py)；这不是抽象味道问题，而是当前真实结构债，因为 `微信登录` 分支已经会读取 `context.application.bot`。
- 2026-04-15 代码审查确认：`search_media` 里搜索候选持久化失败、澄清态 `upsert_pending()` / `clear_pending()` / `get_pending_query()` 失败、以及候选读取 `get_candidate()` 失败都已补红色中文日志和 `[处理建议]`；`add_to_downloader.has_pending_add()` / `cancel_pending_add()` 里的 `job_repo.get_downloader_job_for_chat_ref()` / `get_latest_pending_downloader_job()` 查询失败也已补红色中文日志和 `[处理建议]`，不再静默吞掉 `candidate_repo.save_candidates()` / `clarification_repo.upsert_pending()` / `clarification_repo.clear_pending()` / `clarification_repo.get_pending_query()` / `candidate_repo.get_candidate()` / `job_repo.get_downloader_job_for_chat_ref()` / `job_repo.get_latest_pending_downloader_job()` 异常；当前剩余风险收口为“其他持久化路径仍有 `except Exception: pass/return None` 会把‘真没数据’和‘SQLite/配置异常’混写”。
- 2026-04-15 代码审查确认：`cleanup_smoke_logging` 去模块级全局状态已收口：追加链不再读取全局状态，configure helper 成功/失败态不再写状态，reset helper 和死变量也已删除；后续只保留 `tests/test_cleanup_smoke_logging.py` 回归门禁，不再把这条风险作为独立施工项。
- 2026-04-14 代码审查确认：Feishu 长连接当前仍直接依赖 `lark_oapi` 私有 API 和模块级变量 patch；版本升级前必须重新验证 `_auto_reconnect`、`_disconnect()`、`_cache._cron` 与 `lark_oapi.ws.client.loop` 这几处内部实现。
- 2026-04-14 代码审查确认：`get_download_status` 当前会写 `download_monitor`、补 `downloader.completed_observed`，并可能接到 auto-import，所以它不是只读动作；不要把它误放进 `READ_ONLY_ACTIONS`。
- `series / anime` 独立名称解析还没实现；当前最稳的是 movie-first。
- 当前“给别人用”的体验还偏工程向：私聊返回仍缺更美观的图片/信息卡片/字符排版。
- 当前虽然已经有最小 `Dockerfile` / `docker-compose.yml`，但还没有把 Transmission / Emby / Prowlarr 整套依赖一起内置到主 compose。
- 四个渠道都在真用，最大的维护风险是渠道适配层和 shared runtime 漂移，导致同一协议在四处长出不同分支。
- `shared private-chat runtime` 入口当前仍通过 `app/bot/private_chat_runtime.py -> app/bot/telegram_bot.py.handle_private_chat_query_text` 反向依赖 Telegram；大多数文本路径虽然已经可以在无 Telegram update 的前提下直跑，但 `微信登录` 仍直接依赖 Telegram 的二维码/文本回传能力。这条结构债已记录为 cleanup 窗口后的最小抽离项：把 shared runtime 入口从 `telegram_bot.py` 独立出来，并把 Telegram-only 媒资回传收口成显式注入能力，不在当前 cleanup 验证窗口内展开。
- personal WeChat 仍然仅限单账号私聊文本，每次回复依赖最新消息里的 `context_token`；一旦用户长时间不发言旧 token 会过期，当前没有可靠的 personal WeChat 主动推送闭环；登录成功后仍需下次启动才能开始轮询。
- Feishu / WeCom 当前只支持最小私聊文本，不支持群聊、图片、卡片、按钮回调；Feishu 入站现已切到官方 SDK 长连接，WeCom 仍通过 callback 被动回包，且还没有主动发消息客户端。
- Feishu 长连接当前正常停机时，业务侧已经不再误打 `[Feishu 长连接启动失败]`、`ConnectionClosedOK` traceback 或 `Event loop is closed` traceback；当前剩余 `lark_oapi` 关闭噪声只剩 pending-task warning，仍属于上游 SDK 行为，不是当前主线要扩的 cleanup 能力。
- cleanup inspect / execution 当前只对带结构化 `source_path + target_path` 的导入任务可用；更早历史任务仍需人工甄别。
- PT 做种 guardrail 评估已记录到 `docs/CLEANUP_VERIFICATION_WINDOW.md`；当前 cleanup guardrail 还没读取下载器 seeding 状态，`pt_min_seed_hours` 也未进入 cleanup 阻断判断，因此删源前仍无法确认 PT 任务是否仍在做种。
- completion truth 现在已经有独立 downloader status polling 最小闭环；当前剩余工作只在更细的回归与可观测性收口，不再是“有没有独立后台轮询本体”。
- metadata scraping、subtitle auto-translation（当前仅 `.srt`）、Emby refresh 失败时不会回滚 import success；缺配置时会显式失败。
- BT shared source adapter、BT external web-source、pure BT ranking、`btsub` 选源都已可用，但还不是共享确定性评分器。
- 当前主线只支持 Emby；Jellyfin / Plex 仍是后续扩展，不在 cleanup 窗口这一步混入。
- 通用 plugin / skill / MCP 平台化仍然继续后置，不是当前收口目标。
- 2026-04-14 当前仓库根目录 `.env` 已补齐 Telegram / downloader / import / Feishu / WeCom 所需的最小配置，并且提权启动的 `app.main` 已在运行；本地 `18889/wecom/callback` 也已确认可达。WeCom 真实私聊 smoke 现在也已补齐，cleanup 四渠道验证窗口正式完成。
- 2026-04-14 本地仓库内已经有可回填的窗口期真实 smoke 证据：`logs/cleanup-private-chat-smoke.log` 已命中 Telegram / personal WeChat / Feishu / WeCom 四个渠道的窗口内 `[cleanup 私聊 smoke]` 行；当前四渠道真实私聊 smoke 证据已经齐全。
- 2026-04-14 宿主机侧 `curl` 已确认 PT / BT 两台 Transmission 都返回 `409 Conflict + X-Transmission-Session-Id`、Emby `/System/Info/Public` 正常返回 JSON，`stat -c "%d %n" /data/downloads/tr /data/downloads/tr-bt /data/library/movies` 也确认三条路径仍在同一设备上；当前剩余环境差异主要是本 CLI shell 直打 `19092` 仍失败，以及 sandbox 下本地随机端口监听会返回 `Operation not permitted`，所以 Feishu / WeCom 两条 webhook server HTTP 测试在全量 pytest 中会 skip。
- 2026-04-14 当前仓库里的双 Transmission 测试栈配置已经在宿主机 sudo shell 侧复验通过：`luminarr-test-transmission-bt` 已处于 `Up`，宿主机侧 `curl -si http://127.0.0.1:19092/transmission/rpc` 已返回 `409 Conflict + X-Transmission-Session-Id`，`config/transmission-bt-stack/settings.json` 也已按新挂载方式初始化为 `/downloads/complete` / `/downloads/incomplete` / `/watch`；当前剩余差异只是本 CLI shell 直打 `19092` 仍失败，这更像本地 CLI 连通性差异，不再视为测试栈配置 blocker。

## Latest verification

- tests：2026-04-14，`858 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）
- four-channel cleanup smoke tests：`376 passed`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- cleanup service tests：2026-04-14，`38 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`）
- focused cleanup tests：`526 passed, 93 deselected`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- cleanup verification docs gate：`384 passed`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`）
- focused config truth tests：`4 passed, 21 deselected`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_config.py -k "requires_token or requires_transmission_base_url or defaults_role_binding_to_first_instance or reads_tmdb_settings"`）
- proxy / Feishu 长连接 / PNG 二维码 tests：`135 passed`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_config.py tests/test_tmdb_client.py tests/test_fanart_client.py tests/test_personal_wechat_login.py tests/test_telegram_bot.py tests/test_feishu_long_connection.py tests/test_subtitle_translator.py tests/test_bt_sources.py`）
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
- local test stack endpoint health checks：`passed (PT TR up / BT TR up / Emby up)`（2026-04-14，`curl -si http://127.0.0.1:19091/transmission/rpc`；宿主机 sudo shell `curl -si http://127.0.0.1:19092/transmission/rpc`；`curl -s http://127.0.0.1:18096/System/Info/Public`）
- local test stack path device check：`passed (same device)`（2026-04-14，`stat -c "%d %n" /data/downloads/tr /data/downloads/tr-bt /data/library/movies`）
- env readiness snapshot：`four-channel cleanup smoke env ready`（2026-04-14，`bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "import os; keys=[\"TELEGRAM_BOT_TOKEN\",\"PROWLARR_BASE_URL\",\"PROWLARR_API_KEY\",\"TRANSMISSION_BASE_URL\",\"EMBY_BASE_URL\",\"EMBY_API_KEY\",\"FEISHU_APP_ID\",\"FEISHU_APP_SECRET\",\"FEISHU_ENCRYPT_KEY\",\"WECOM_TOKEN\",\"WECOM_ENCODING_AES_KEY\",\"WECOM_RECEIVE_ID\"]; print(\"\\n\".join(f\"{k}=\" + (\"set\" if os.getenv(k,\"\").strip().strip('\"\'') else \"missing\") for k in keys))"' ; python3 -c "import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; rows=dict(line.split('=', 1) for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if '=' in line); lookup={key.lower(): value.strip().strip('\"\'') for key, value in rows.items()}; print('\\n'.join(f'{k}=' + ('set' if lookup.get(k.lower(), '') else 'missing') for k in keys))" ; python3 -c "from pathlib import Path; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; data={}; env_path=Path('.env'); text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); data.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); print('\\n'.join(f'{k}=' + ('set' if data.get(k, '').strip() else 'missing') for k in keys))"`）
- telegram bot api snapshot：`telegram bot api ready`（2026-04-14，`python3 -c "import json, os, subprocess, urllib.request; from pathlib import Path; token=os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip('\"\''); env_path=Path('.env'); env_map={}; text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); env_map.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); token=token or env_map.get('TELEGRAM_BOT_TOKEN','').strip(); token=token or next((line.partition('=')[2].strip().strip('\"\'') for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if line.partition('=')[0].strip().lower() == 'telegram_bot_token'), ''); print('telegram bot token missing' if not token else ('telegram bot api ready' if json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=5)).get('ok') else 'telegram bot api rejected token'))"`）
- local smoke evidence snapshot：`found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered`（2026-04-14，`sqlite3 -header -column data/luminarr.db "select max(created_at) as max_created_at from jobs; select max(created_at) as max_created_at from job_event; select max(created_at) as max_created_at, count(*) as rows from telegram_updates;" ; rg -n "\[cleanup 私聊 smoke\]" logs`）
- cleanup 补证窗口快照：`sync-cleanup-doc-snapshots` 现在在窗口仍进行中时，会继续接受开始日期之后、当前快照日期之前的真实 smoke 日志，不再把 `最早可结束日期` 误当成后续补证硬截止线。
- cleanup 窗口规则同步快照：`docs/CLEANUP_VERIFICATION_WINDOW.md` 的 `Update rule` 现在也明确写出“进行中窗口的补证上界跟随当前结论快照日期”，避免台账文字和 docs sync 行为继续分叉。
- runtime process snapshot：`luminarr process running`（2026-04-14，`python3 -c "from pathlib import Path; proc_root=Path('/proc'); matches=[]; pid_dirs=sorted((path for path in proc_root.iterdir() if path.is_dir() and path.name.isdigit()), key=lambda path: int(path.name)); for pid_dir in pid_dirs:  cmdline_path=pid_dir/'cmdline';  raw=cmdline_path.read_bytes() if cmdline_path.exists() else b'';  tokens=[token.decode('utf-8', errors='ignore') for token in raw.split(b'\\0') if token];  if tokens and 'python' in Path(tokens[0]).name and any(tokens[index] == '-m' and tokens[index + 1] == 'app.main' for index in range(len(tokens) - 1)):   matches.append(f'{pid_dir.name} ' + ' '.join(tokens)); print('luminarr process running' if matches else 'no luminarr process running')"`）
- runtime process 门禁快照：`tests/test_cleanup_docs_consistency.py` 现在只要求 runtime snapshot 在 `docs/STATUS.md` 和窗口台账之间保持一致，并接受 `running` / `no running` 两种当前态，避免合法 bring-up 快照被 gate 误判成回归。
- Telegram-only bring-up 快照：2026-04-13 提权启动 `.venv/bin/python -m app.main` 后，当前进程已进入运行态；缺少 BT 下载器角色绑定时会打印 `[BT 订阅后台扫描未启动]` 红色警告，但不会阻断最小 Telegram 入口启动。
- BT 订阅后台扫描 warning 门禁快照：`tests/test_telegram_bot.py` 现在也单独锁住 `[BT 订阅后台扫描未启动]` 和 `[处理建议]` 这组日志，避免 BT 角色绑定缺失时只剩无提示 return。
- Telegram 启动失败可观测性快照：当前 Telegram bootstrap 遇到网络 / DNS 问题时，也会先打印红色中文 `[Telegram 启动失败]` 和 `[处理建议]`，再把异常继续抛出，避免纯英文 traceback 直接淹没修复线索。
- cleanup smoke logging tests：2026-04-15，`6 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_smoke_logging.py`）
- cleanup smoke default-path manual check：2026-04-15，`passed`（`tmpdir=$(mktemp -d) && cd "$tmpdir" && PYTHONPATH=/home/alex/projects/luminarr /home/alex/projects/luminarr/.venv/bin/python -c "from app.bot.cleanup_smoke_logging import log_cleanup_private_chat_smoke; log_cleanup_private_chat_smoke(channel='telegram', query='cleanup inspect cleanup-shortcut', reply_text='清理预检结果：\\n任务 ID: 87', chat_id=1, user_id=2)" && cat "$tmpdir/logs/cleanup-private-chat-smoke.log"`）
- cleanup smoke ignore-global fallback manual check：2026-04-15，`passed`（`tmpdir=$(mktemp -d) && cd "$tmpdir" && PYTHONPATH=/home/alex/projects/luminarr /home/alex/projects/luminarr/.venv/bin/python -c "from pathlib import Path; import app.bot.cleanup_smoke_logging as m; m._cleanup_private_chat_smoke_log_path = Path('/definitely-blocked/cleanup.log'); m.log_cleanup_private_chat_smoke(channel='telegram', query='cleanup inspect cleanup-shortcut', reply_text='清理预检结果：\\n任务 ID: 87', chat_id=1, user_id=2)" && cat "$tmpdir/logs/cleanup-private-chat-smoke.log"`）
- cleanup smoke configure-success-no-global manual check：2026-04-15，`passed`（`tmpdir=$(mktemp -d) && cd "$tmpdir" && PYTHONPATH=/home/alex/projects/luminarr /home/alex/projects/luminarr/.venv/bin/python -c "from pathlib import Path; import app.bot.cleanup_smoke_logging as m; m.configure_cleanup_private_chat_smoke_log_file(log_dir=Path('custom-logs')); m.log_cleanup_private_chat_smoke(channel='telegram', query='cleanup inspect cleanup-shortcut', reply_text='清理预检结果：\\n任务 ID: 87', chat_id=1, user_id=2)" && test -f "$tmpdir/logs/cleanup-private-chat-smoke.log" && test ! -f "$tmpdir/custom-logs/cleanup-private-chat-smoke.log"`）
- cleanup smoke configure-failure-no-global-clear manual check：2026-04-15，`passed`（`tmpdir=$(mktemp -d) && cd "$tmpdir" && PYTHONPATH=/home/alex/projects/luminarr /home/alex/projects/luminarr/.venv/bin/python -c "from pathlib import Path; import app.bot.cleanup_smoke_logging as m; m._cleanup_private_chat_smoke_log_path = Path('/stale/path/cleanup.log'); blocked=Path('blocked-parent'); blocked.write_text('occupied', encoding='utf-8'); m.configure_cleanup_private_chat_smoke_log_file(log_dir=blocked / 'logs'); m.log_cleanup_private_chat_smoke(channel='telegram', query='cleanup inspect cleanup-shortcut', reply_text='清理预检结果：\\n任务 ID: 87', chat_id=1, user_id=2)" && test -f \"$tmpdir/logs/cleanup-private-chat-smoke.log\"`）
- cleanup smoke reset-noop manual check：2026-04-15，`passed`（`tmpdir=$(mktemp -d) && cd "$tmpdir" && PYTHONPATH=/home/alex/projects/luminarr /home/alex/projects/luminarr/.venv/bin/python -c "from pathlib import Path; import app.bot.cleanup_smoke_logging as m; m._cleanup_private_chat_smoke_log_path = Path('/stale/path/cleanup.log'); m.reset_cleanup_private_chat_smoke_log_file(); m.log_cleanup_private_chat_smoke(channel='telegram', query='cleanup inspect cleanup-shortcut', reply_text='清理预检结果：\\n任务 ID: 87', chat_id=1, user_id=2)" && test -f \"$tmpdir/logs/cleanup-private-chat-smoke.log\"`）
- cleanup smoke remove-dead-global-symbol manual check：2026-04-15，`passed`（`tmpdir=$(mktemp -d) && cd "$tmpdir" && PYTHONPATH=/home/alex/projects/luminarr /home/alex/projects/luminarr/.venv/bin/python -c "import app.bot.cleanup_smoke_logging as m; from pathlib import Path; assert not hasattr(m, '_cleanup_private_chat_smoke_log_path'); m.log_cleanup_private_chat_smoke(channel='telegram', query='cleanup inspect cleanup-shortcut', reply_text='清理预检结果：\\n任务 ID: 87', chat_id=1, user_id=2)" && test -f \"$tmpdir/logs/cleanup-private-chat-smoke.log\"`）
- cleanup smoke remove-reset-api-shell manual check：2026-04-15，`passed`（`tmpdir=$(mktemp -d) && cd "$tmpdir" && PYTHONPATH=/home/alex/projects/luminarr /home/alex/projects/luminarr/.venv/bin/python -c "import app.bot.cleanup_smoke_logging as m; from pathlib import Path; assert not hasattr(m, 'reset_cleanup_private_chat_smoke_log_file'); m.log_cleanup_private_chat_smoke(channel='telegram', query='cleanup inspect cleanup-shortcut', reply_text='清理预检结果：\\n任务 ID: 87', chat_id=1, user_id=2)" && test -f \"$tmpdir/logs/cleanup-private-chat-smoke.log\"`）
- search media candidate-save observability manual check：2026-04-15，`passed`（`PYTHONPATH=/home/alex/projects/luminarr /home/alex/projects/luminarr/.venv/bin/python -c "import asyncio; from app.services.search_media import SearchMediaService; BoomRepo=type('BoomRepo', (), {'save_candidates': lambda self, chat_id, items: (_ for _ in ()).throw(RuntimeError('db down'))}); service=SearchMediaService(lambda query: asyncio.sleep(0, result=[{'title':'Dune','year':2021,'size':1,'indexerName':'IndexerA'}]), candidate_repo=BoomRepo()); asyncio.run(service.search_and_format('dune', chat_id=1001))"`）
- search media tests：2026-04-15，`20 passed`（`.venv/bin/python -m pytest -q tests/test_search_media.py`）
- search media clarification-upsert observability manual check：2026-04-15，`passed`（`PYTHONPATH=/home/alex/projects/luminarr /home/alex/projects/luminarr/.venv/bin/python -c "import asyncio; from app.services.search_media import SearchMediaService; BoomRepo=type('BoomRepo', (), {'upsert_pending': lambda self, chat_id, query: (_ for _ in ()).throw(RuntimeError('db down'))}); service=SearchMediaService(lambda query: asyncio.sleep(0, result=[]), clarification_repo=BoomRepo()); asyncio.run(service.search_and_format('unknown', chat_id=1001))"`）
- search media clarification-clear observability tests：2026-04-15，`4 passed, 17 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification or clear_clarification_pending_logs_persistence_failure"`）
- search media clarification-load observability tests：2026-04-15，`5 passed, 17 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification or is_clarification_pending_logs_persistence_failure"`）
- search media candidate-load observability manual check：2026-04-15，`passed`（`PYTHONPATH=/home/alex/projects/luminarr /home/alex/projects/luminarr/.venv/bin/python -c "from app.services.search_media import SearchMediaService; BoomRepo=type('BoomRepo', (), {'get_candidate': lambda self, chat_id, index: (_ for _ in ()).throw(RuntimeError('db down'))}); service=SearchMediaService(lambda query: None, candidate_repo=BoomRepo()); service.get_cached_candidate(1001, 1)"`）
- channel identity fail-closed tests：2026-04-15，`1 passed, 38 deselected`（`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k project_channel_identity`）
- downloader routing fail-closed tests：2026-04-15，`4 passed`（`.venv/bin/python -m pytest -q tests/test_main.py`）
- add to downloader pending-query observability tests：2026-04-15，`4 passed, 7 deselected`（`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "pending or test_has_pending_add_logs_job_lookup_failure"`）
- add to downloader cancel-query observability tests：2026-04-15，`5 passed, 7 deselected`（`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "pending or cancel_pending_add_logs_job_lookup_failure"`）
- compile check：2026-04-14，`passed`（`python3 -m compileall app tests`）
- search media compile check：2026-04-15，`passed`（`python3 -m compileall app/services/search_media.py tests/test_search_media.py`）
- docs consistency check：2026-04-14，`passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`）
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
