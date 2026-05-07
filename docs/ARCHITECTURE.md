# ARCHITECTURE.md

> 本文基于 2026-05-07 代码结构反推，描述“现在系统怎么工作”。如果文档和代码冲突，以代码为准。

## 1. 总体结构

Luminarr 是一个单进程 Python 应用。`app/main.py` 在启动时完成装配：

1. 读取环境变量并按能力生成 `Settings`
2. 判定当前宿主模式（Telegram / WeCom / Feishu）
3. 初始化 SQLite
4. 创建 repo、外部 client、业务 service
5. 创建 Telegram `Application` 或 `NonTelegramRuntimeHost`
6. 注入 shared runtime、sender、scheduler 所需 `bot_data`
7. 启动 Telegram polling 或非 Telegram host 生命周期

业务入口不是 Web API，而是多渠道私聊文本和 Telegram callback。它们最终都进入 shared private-chat runtime：

`渠道适配层 -> shared private-chat runtime -> execution gate -> services -> repos / external clients -> reply`

## 2. 技术栈

| 维度 | 当前实现 |
| --- | --- |
| 语言 | Python 3.12 |
| 核心依赖 | `python-telegram-bot`、`httpx`、`cryptography`、`wechat-clawbot` |
| 持久化 | SQLite |
| 下载器协议 | Transmission RPC、qBittorrent Web API |
| 媒体系统 | Emby、Jellyfin、Plex |
| 搜索 / 元数据 | Prowlarr、TMDB、Fanart.tv、BT WebSource |
| 渠道 | Telegram、personal WeChat、Feishu、WeCom |
| 本地工具 | Docker Compose、`ffmpeg` / `ffprobe` |
| CI | GitHub Actions `quality.yml` |

补充说明：

- Feishu 长连接在代码里通过可选 `lark_oapi` 启动
- WeCom 回调用内置 `HTTPServer`，不是引入完整 Web 框架
- 字幕翻译通过 OpenAI 兼容 chat completions 接口调用

## 3. 目录分工

| 路径 | 职责 |
| --- | --- |
| `app/main.py` | 应用装配根入口 |
| `app/config.py` | 环境变量校验、解析、标准化 |
| `app/bot/` | 渠道适配、shared private-chat runtime、BT follow-up 状态机 |
| `app/services/` | 搜索、下载确认、导入、cleanup、watchlist、btsub、metadata、字幕等业务逻辑 |
| `app/clients/` | 对外部系统的最小协议封装 |
| `app/db/` | SQLite schema 和 repo |
| `app/runtime/` | execution gate、跨渠道文本 delivery |
| `app/maintenance/` | 文档快照同步等维护脚本 |
| `tests/` | 行为回归、协议保护、docs gate |
| `docker-compose.yml` | 部署本体 |
| `docker-compose.test.yml` | 本地联调测试栈 |
| `archive/docs/` | 已归档的历史方案和施工记录 |

## 4. 启动装配图

### 4.1 配置与真相层

- `load_settings()` 读取 `.env`
- `SqliteDatabase.initialize()` 创建 / 修补表结构
- 创建以下 repo：
  - `CandidateMappingRepo`
  - `ClarificationRepo`
  - `ApprovalRepo`
  - `JobRepo`
  - `JobEventRepo`
  - `DownloadMonitorRepo`
- `BtPendingRepo`
- `WatchlistRepo`
- `BtSubscriptionRepo`
- `AdultContentRegistryRepo`
- `AdultDuplicateMemorySnapshotRepo`
- `TelegramUpdateRepo`

### 4.2 外部 client

- `ProwlarrClient`
- `TmdbClient`
- `FanartClient`
- `TransmissionClient`
- `QbittorrentClient`
- `EmbyClient` / `JellyfinClient` / `PlexClient`
- `WebSourceClient`
- `FeishuClient`
- Avmoo / Avsox / JavBus / Caribbeancom / JavLibrary read-only helper clients

### 4.3 业务 service

- `SearchMediaService`
- `AddToDownloaderService`
- `AdultDuplicateMemoryService`
- `GetDownloadStatusService`
- `ImportToLibraryService`
- `PostDownloadAutoImportService`
- `CleanupDownloadedSourceService`
- `ManageWatchlistService`
- `ManageBtSubscriptionService`
- `AdultArchiveService`
- `MetadataScraperService`
- `SubtitleTranslatorService`
- `RefreshMediaServerService`

