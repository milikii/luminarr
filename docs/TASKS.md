# Luminarr 任务清单

> 我正在使用 `superpowers:writing-plans` 基于 `docs/PRD.md`、`docs/ARCHITECTURE.md` 和当前已批准的 Stage 1 设计拆解任务。  
> 本清单按 2026-04-30 当前仓库真相标注状态；执行阶段始终从第一个 `状态：未完成` 的任务开始。

## 使用说明

- `[x]` 已完成：当前仓库已有实现，且已有测试或验证入口保护。
- `[ ]` 未完成：当前仍需推进；执行阶段默认从编号最小的未完成任务开始。
- 若继续扩 `BT subscription`，只允许服务成人 BT 连续追踪；不引入影视 BT、动漫 BT、`raw_bt subscription`，也不放宽 `confirm` 边界。
- `watchlist` 继续只做手动清单，不桥接成自动下载或 BT 订阅。
- `direct BT` / `magnet:?` 继续先问 `观影 PT 链` 或 `BT 成人链`，不允许默认落到成人 BT。

## 任务列表

### T01 `[x]` 启动装配与能力化配置

- 任务描述：
  让 `app/main.py`、`app/config.py` 和运行时宿主按能力装配应用，只对已启用能力要求必填配置，并在启动时完成数据库、repo、client、service 和宿主初始化。
- 关键触点：
  `app/main.py`、`app/config.py`、`.env.example`
- 完成标准：
  - `load_settings()` 对 Telegram、Prowlarr、下载器、媒体服务器和各渠道凭据按能力 fail-closed 校验，而不是对未启用能力一律硬必填。
  - 启动阶段会初始化 PRD/ARCHITECTURE 约定的 SQLite 真相层、repo、外部 client 和业务 service。
  - Telegram、Feishu-only、WeCom-only 的最小宿主路径已经存在，缺少必需能力时会明确拒绝启动。
- 依赖的前置任务：
  无

### T02 `[x]` SQLite 真相层与 Repo 边界

- 任务描述：
  建立并稳定维护 `candidate_mapping`、`clarification_state`、`approval_record`、`jobs`、`job_event`、`download_monitor`、`bt_pending_state`、`watchlist_item`、`bt_subscription_item`、`adult_content_registry`、`telegram_updates` 等持久化真相。
- 关键触点：
  `app/db/sqlite.py`、`app/db/*.py`
- 完成标准：
  - 表结构和 repo API 与 `docs/ARCHITECTURE.md` 第 4.1 节、第 8 节一致。
  - 搜索、确认、状态、导入、cleanup、watchlist、btsub 都能从持久化数据重建最小执行上下文。
  - repo 层对坏行、缺失结果、并发冲突保持 fail-closed，不出现静默成功。
- 依赖的前置任务：
  T01

### T03 `[x]` Shared Private-Chat Runtime 与 ExecutionGate

- 任务描述：
  把 Telegram、personal WeChat、Feishu、WeCom 的私聊文本统一投影到 shared runtime，并由 `ExecutionGate` 串行化副作用操作。
- 关键触点：
  `app/bot/private_chat_runtime.py`、`app/runtime/execution_policy.py`、`app/runtime/delivery.py`
- 完成标准：
  - 四个渠道都统一投影成 `query`、`chat_id`、`user_id`、`channel`、`reply_func` 后再进入业务链。
  - 路由顺序与 `docs/ARCHITECTURE.md` 第 5 节一致，覆盖取消、BT follow-up、execution-gated 命令、`confirm`、数字选片和搜索 fallback。
  - 只读操作可直接放行，副作用操作会被串行化，重复或 stale 执行会被明确拒绝。
- 依赖的前置任务：
  T01、T02

### T04 `[x]` 搜索、候选映射与歧义澄清

- 任务描述：
  实现自然语言影视搜索、BT 只读搜索、排序去重、TMDB 增强、候选缓存和歧义澄清，使用户可以先看候选再做选择。
- 关键触点：
  `app/services/search_media.py`、`app/services/search_reply_formatter.py`、`app/db/candidate_repo.py`、`app/db/clarification_repo.py`
- 完成标准：
  - 自然语言搜索会联合 Prowlarr、TMDB 和必要的 BT 只读来源生成候选结果。
  - 搜索结果会被排序、去重、格式化，并写入 `candidate_mapping` 供后续数字选择。
  - 结果歧义过高时会进入 `clarification_state`，而不是盲目返回候选或直接触发副作用。
- 依赖的前置任务：
  T02、T03

### T05 `[x]` 下载审批与下载器投递

- 任务描述：
  把候选资源、直接链接或 direct BT 来源统一落成待确认下载任务，并在 `confirm` 后按任务真相投递到 Transmission 或 qBittorrent。
