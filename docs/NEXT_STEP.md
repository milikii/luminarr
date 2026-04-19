# Next step (v211)

## Current goal

- 当前唯一主线：**`app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化**（2026-04-19 冷启动一致性检查已确认 `private_chat_runtime.py` 主线退出条件 2 与持久化审计条件均已满足，当前正式切线到 `After this step` 第 1 项）
- 上一条主线完成态：**`private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化已在 2026-04-19 通过 `_log_private_chat_inbound()` / `_wrap_reply_with_trace()` helper + focused tests 满足退出条件 2**
- 再上一条主线完成态：**`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化已在 2026-04-19 通过 `app/services/cleanup_correlation_lookup.py` helper 抽离满足退出条件 1**
- 更早完成态：**`manage_bt_subscription.py` 订阅编排层瘦身 / 模块化已完成**
- 更早完成态：**`search_media.py` 搜索编排层瘦身 / 模块化已完成**
- 更早完成态：**`add_to_downloader.py` 下载编排层瘦身 / 模块化已完成**
- 更早完成态：**`import_to_library.py` 导入编排层瘦身 / 模块化已完成**
- 更早完成态：**`telegram_bot.py` 渠道层瘦身 / 模块化已完成**
- 更早完成态：**独立后台下载完成轮询剩余少量回归与验证收口已完成**
- 更早完成态：**Feishu 私聊事件解析器去重已完成**
- 更早完成态：**Feishu 长连接私有 API 风险收口已完成**
- 更早完成态：**持久化吞错收口已完成**
- 更早完成态：**shared private-chat runtime 最小抽离已完成**
- 更早完成态：**cleanup 四渠道验证窗口已完成**
- 当前窗口：`2026-04-05 to 2026-04-12`（cleanup 已完成验证窗口）
- 当前主线的详细闭环、focused tests 和风险分组统一写在 `docs/APP_MAIN_SLIMMING_LOG.md`
- 上一条已完成主线的详细闭环和 focused tests 继续写在 `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`
- 再上一条已完成主线的详细闭环和 focused tests 继续写在 `docs/CLEANUP_SLIMMING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口的详细台账和证据统一写在 `docs/CLEANUP_VERIFICATION_WINDOW.md`
- 当前最小闭环：先从 `app/main.py` 的下载器路由 helper / 启动装配里选一个连贯切片拆开，优先复用 `tests/test_main.py` 和 `tests/test_telegram_bot.py` 现有入口

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线详细台账：`docs/APP_MAIN_SLIMMING_LOG.md`
- 上一条主线详细台账：`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`
- 再上一条主线详细台账：`docs/CLEANUP_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/SEARCH_MEDIA_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线详细台账：`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线详细台账：`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线详细台账：`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 继续收口 `app/main.py` 的一个连贯切片；每轮只做一个最小闭环，不顺手清理不相关模块
- 保持 Telegram / personal WeChat / Feishu / WeCom 四个渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持当前已经落下来的 cleanup / search / approval / import / btsub 边界不回退：
  - cleanup inspect 继续只读，不删除任何文件
  - cleanup execution 继续只删除 downloader/source 侧资产，不删库内目标、sidecar 或其他任务文件
  - pending state gate、guardrail 拒绝、事件落盘失败继续显式中文日志 + `[处理建议]`
- 涉及真实 downloader / import / refresh 行为的任务，继续使用本地 Transmission / Emby 联调栈验证；当前主线本身只做启动装配与路由瘦身，不扩成新的下载、导入或刷新副作用闭环
- 文档继续分层：
  - `docs/STATUS.md` 只保留当前快照
  - `docs/APP_MAIN_SLIMMING_LOG.md` 承接当前主线详细闭环
  - `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md` 保留上一条主线已完成台账
  - `docs/CLEANUP_SLIMMING_LOG.md` 保留再上一条主线已完成台账
  - `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md` 保留更早主线已完成台账
  - `docs/SEARCH_MEDIA_SLIMMING_LOG.md` 保留更早主线已完成台账
  - `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` 保留更早主线已完成台账
  - `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` 保留更早主线已完成台账
  - `docs/TELEGRAM_BOT_SLIMMING_LOG.md` 保留更早主线已完成台账
  - `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md` 保留更早主线已完成台账
  - `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md` 保留更早主线已完成台账
  - `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md` 保留更早主线已完成台账
  - `docs/PERSISTENCE_CLOSURE_LOG.md` 保留更早主线已完成台账
  - `docs/CLEANUP_VERIFICATION_WINDOW.md` 只承接 cleanup 已完成窗口证据