### 4.4 运行时宿主

- `build_telegram_application()` 创建 Telegram `Application`
- `_resolve_runtime_host_mode()` 会在 Telegram、WeCom-only、Feishu-only 之间选择宿主
- `NonTelegramRuntimeHost` 为 WeCom-only / Feishu-only 提供最小 host 容器
- `telegram_sidecar_runtime.py` / `non_telegram_runtime_host.py` 负责启动和关闭：
  - Feishu 长连接
  - personal WeChat 轮询（仅 Telegram host）
  - WeCom webhook server
  - 下载完成轮询与自动导入 scheduler
  - BT subscription scheduler

## 5. shared private-chat runtime

`app/bot/private_chat_runtime.py` 是 shared private-chat runtime 边界。四个渠道都只负责把外部消息投影成：

- `query`
- `chat_id`
- `user_id`
- `channel`
- `reply_func`

随后统一进入下面的路由顺序：

1. 开场路由：取消、direct BT、personal WeChat 登录、BT 只读、BT 批量确认、adult duplicate override
2. BT follow-up：处理链选择、媒体类型选择
3. execution-gated 路由：状态、watchlist、btsub、import、cleanup
4. 尾部路由：`confirm`、TMDB 关联、raw BT 目录选择、数字选片 / callback 选资源、搜索 fallback

`ExecutionGate` 会把只读操作直接放行，把副作用操作串行化。

## 6. 渠道层

### Telegram

- `telegram_runtime_adapter.py` 把 Update / CallbackQuery 接到 runtime
- Telegram PT 资源卡与 adult BT richer reply 通过 inline buttons / callback data 接回 shared runtime
- `telegram_update_repo` 负责 update 去重
- Telegram 也是 sidecar 生命周期宿主

### personal WeChat

- `personal_wechat_text.py` 通过 `wechat-clawbot` 轮询单账号私聊文本
- 渠道身份会被映射成内部 `chat_id` / `user_id`
- 当前主动推送 / 登录态依赖本地运行状态

### Feishu

- `feishu_adapter.py` 解析私聊文本事件
- `feishu_long_connection.py` 通过官方 SDK 长连接接收事件

### WeCom

- `wecom_adapter.py` 负责验签、解密、回包加密
- `wecom_webhook_server.py` 提供轻量 HTTP webhook 入口
- shared sender 当前不支持 WeCom 主动回发；WeCom 只具备入站文本最小画像

### 跨渠道统一层

- `channel_identity.py` 对外部 chat/user id 做哈希投影
- `runtime/delivery.py` 根据渠道渲染统一的 DeliveryItem 文本

## 7. 关键业务模块

### 7.1 搜索与候选

`SearchMediaService` 负责：

- 解析用户查询
- 调 TMDB 做标题 / 年份增强
- 调 Prowlarr / WebSource 搜索
- 排序、去重、歧义识别
- 保存候选到 `candidate_mapping`
- 保存澄清态到 `clarification_state`
- 生成跨渠道回复文本

BT 只读和 BT 批量预览共用同一个 service，但不会直接触发副作用。

### 7.2 下载确认

`AddToDownloaderService` 负责：

- 从候选或直接 source 构造 `PendingAddContext`
- 写入 downloader approval pending
- 写入 pending `jobs`
- 记录 `job_event`
- 数字选资源 / Telegram callback 走 guarded auto-confirm；direct source / BT follow-up / duplicate override 保留显式 `confirm`
- `confirm` 后真正调下载器
- 记录 `download_monitor`
- 维护成人资源历史状态

下载确认的真正副作用边界是：

`pending_add -> approval_record(pending) -> jobs(pending_approval) -> confirm -> downloader.add_torrent()`

### 7.3 状态与自动导入

`GetDownloadStatusService` 负责：

- 按 task ref 查实际下载器状态
- 把观察结果写回 `download_monitor`
- 首次完成时写 `downloader.completed_observed`
- 触发 `PostDownloadAutoImportService`

`PostDownloadAutoImportService` 会：

- 跳过低质量 CAM / TS 等资源
- 成人内容走 `AdultArchiveService`
- 普通内容走 `ImportToLibraryService.auto_import_by_task_ref()`

### 7.4 导入与后处理