- 关键触点：
  `app/services/add_to_downloader.py`、`app/services/add_pending_context.py`、`app/clients/transmission.py`、`app/clients/qbittorrent.py`
- 完成标准：
  - 下载请求会先写入 `approval_record`、`jobs` 和 `job_event`，不会直接触发下载器副作用。
  - `confirm <任务引用>` 后才会真正投递下载器，并把实际下载信息登记到 `download_monitor`。
  - 下载器路由会从持久化任务真相恢复，不依赖临时内存状态或渠道专属分支。
- 依赖的前置任务：
  T03、T04

### T06 `[x]` 下载状态观察、完成事件与自动跟进

- 任务描述：
  提供 `status` 查询、下载完成观察、完成事件记账，以及普通内容自动导入和成人内容归档分流。
- 关键触点：
  `app/services/get_download_status.py`、`app/services/post_download_auto_import.py`、`app/db/download_monitor_repo.py`
- 完成标准：
  - `status <任务ID或Hash>` 可以查询下载器实际状态，并把观察结果写回 `download_monitor`。
  - 首次观察到完成时只会记录一次完成事件，不会重复写入完成真相。
  - 普通内容会进入自动导入跟进，成人内容会进入成人归档支线，低质量资源会被显式跳过。
- 依赖的前置任务：
  T05

### T07 `[x]` 入库审批、copy-fallback 与后处理链

- 任务描述：
  为已完成下载任务提供导入待确认、硬链接导入、跨文件系统复制兜底，以及 metadata、字幕、媒体库刷新后处理。
- 关键触点：
  `app/services/import_to_library.py`、`app/services/import_transfer_execution.py`、`app/services/import_post_processing.py`
- 完成标准：
  - `import <任务引用>` 会先创建待确认导入；`raw_bt` 任务会被确定性阻断。
  - 确认导入默认走硬链接；跨文件系统时会进入显式 `copy-fallback pending`，必须再次确认才允许复制。
  - 导入成功会写入 `import.succeeded` 及 source/target/media identity 真相，并继续执行 metadata scraping、字幕翻译和媒体库刷新。
- 依赖的前置任务：
  T05、T06

### T08 `[x]` Direct BT 处理链、TMDB 关联与成人 BT 生命周期

- 任务描述：
  支持 direct `BT` / `magnet:?` 入口的处理链选择、媒体类型选择、TMDB 关联、pure BT 目录选择，以及成人 BT 的历史登记、归档和保留期清理。
- 关键触点：
  `app/bot/private_chat_bt_*_runtime.py`、`app/services/pure_bt.py`、`app/services/adult_archive_service.py`、`app/services/adult_content.py`
- 完成标准：
  - direct BT 入口会先问 `观影 PT 链` 或 `BT 成人链`，不会默认跳成人链。
  - 影视入库链会继续做 `movie / series / anime` 选择和 TMDB 关联；pure BT 会要求选择预设下载目录并保持不进入媒体入库链。
  - 成人 BT 会写入历史真相，并在下载完成后进入归档、保留期和清理支线。
  - BT 只读搜索、批量预览和批量确认能力可用，但仍受既有审批边界保护。
- 依赖的前置任务：
  T03、T05、T06、T07

### T09 `[x]` Cleanup 下载源保护链

- 任务描述：
  基于 `import.succeeded` 的 source/target 关联，提供 `cleanup inspect` 的只读预检和 `cleanup` 的真实删除，并加上路径与做种保护。
- 关键触点：
  `app/services/cleanup_downloaded_source.py`、`app/services/cleanup_correlation_lookup.py`
- 完成标准：
  - `cleanup inspect` 只做只读检查，明确展示 source、target 和 guardrail 结论。
  - `cleanup` 必须依赖最近一次 `import.succeeded` 关联真相，不允许脱离导入事件盲删。
  - 路径保护、目标存在性检查和 PT 最小做种窗口保护均已生效。
- 依赖的前置任务：
  T07

### T10 `[x]` Watchlist 与成人 BT Subscription 基线

- 任务描述：
  保持 `watchlist` 作为手动持久化清单，并把 `btsub` 锁定在当前已决定的成人 BT 连续追踪边界内。
- 关键触点：
  `app/services/manage_watchlist.py`、`app/services/manage_bt_subscription.py`、`app/services/bt_subscription_candidate_helpers.py`
- 完成标准：
  - `watchlist` 支持 `list/add/remove/clear`，只做持久化，不自动下载；`watchlist sync` / `想看 同步` 继续 fail-closed，不桥接到 BT 订阅。
  - `btsub` 支持 `list/add/remove/clear/run` 和 scheduler tick；命中新资源后仍然必须进入现有 downloader approval -> `confirm` 边界。
  - `btsub add` 当前只接受成人 BT 精确番号追踪；旧的非成人订阅条目会显式告警并跳过扫描。
  - 同标题但不同 URL 的镜像命中不会重复创建新的下载待确认，`btsub list` 会展示“上次命中资源”。
