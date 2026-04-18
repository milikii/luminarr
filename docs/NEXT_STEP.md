# Next step (v208)

## Current goal

- 当前唯一主线：**`manage_bt_subscription.py` 订阅编排层瘦身 / 模块化**
- 上一条主线完成态：**`search_media.py` 搜索编排层瘦身 / 模块化已完成**
- 更早完成态：**`add_to_downloader.py` 下载编排层瘦身 / 模块化已完成**
- 更早完成态：**`import_to_library.py` 导入编排层瘦身 / 模块化已完成**
- 更早完成态：**`telegram_bot.py` 渠道层瘦身 / 模块化已完成**
- 更早完成态：**独立后台下载完成轮询剩余少量回归与验证收口已完成**
- 更早完成态：**Feishu 私聊事件解析器去重已完成**
- 更早完成态：**Feishu 长连接私有 API 风险收口已完成**
- 更早完成态：**持久化吞错收口已完成**
- 更早完成态：**shared private-chat runtime 最小抽离已完成**
- 更早完成态：**cleanup 四渠道验证窗口已完成**
- 当前窗口：`2026-04-05 to 2026-04-12`（上一条 cleanup 主线的完成窗口）
- 当前主线的详细闭环、focused tests 和风险分组统一写在 `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`
- 上一条主线的详细闭环和 focused tests 继续写在 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口的详细台账和证据统一写在 `docs/CLEANUP_VERIFICATION_WINDOW.md`
- 当前最小闭环：每轮只收 `manage_bt_subscription.py` 里的一个连贯切片，优先处理清单增删 / 标题解析 / 回复文本，或扫描候选筛选 / `last_seen` 更新 / scheduler tick 中的一组，不改 `bt_subscription_item` 真相、downloader approval 边界和自动扫描停路规则

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线详细台账：`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`
- 上一条主线详细台账：`docs/SEARCH_MEDIA_SLIMMING_LOG.md`
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

- 继续收口 `manage_bt_subscription.py` 的一个连贯切片；每轮只做一个最小闭环，不顺手清理不相关模块
- 保持 Telegram / personal WeChat / Feishu / WeCom 四个渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持当前已经落下来的 BT 订阅边界不回退：
  - 命中新资源后仍必须走现有 downloader approval -> `confirm` 边界
  - `last_seen` 写入失败继续显式中文日志 + `[处理建议]`，不把坏真相误判成“已完成追踪”
  - scheduler tick 继续只做确定性扫描和 follow-up，不依赖 LLM
- 涉及真实 downloader / import / refresh 行为的任务，继续使用本地 Transmission / Emby 联调栈验证；当前主线本身不扩成新的下载、导入或刷新副作用闭环
- 文档继续分层：
  - `docs/STATUS.md` 只保留当前快照
  - `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md` 承接当前主线详细闭环
  - `docs/SEARCH_MEDIA_SLIMMING_LOG.md` 保留上一条主线已完成台账
  - `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` 保留更早主线已完成台账
  - `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` 保留更早主线已完成台账
  - `docs/TELEGRAM_BOT_SLIMMING_LOG.md` 保留更早主线已完成台账
  - `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md` 保留更早主线已完成台账
  - `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md` 保留更早主线已完成台账
  - `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md` 保留更早主线已完成台账
  - `docs/PERSISTENCE_CLOSURE_LOG.md` 保留更早主线已完成台账
  - `docs/CLEANUP_VERIFICATION_WINDOW.md` 只承接 cleanup 已完成窗口证据
- 新闭环按主题合并进 `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md` 2.1~2.2 已有分组，**不再开新的 `### 2026-xx-xx 分流缺口` 小节；`STATUS.md` 只补一句当前结论或风险，不逐天追加 `截至 ...` 条目**
- 保持 cleanup 完成态文档结论稳定：`README.md`、`docs/NEXT_STEP.md`、`docs/STATUS.md` 不要回退成“cleanup 仍在进行中”
- 保持 verification docs gate 可持续通过；当前 docs gate 只需要锁住入口一致性、状态页短快照结构、固定验证快照和当前主线台账入口

## Do not do

- 不新增自动 inspect、自动 cleanup、批量 cleanup、删种或新的 cleanup workflow
- 不放宽现有 cleanup guardrail、删除范围或 correlation 校验
- 不把 `manage_bt_subscription.py` 借机重构成通用订阅平台、通用 scheduler 平台或通用 BT 自动化框架
- 不在这一步引入自动 `confirm`、自动下载、BT 共享评分器、series / anime 新解析能力、shared private-chat 交付体验 polish、Jellyfin / Plex 支持或其他新集成
- 不回退现有 `confirm` / approval / `jobs` / `job_event` / lease/version / SQLite 真相边界，也不改现有 BT 订阅命中新资源后的下载待确认协议

## Done when

当前主线视为 **已基本完成**，触发以下任一可测量条件即停止，并通知用户切换到下面 `After this step` 的第 1 项：

1. `manage_bt_subscription.py` 里的清单增删 / 标题解析 / 回复文本已抽到仓库自管 helper 或等价的统一边界，且 `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "parse_bt_subscription_query or add or list or remove or clear"` 全绿；
2. 或者 `manage_bt_subscription.py` 里的扫描候选筛选 / `last_seen` 更新 / scheduler tick 已抽到一组连贯 helper / 等价统一边界，且 `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "run_once or scheduler_tick or last_seen"` 全绿；
3. 或者本轮候选闭环的代码变更 **< 20 行**、本质只是为同一个 repo API 再拆一条 `if/elif/log` 诊断分支（收益递减），且上一轮也是同类微闭环——此时视为已越过完成线，直接停止。

满足其中任一条时，直接回到本文件 `After this step` 第 1 项（`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化）。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `verification docs gate` 与 cleanup 完成态证据持续通过
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md` / `docs/SEARCH_MEDIA_SLIMMING_LOG.md` / `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` / `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` / `docs/TELEGRAM_BOT_SLIMMING_LOG.md` / `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md` / `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md` / `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md` / `docs/PERSISTENCE_CLOSURE_LOG.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 继续保持分层一致，不重新写回长台账

## After this step

1. `cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化：把 cleanup 身份解析（`_resolve_cleanup_task_identity` + `_find_import_correlation`）、inspect 与 execution 主路径、路径校验与 source 删除（`_validate_cleanup_paths` + `_delete_source_asset`）、follow-up 文案组装（`_append_cleanup_follow_up` / `_format_cleanup_inspect_follow_up` 等）和事件落盘 + 中文日志 helper（`_record_event` + `_print_cleanup_*`）继续拆开；目标是不改 cleanup guardrail、删除范围、identity retention、`job_event` 真相和现有 cleanup 文本协议
2. `private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化：把 frustration reset、pending state gate、命令分发和 shared reply 包装继续拆开；目标是不改四渠道共用协议、approval、`jobs` 和 SQLite 真相边界
3. `app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化：把 client 装配、后台任务启停、下载器路由 helper 和启动日志继续拆开；目标是不改启动入口、角色绑定和现有运行时真相
4. `series / anime` 独立名称解析最小实现（结构化解析 + 小型识别词/替换配置）
5. `.ass` 字幕支持评估与最小实现
6. shared private-chat 交付体验收口（图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI）
7. 最小人类可用入口继续补齐（quick start / 配置模板 / 首个渠道 10 分钟跑通）
8. BT 共享确定性评分器
9. Jellyfin / Plex 支持（后续）
10. plugin 体系继续后置
