# Next step (v215)

## Current goal

- 当前唯一主线：**`series / anime` 独立名称解析最小实现（含 `.ass` 最小支持评估）**（2026-04-19 已在 `app/main.py` 主线通过 `app/downloader_route_lookup.py` helper + focused tests 满足退出条件 1 后切到本线）
- 上一条主线完成态：**`app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化已在 2026-04-19 通过 `app/downloader_route_lookup.py` helper + focused tests 满足退出条件 1**
- 再上一条主线完成态：**`private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化已在 2026-04-19 通过 `_log_private_chat_inbound()` / `_wrap_reply_with_trace()` helper + focused tests 满足退出条件 2**
- 更早完成态：**`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化已在 2026-04-19 通过 `app/services/cleanup_correlation_lookup.py` helper 抽离满足退出条件 1**
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
- 当前主线的设计蓝图统一写在 `docs/SERIES_ANIME_NAMING_PLAN.md`
- 当前主线的详细闭环、focused tests 和风险分组统一写在 `docs/SERIES_ANIME_NAMING_LOG.md`
- 上一条已完成主线的详细闭环和 focused tests 继续写在 `docs/APP_MAIN_SLIMMING_LOG.md`
- 再上一条已完成主线的详细闭环和 focused tests 继续写在 `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`
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
- 当前最小闭环：继续收口 `docs/SERIES_ANIME_NAMING_PLAN.md` Phase 3 剩余接点；当前已把 `search_request_context`、BT source adapter、`import_to_library` 命名 helper 接到统一 parser，下一步补下载完成后的剩余消费点并跑 Phase 3 focused suite，不改现有 movie-first 行为

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线蓝图：`docs/SERIES_ANIME_NAMING_PLAN.md`
- 当前主线详细台账：`docs/SERIES_ANIME_NAMING_LOG.md`
- 上一条主线详细台账：`docs/APP_MAIN_SLIMMING_LOG.md`
- 再上一条主线详细台账：`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`
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

- 继续收口 `series / anime` 名称解析的一个最小 Phase；每轮只做一个最小闭环，不顺手清理不相关模块
- 保持 Telegram / personal WeChat / Feishu / WeCom 四个渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持当前已经落下来的 cleanup / search / approval / import / btsub 边界不回退：
  - cleanup inspect 继续只读，不删除任何文件
  - cleanup execution 继续只删除 downloader/source 侧资产，不删库内目标、sidecar 或其他任务文件
  - pending state gate、guardrail 拒绝、事件落盘失败继续显式中文日志 + `[处理建议]`
- 涉及真实 downloader / import / refresh 行为的任务，继续使用本地 Transmission / Emby 联调栈验证；当前主线优先做 parser 和集成点切换，不扩成新的下载、导入或刷新副作用闭环
- 文档继续分层：
  - `docs/STATUS.md` 只保留当前快照
  - `docs/SERIES_ANIME_NAMING_PLAN.md` 承接当前主线蓝图
  - `docs/SERIES_ANIME_NAMING_LOG.md` 承接当前主线详细闭环
  - `docs/APP_MAIN_SLIMMING_LOG.md` 保留上一条主线已完成台账
  - `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md` 保留再上一条主线已完成台账
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
- 新闭环按主题合并进 `docs/SERIES_ANIME_NAMING_LOG.md` 2.1~2.3 已有分组，**不再开新的 `### 2026-xx-xx 分流缺口` 小节；`STATUS.md` 只补一句当前结论或风险，不逐天追加 `截至 ...` 条目**
- 保持 cleanup 完成态文档结论稳定：`README.md`、`docs/NEXT_STEP.md`、`docs/STATUS.md` 不要回退成“cleanup 验证窗口仍在进行中”或“cleanup 主线仍在进行中”
- 保持 verification docs gate 可持续通过；当前 docs gate 只需要锁住入口一致性、状态页短快照结构、固定验证快照和当前主线台账入口

## Do not do

- 不把 `series / anime` 主线借机扩成通用规则引擎、通用 DSL 或新的 LLM 猜测平台
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不在这一步引入自动 `confirm`、自动下载、series / anime 新解析能力、cleanup 新 workflow、shared private-chat 体验 polish、Jellyfin / Plex 支持或其他新集成
- 不回退现有 cleanup / search / approval / import / status / watchlist / btsub 文本协议

## Done when

当前主线视为 **已基本完成**，触发以下任一可测量条件即停止，并通知用户切换到下面 `After this step` 第 1 项：

1. `docs/SERIES_ANIME_NAMING_PLAN.md` §6 四处集成点都已切到 `ParsedMediaName`，且 `.venv/bin/python -m pytest -q tests/test_media_name_parser.py tests/test_search_media.py tests/test_import_to_library.py tests/test_post_download_auto_import.py tests/test_subtitle_translator.py` 全绿；
2. 或者 `docs/SERIES_ANIME_NAMING_PLAN.md` Phase 1-5 已完成 3 个，剩余 2 个都涉及产品决策（例如 clarification 分流文案），此时停下来请用户确认；
3. 或者本轮代码改动 **< 20 行**、只是对同一个规则表再加一条 `strip_tag` / `alt_title`（收益递减），此时走 `AGENTS.md §11` 停机规则。

满足其中任一条时，直接回到本文件 `After this step` 第 1 项（shared private-chat 交付体验收口）。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `verification docs gate` 与 cleanup 完成态证据持续通过
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `docs/SERIES_ANIME_NAMING_PLAN.md` / `docs/SERIES_ANIME_NAMING_LOG.md` / `docs/APP_MAIN_SLIMMING_LOG.md` / `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md` / `docs/CLEANUP_SLIMMING_LOG.md` / `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md` / `docs/SEARCH_MEDIA_SLIMMING_LOG.md` / `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` / `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` / `docs/TELEGRAM_BOT_SLIMMING_LOG.md` / `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md` / `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md` / `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md` / `docs/PERSISTENCE_CLOSURE_LOG.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 继续保持分层一致，不重新写回长台账

## After this step

1. shared private-chat 交付体验收口（图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI）——详细蓝图见 `docs/SHARED_DELIVERY_UX_PLAN.md`
2. 最小人类可用入口继续补齐（quick start / 配置模板 / 首个渠道 10 分钟跑通）——详细蓝图见 `docs/QUICK_START_PLAN.md`
3. BT 共享确定性评分器——详细蓝图见 `docs/BT_SCORING_PLAN.md`
4. Jellyfin / Plex 支持（后续）
5. plugin 体系继续后置