- 依赖的前置任务：
  T03、T05、T08

### T11 `[x]` 多渠道私聊文本入口与宿主边界

- 任务描述：
  保持 Telegram、personal WeChat、Feishu、WeCom 四条私聊文本入口共用同一套 runtime，同时把 sidecar/scheduler 生命周期收口成通用宿主边界。
- 关键触点：
  `app/bot/telegram_runtime_adapter.py`、`app/bot/personal_wechat_text.py`、`app/bot/feishu_adapter.py`、`app/bot/wecom_adapter.py`、`app/bot/sidecar_host_runtime.py`
- 完成标准：
  - 四个渠道都通过各自适配层接入 shared private-chat runtime，而不是分叉业务逻辑。
  - Telegram 仍可作为 PTB 宿主；Feishu-only、WeCom-only 的最小文本私聊启动路径已经存在。
  - sidecar 和 scheduler 生命周期已抽成通用 host 边界，渠道差异主要留在适配层和发送层。
- 依赖的前置任务：
  T01、T03

### T12 `[x]` 质量 Gate、Docs Gate 与回归基线

- 任务描述：
  建立 `make quality`、`make lint`、`make verify-mainline`、`make verify-adult-bt-wedge` 等验证入口，并用测试保护核心文档和主线行为。
- 关键触点：
  `Makefile`、`tests/`、`docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/INDEX.md`
- 完成标准：
  - `make quality`、`make lint`、`make verify-mainline` 当前可通过，并覆盖主线质量门禁。
  - 成人 BT 专线已有 focused 验证入口 `make verify-adult-bt-wedge`。
  - 文档一致性测试已经保护 `AGENTS.md`、`INDEX.md`、`STATUS.md`、`NEXT_STEP.md` 等当前真相入口。
- 依赖的前置任务：
  T01、T03、T04、T05、T06、T07、T08、T09、T10、T11

### T13 `[x]` 成人 BT 连续追踪收尾与实机验证

- 任务描述：
  继续沿当前唯一主线收尾成人 BT 专线，只允许在成人 BT 连续追踪边界内补最小 contract 或实机验证，不回切影视 BT、动漫 BT、`raw_bt subscription` 或 auto-confirm。
- 关键触点：
  `app/services/manage_bt_subscription.py`、`app/services/bt_subscription_candidate_helpers.py`、`app/bot/private_chat_bt_subscription_runtime.py`、`docs/STATUS.md`、`docs/NEXT_STEP.md`
- 完成标准：
  - 若继续改 `btsub`，变更只服务成人 BT 精确番号连续追踪，不引入任何影视资源订阅或 `raw_bt subscription`。
  - direct BT / `magnet:?` 入口仍然保留 `观影 PT 链 / BT 成人链` 问询，不会默认进入成人链。
  - 完成至少一轮 Telegram 实机 smoke 或等价真实链路验证，确认当前成人 BT 主线没有回退。
  - 变更完成后 `make quality`、`make lint`、`make verify-mainline`、`make verify-adult-bt-wedge` 继续通过，且 `docs/STATUS.md` / `docs/NEXT_STEP.md` 与实现保持一致。
- 依赖的前置任务：
  T08、T10、T11、T12

### T14 `[x]` 运行时外部依赖真相页收口

- 任务描述：
  把 `ffmpeg` / `ffprobe`、personal WeChat 登录态目录、Feishu SDK、WeCom 回调端口与反代要求等运行依赖收敛到单一运维真相页，减少文档分散和口径漂移。
- 关键触点：
  `docs/GETTING_STARTED.md`、`docs/OPERATOR_RUNBOOK.md`、`docs/STATUS.md`
- 完成标准：
  - 运行依赖、安装前提和渠道特有部署要求有且只有一个主真相入口。
  - `README.md`、`INDEX.md`、`GETTING_STARTED.md`、`STATUS.md` 对该真相页的引用关系清楚，不重复堆砌冲突信息。
  - 若新增或调整文档入口，docs gate 会同步更新，避免再次出现入口文档失真。
- 依赖的前置任务：
  T01、T11、T12

### T15 `[x]` 剩余结构性维护风险收口

- 任务描述：
  在不改变 PRD 边界、不改 SQLite 真相和外部协议的前提下，继续降低超大 service 文件与残余渠道耦合带来的维护风险。
- 关键触点：
  `app/services/`、`app/bot/private_chat_runtime.py`、`app/bot/telegram_bot.py`、`docs/ARCHITECTURE.md`