- 新闭环按主题合并进 `docs/APP_MAIN_SLIMMING_LOG.md` 2.1~2.3 已有分组，**不再开新的 `### 2026-xx-xx 分流缺口` 小节；`STATUS.md` 只补一句当前结论或风险，不逐天追加 `截至 ...` 条目**
- 保持 cleanup 完成态文档结论稳定：`README.md`、`docs/NEXT_STEP.md`、`docs/STATUS.md` 不要回退成“cleanup 验证窗口仍在进行中”或“cleanup 主线仍在进行中”
- 保持 verification docs gate 可持续通过；当前 docs gate 只需要锁住入口一致性、状态页短快照结构、固定验证快照和当前主线台账入口

## Do not do

- 不把 `app/main.py` 借机重构成新的容器框架、通用依赖注入平台或新的生命周期系统
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不在这一步引入自动 `confirm`、自动下载、series / anime 新解析能力、cleanup 新 workflow、shared private-chat 体验 polish、Jellyfin / Plex 支持或其他新集成
- 不回退现有 cleanup / search / approval / import / status / watchlist / btsub 文本协议

## Done when

当前主线视为 **已基本完成**，触发以下任一可测量条件即停止，并通知用户切换到下面 `After this step` 第 2 项：

1. `app/main.py` 里的下载器路由查询 / client 解析 / status/import source 路由已抽到一组连贯 helper 或等价统一边界，且 `.venv/bin/python -m pytest -q tests/test_main.py -k "resolve_downloader_name_for_task or resolve_downloader_client_for_lookup or resolve_downloader_client_for_dispatch or get_torrent_status_with_routing or get_torrent_import_source_with_routing"` 全绿；
2. 或者 `app/main.py` 里的 client 装配、可选渠道 bot_data 绑定或启动入口日志已抽到一组连贯 helper / 等价统一边界，且 `.venv/bin/python -m pytest -q tests/test_main.py tests/test_telegram_bot.py -k "run_application_polling or build_application"` 全绿；
3. 或者本轮候选闭环的代码变更 **< 20 行**、本质只是为同一个 repo API 再拆一条 `if/elif/log` 诊断分支（收益递减），且上一轮也是同类微闭环，此时视为已越过完成线，直接停止。

满足其中任一条时，直接回到本文件 `After this step` 第 2 项（`series / anime` 独立名称解析最小实现）。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `verification docs gate` 与 cleanup 完成态证据持续通过
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `docs/APP_MAIN_SLIMMING_LOG.md` / `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md` / `docs/CLEANUP_SLIMMING_LOG.md` / `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md` / `docs/SEARCH_MEDIA_SLIMMING_LOG.md` / `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` / `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` / `docs/TELEGRAM_BOT_SLIMMING_LOG.md` / `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md` / `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md` / `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md` / `docs/PERSISTENCE_CLOSURE_LOG.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 继续保持分层一致，不重新写回长台账

## After this step

1. `app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化：当前正在做；把 client 装配、后台任务启停、下载器路由 helper 和启动日志继续拆开；目标是不改启动入口、角色绑定和现有运行时真相。施工纪律见 `docs/SLIMMING_RULES.md`
2. `series / anime` 独立名称解析最小实现（结构化解析 + 小型识别词/替换配置）——详细蓝图见 `docs/SERIES_ANIME_NAMING_PLAN.md`
3. `.ass` 字幕支持评估与最小实现——合并在 `docs/SERIES_ANIME_NAMING_PLAN.md` §7 同步落地
4. shared private-chat 交付体验收口（图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI）——详细蓝图见 `docs/SHARED_DELIVERY_UX_PLAN.md`
5. 最小人类可用入口继续补齐（quick start / 配置模板 / 首个渠道 10 分钟跑通）——详细蓝图见 `docs/QUICK_START_PLAN.md`
6. BT 共享确定性评分器——详细蓝图见 `docs/BT_SCORING_PLAN.md`
7. Jellyfin / Plex 支持（后续）
8. plugin 体系继续后置
