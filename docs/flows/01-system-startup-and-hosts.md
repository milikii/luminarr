# System Startup And Hosts

> 主要依据：`app/main.py`、`app/bot/telegram_runtime_adapter.py`、`app/bot/telegram_sidecar_runtime.py`、`app/bot/non_telegram_runtime_host.py`

## 1. 启动入口

应用从 `app/main.py:main()` 启动，启动顺序固定为：

1. `load_settings()` 读取并校验环境变量
2. `_resolve_runtime_host_mode()` 决定宿主模式
3. `SqliteDatabase.initialize()` 初始化 / 补齐表结构
4. 创建 repo
5. 创建外部 client
6. 创建业务 service
7. 创建运行时宿主
8. 注入 sidecar 所需 `bot_data`
9. 启动 Telegram polling 或非 Telegram host 生命周期

## 2. 宿主模式判定

`_resolve_runtime_host_mode()` 的优先级是：

1. 有 `TELEGRAM_BOT_TOKEN` -> `telegram`
2. 否则有 WeCom 宿主配置 -> `wecom`
3. 否则有 Feishu 宿主配置 -> `feishu`
4. 都没有 -> 启动失败

这意味着：

- Telegram 仍是默认宿主。
- WeCom-only / Feishu-only 可以启动，但它们不是完整复制 Telegram 宿主，而是走 `NonTelegramRuntimeHost`。

## 3. 启动时装配的核心对象

### 3.1 SQLite repo

启动即创建这些持久化边界：

- `CandidateMappingRepo`
- `ClarificationRepo`
- `ApprovalRepo`
- `JobRepo`
- `JobEventRepo`
- `DownloadMonitorRepo`
- `BtPendingRepo`
- `BtSubscriptionRepo`
- `AdultContentRegistryRepo`
- `AdultDuplicateMemorySnapshotRepo`
- `TelegramUpdateRepo`
- `WatchlistRepo`

### 3.2 外部 client

按配置条件装配：

- 搜索 / 元数据：`ProwlarrClient`、`TmdbClient`、`FanartClient`、`WebSourceClient`
- 下载器：legacy `TransmissionClient` + 多实例 `TransmissionClient` / `QbittorrentClient`
- 刷库：`EmbyClient` / `JellyfinClient` / `PlexClient`
- 渠道：`FeishuClient`
- 成人只读 helper：Avmoo / Avsox / JavBus / JavLibrary / Caribbeancom

### 3.3 业务 service

主链路服务在启动时全部组装好：

- `SearchMediaService`
- `AddToDownloaderService`
- `ImportToLibraryService`
- `PostDownloadAutoImportService`
- `GetDownloadStatusService`
- `CleanupDownloadedSourceService`
- `ManageWatchlistService`
- `ManageBtSubscriptionService`
- `AdultArchiveService`

## 4. 下载器路由不是硬编码单实例

`main()` 会同时构造：

- legacy `transmission_client`
- `downloader_instances_by_name`
- `transmission_clients_by_name`
- `qbittorrent_clients_by_name`

之后所有下载、状态、导入源、删除动作都经过 routing helper：

- `add_torrent_with_routing()`
- `get_torrent_status_with_routing()`
- `get_torrent_import_source_with_routing()`
- `remove_torrent_with_routing()`

因此业务层知道“任务引用”，不直接依赖某个固定下载器对象。

## 5. Telegram 宿主和非 Telegram 宿主的差异

### Telegram 模式

`build_telegram_application()` 会：

- 创建 PTB `Application`
- 注册 message handler 和 callback query handler
- 把 service / repo / sender / execution gate 全部塞进 `application.bot_data`
- 把 sidecar 生命周期绑到 `post_init` / `post_shutdown`

### 非 Telegram 模式

`NonTelegramRuntimeHost` 只提供两件事：

- `bot_data`
- `create_task()` / `wait_until_stopped()`

随后 `main()` 通过 `_populate_non_telegram_runtime_bot_data()` 手动注入 shared runtime 所需依赖，再运行 `_run_non_telegram_host()`。

## 6. Sidecar 生命周期

sidecar 统一由 `app/bot/telegram_sidecar_runtime.py` 管理。

### Telegram host 启动时

会启动：

- WeCom webhook server
- Feishu 长连接
- personal WeChat 私聊轮询
- post-download auto-import scheduler
- BT subscription scheduler
- download completion polling

### 非 Telegram host 启动时

会启动：

- WeCom webhook server
- Feishu 长连接
- post-download auto-import scheduler
- BT subscription scheduler

不会启动 personal WeChat 轮询。

## 7. 主动通知能力的真实边界

宿主会尝试注入统一的 `SIDECAR_HOST_SEND_TEXT_FUNC_KEY`。

当前可主动发送的渠道实现是：

- Telegram
- Feishu
- personal WeChat

WeCom 当前仍能接收入站，但 `build_shared_private_chat_send_text_func()` 对 WeCom 主动发送直接报 unsupported。这意味着：

- WeCom 私聊入口能用 shared runtime
- 但部分后台主动通知不能像 Telegram / Feishu / personal WeChat 那样稳定复用

## 8. 启动流程图

```mermaid
flowchart TD
    A[main()] --> B[load_settings]
    B --> C[resolve host mode]
    C --> D[initialize SQLite schema]
    D --> E[create repos]
    E --> F[create clients]
    F --> G[create services]
    G --> H{telegram host?}
    H -- yes --> I[build PTB Application]
    H -- no --> J[build NonTelegramRuntimeHost]
    I --> K[inject bot_data]
    J --> K
    K --> L[inject channel services and proactive senders]
    L --> M{telegram host?}
    M -- yes --> N[run_polling]
    M -- no --> O[start non-telegram sidecar lifecycle]
```

## 9. 启动阶段最关键的设计结论

- 启动不是“按渠道分叉业务”，而是“先把共用 service 装好，再选择一个宿主容器”。
- sidecar 和 scheduler 不是第二进程，而是宿主生命周期上的后台 task。
- 绝大多数后续流程都依赖 `bot_data` 注入，因此“服务是否就绪”本质上是启动装配是否完成。