- 完成标准：
  - 选择单个、低风险、可验证的切口继续拆分超大文件或残余 helper 耦合，不顺手重构整仓。
  - 行为保持不变，相关 focused tests、`make quality`、`make lint`、`make verify-mainline` 继续通过。
  - 如果代码边界发生可感知变化，`docs/ARCHITECTURE.md` 与相关执行文档会同步更新。
- 依赖的前置任务：
  T03、T08、T10、T11、T12

### T16 `[x]` 成人 BT 下载前防重记忆层

- 任务描述：
  在 `AddToDownloaderService` shared path 前增加 adult-only duplicate memory gate，把本地成人目录、`adult_content_registry` 和旧任务事件聚合成统一记忆层；命中旧番号时先强提醒，再让操作者显式继续。
- 关键触点：
  `app/db/sqlite.py`、`app/db/adult_duplicate_memory_snapshot_repo.py`、`app/services/adult_duplicate_memory.py`、`app/services/add_to_downloader.py`、`app/bot/private_chat_runtime.py`
- 完成标准：
  - 新增 sibling snapshot 真相 `adult_duplicate_memory_snapshot`，且 repo 能 round-trip。
  - duplicate memory 只对带 `adult_content_id` / `normalized_content_id` 的成人 BT 路径生效，且 exact 命中强制复用 `extract_exact_adult_content_match`。
  - direct BT、批量选择、`btsub` 命中创建待确认前都会先过同一层 duplicate gate。
  - duplicate 命中时不会直接创建下载待确认，而是进入显式 `duplicate_override` follow-up；异常时显式降级，不静默跳过。
  - focused tests、`make quality`、`make verify-mainline`、`make verify-adult-bt-wedge`、`make lint` 继续通过。
- 依赖的前置任务：
  T05、T08、T10、T12

### T17 `[x]` Telegram-first 高频主链交付层

- 任务描述：
  只针对 Telegram 高频主链，把搜索结果、下载确认、导入确认、状态反馈和关键 BT follow-up 收口成更直接的 Telegram-first 交付层；其他渠道继续保留文本 fallback，不追求一轮内同时追平。
- 关键触点：
  `app/runtime/delivery.py`、`app/bot/telegram_delivery_runtime.py`、`app/bot/telegram_runtime_adapter.py`、`app/services/search_reply_formatter.py`、`app/services/add_to_downloader.py`、`app/services/get_download_status.py`
- 完成标准：
  - Telegram 能为高频主链消息提供更直接的动作区，不再只依赖长文本手输命令。
  - shared delivery intent 继续可被 Feishu / WeCom / personal WeChat 渲染成稳定文本 fallback，不分叉业务真相。
  - duplicate memory 的提醒与显式继续语义要并入 Telegram 主体验，不允许形成平行支线。
  - focused tests 与主线回归继续通过。
- 依赖的前置任务：
  T03、T04、T05、T06、T07、T12、T16

### T18 `[x]` 成人 BT 来源角色底座

- 任务描述：
  把成人 BT 来源固定成可持续扩站的底座，显式区分主力 BT、辅助 PT 成人站点和 helper-only，只让 helper 做只读补全，不再混进主下载语义。
- 关键触点：
  `app/services/bt_sources.py`、`app/clients/web_source.py`、`app/services/search_media.py`、`app/services/bt_read_only_display.py`、`app/main.py`
- 完成标准：
  - 来源角色真相稳定存在，后续扩站不需要重写搜索、排序和交付语义。
  - `javlibrary` 继续锁定为 helper-only，只做只读补全，不进入主动下载来源。
  - 成人 BT 结果排序、说明文案和 helper-only 行为一致，不回切到“几个零散站点脚本”的状态。
  - focused tests 与主线回归继续通过。
- 依赖的前置任务：
  T04、T08、T12、T16、T17

### T19 `[x]` Stage 1 聚合验证与运维真相同步

- 任务描述：
  在 `T16`、`T17`、`T18` 分别完成后，补一轮 Stage 1 focused 验证矩阵与 operator 文档真相同步，确保新主线不是只在开发者上下文里成立。
- 关键触点：
  `Makefile`、`tests/`、`docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/GETTING_STARTED.md`、`docs/OPERATOR_RUNBOOK.md`
- 完成标准：
  - Stage 1 focused verification 入口可重复运行，并覆盖 duplicate memory、Telegram-first 高频链和来源角色底座。
  - `docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/GETTING_STARTED.md` 与实现状态一致，不再保留“冻结态”口径。
  - 真实 Telegram 操作路径至少补一轮新的实机 smoke 或等价证据。
  - `make quality`、`make verify-mainline`、`make verify-adult-bt-wedge`、`make lint` 继续通过。
- 依赖的前置任务：
  T16、T17、T18

## 当前第一个未完成任务

- 当前没有未完成执行任务；进入收尾阶段。