`ImportToLibraryService` 负责：

- 校验下载是否完成
- 识别 raw BT 并阻断
- 生成导入待确认
- `import <ref>` 会走 `auto_import_by_task_ref()`：先创建 pending，再自动执行首轮 confirm
- 首轮 confirm 默认执行硬链接导入
- 跨文件系统时进入 copy-fallback pending
- 记录 import 事件、媒体身份、目标路径

后处理由 `ImportPostProcessingService` 串起：

- metadata scraping
- subtitle translation
- media server refresh

### 7.5 cleanup

`CleanupDownloadedSourceService` 依赖 `job_event` 中最近一次 `import.succeeded`：

- `cleanup inspect` 只读检查 source / target / guardrail
- `cleanup` 真正删除下载源
- 可选 PT 最小做种时间窗保护

### 7.6 watchlist 与 BT subscription

`ManageWatchlistService`：

- `list/add/remove/clear`
- 只做持久化，不自动下载

`ManageBtSubscriptionService`：

- `list/add/remove/clear/run`
- scheduler tick 通过搜索命中新资源
- 命中后调用 `AddToDownloaderService.add_candidate_source()`
- 仍保留人工 `confirm` 边界

## 8. 数据模型

| 表 | 用途 |
| --- | --- |
| `candidate_mapping` | 搜索候选序号映射 |
| `clarification_state` | 搜索歧义待澄清状态 |
| `approval_record` | 下载 / 导入审批状态、lease version、过期时间 |
| `jobs` | 待确认任务、执行权、payload、版本号 |
| `job_event` | 任务事件流水、source / target 路径、媒体身份等 |
| `telegram_updates` | Telegram update 去重 |
| `download_monitor` | 下载状态观察、完成观察时间、自动导入候选 |
| `bt_pending_state` | direct BT follow-up 中间态 |
| `watchlist_item` | 想看清单 |
| `bt_subscription_item` | BT 订阅及 last_seen 真相 |
| `adult_content_registry` | 成人资源生命周期、归档路径、保留期状态 |

## 9. 关键数据流

### 9.1 影视搜索到下载

`用户文本 -> SearchMediaService -> candidate_mapping -> 数字选择 -> AddToDownloaderService -> approval_record/jobs -> confirm -> Transmission/qBittorrent`

### 9.2 下载完成到导入

`status / scheduler -> download_monitor -> PostDownloadAutoImportService -> ImportToLibraryService -> import.succeeded -> metadata / subtitle / refresh`

### 9.3 direct BT 影视链

`magnet -> 处理链选择 -> movie/series/anime -> TMDB 关联 -> AddToDownloaderService -> 下载确认`

### 9.4 direct BT pure 链

`magnet -> 处理链选择 -> raw_bt 目录选择 -> AddToDownloaderService(auto_import_disabled) -> 下载完成后不进入媒体导入`

### 9.5 成人 BT 链

`magnet / adult candidate -> AddToDownloaderService(auto_import_disabled) -> adult_content_registry -> 下载完成 -> AdultArchiveService -> 归档 -> 保留期到期后删除下载源`

### 9.6 cleanup

`cleanup inspect / cleanup -> CleanupCorrelationLookup -> job_event(import.succeeded) -> guardrail -> delete source`

## 10. 安全与一致性机制

- `approval_record` 保存 pending / approved / cancelled、`lease_version`、`executed_version`、`expires_at`
- `jobs` 保存 `version`、`lease_owner`、`lease_until`
- `ExecutionGate` 把副作用串行化
- 取消、过期、stale confirm 都显式拒绝
- 下载器路由从 `jobs.payload_json` 读取 `downloader_name`
- 大量 repo / service 在“结果缺失、坏行、并发冲突”场景下选择 fail-closed

## 11. 当前结构性限制

- Telegram 仍是默认宿主，但代码已支持 WeCom-only / Feishu-only 的最小文本私聊 host；当前不应再把系统描述成 Telegram-only
- `shared private-chat runtime` 仍通过 `app.bot.telegram_bot` 读取大量常量和 service key
- 渠道共享的是 runtime，不是 Telegram 同级的交付能力：按钮 / callback、实时进度卡、最终总结通知当前都主要绑定 Telegram
- 若后续继续扩功能，最大的维护风险不是协议，而是 `services/` 下多个超大文件
