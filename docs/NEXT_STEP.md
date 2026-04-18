# Next step (v205)

## Current goal

- 当前唯一主线：**独立后台下载完成轮询剩余少量回归与验证收口**
- 上一条主线完成态：**Feishu 私聊事件解析器去重已完成**
- 更早完成态：**Feishu 长连接私有 API 风险收口已完成**
- 更早完成态：**持久化吞错收口已完成**
- 更早完成态：**shared private-chat runtime 最小抽离已完成**
- 更早完成态：**cleanup 四渠道验证窗口已完成**
- 当前窗口：`2026-04-05 to 2026-04-12`（上一条 cleanup 主线的完成窗口）
- cleanup 已完成窗口的详细台账和证据统一写在 `docs/CLEANUP_VERIFICATION_WINDOW.md`
- 当前主线的详细闭环、focused tests 和风险分组统一写在 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 上一条主线的详细闭环和 focused tests 继续写在 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线的详细闭环和 focused tests 继续写在 `docs/PERSISTENCE_CLOSURE_LOG.md`
- 当前最小闭环：每轮只收一个后台下载完成轮询的 regression / verification gap，优先处理 `app/bot/telegram_bot.py` 里的待轮询列表读取、独立轮询启动/停机和必要的真实链路验证，不改 shared runtime、下载分发、approval、`jobs` 和 SQLite 真相

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线详细台账：`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 上一条主线详细台账：`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线详细台账：`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线详细台账：`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 继续收口独立后台下载完成轮询的剩余 regression / verification gap；每轮只做一个最小闭环，不顺手清理不相关模块
- 保持 Telegram / personal WeChat / Feishu / WeCom 四个渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持当前已经落下来的下载完成轮询 / 自动导入 / 中文日志方向不回退：
  - `telegram_bot._poll_pending_download_completion_once()` 的待轮询列表结果缺失 / 记录损坏 / 读库失败继续显式分流
  - `telegram_bot._download_completion_polling_loop()` 的逐条状态轮询失败继续显式中文日志 + `[处理建议]`
  - `_start_post_download_auto_import_scheduler()` / `_stop_post_download_auto_import_scheduler()` 的独立启动 / 停机失败边界不回退
- 涉及真实 downloader / import / refresh 行为的任务，继续使用本地 Transmission / Emby 联调栈验证；当前主线允许补一条真实轮询验证，但不扩成更大的导入或 cleanup 新主线
- 文档继续分层：
  - `docs/STATUS.md` 只保留当前快照
  - `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md` 承接当前主线详细闭环
  - `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md` 保留上一条主线已完成台账
  - `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md` 保留更早主线已完成台账
  - `docs/PERSISTENCE_CLOSURE_LOG.md` 保留更早主线已完成台账
  - `docs/CLEANUP_VERIFICATION_WINDOW.md` 只承接 cleanup 已完成窗口证据
- 新闭环按主题合并进 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md` 2.1~2.2 已有分组，**不再开新的 `### 2026-xx-xx 分流缺口` 小节；`STATUS.md` 只补一句当前结论或风险，不逐天追加 `截至 ...` 条目**
- 保持 cleanup 完成态文档结论稳定：`README.md`、`docs/NEXT_STEP.md`、`docs/STATUS.md` 不要回退成“cleanup 仍在进行中”
- 保持 verification docs gate 可持续通过；当前 docs gate 只需要锁住入口一致性、状态页短快照结构、固定验证快照和当前主线台账入口

## Do not do

- 不新增自动 inspect、自动 cleanup、批量 cleanup、删种或新的 cleanup workflow
- 不放宽现有 cleanup guardrail、删除范围或 correlation 校验
- 不在这一步顺手启动 `telegram_bot.py` 大规模瘦身 / 模块化、scheduler 平台化或其他渠道层重构
- 不在这一步启动 Feishu / WeCom 新能力、`series / anime`、shared private-chat 交付体验 polish、BT 共享评分器、Jellyfin / Plex 支持或其他新集成
- 不回退现有 `confirm` / approval / `jobs` / lease/version / SQLite 真相边界，也不改现有下载分发、导入成功真相和 cleanup 最小协议

## Done when

当前主线视为 **已基本完成**，触发以下任一可测量条件即停止，并通知用户切换到下面 `After this step` 的第 1 项：

1. 本地 Transmission / Emby 联调栈上已补到一条真实“下载完成轮询 -> 既有状态 / 自动导入边界”验证证据，且 `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "pending_list or download_completion_polling or post_download_auto_import_scheduler"` 全绿；
2. 或者 `app/bot/telegram_bot.py` 里的 `_poll_pending_download_completion_once()`、`_download_completion_polling_loop()` 与 `_start/_stop_post_download_auto_import_scheduler()` 不再各自补零散分叉，而是收口成同一组仓库自管 helper 或等价的统一边界，且上面的 focused tests 全绿；
3. 或者本轮候选闭环的代码变更 **< 20 行**、本质只是为同一个 repo API 再拆一条 `if/elif/log` 诊断分支（收益递减），且上一轮也是同类微闭环——此时视为已越过完成线，直接停止。

满足其中任一条时，直接回到本文件 `After this step` 第 1 项（`telegram_bot.py` 渠道层瘦身 / 模块化）。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `verification docs gate` 与 cleanup 完成态证据持续通过
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md` / `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md` / `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md` / `docs/PERSISTENCE_CLOSURE_LOG.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 继续保持分层一致，不重新写回长台账

## After this step

1. `telegram_bot.py` 渠道层瘦身 / 模块化：把 Telegram 收包回包、后台生命周期、BT pending helper 和 shared runtime 包装继续拆开；目标是让渠道层更接近“协议差异 + 调 shared runtime”，但不改 shared runtime、approval、`jobs`、SQLite 真相和现有副作用边界
2. `import_to_library.py` 导入编排层瘦身 / 模块化：把导入前上下文重建与 raw_bt 判定、执行模式 / copy-fallback、文件系统导入执行、metadata / subtitle / refresh 收尾继续拆开；目标是不改 approval、`jobs`、`job_event`、导入成功真相和现有副作用边界
3. `add_to_downloader.py` 下载编排层瘦身 / 模块化：把候选选择 / 来源解析、待确认写入、confirm 执行、下载监控登记和事件落盘继续拆开；目标是不改 search、approval、`jobs`、`download_monitor`、`job_event` 和现有下载副作用边界
4. `search_media.py` 搜索编排层瘦身 / 模块化：把 query 解析、TMDB / Prowlarr 查询、歧义澄清与候选持久化、回复格式化继续拆开；目标是不改 clarification / candidate 状态协议、shared runtime 入口和 SQLite 真相边界
5. `manage_bt_subscription.py` 订阅编排层瘦身 / 模块化：把清单增删、扫描候选筛选、`last_seen` 更新和 scheduler tick 收口继续拆开；目标是不改 `bt_subscription_item` 真相、downloader approval 边界和自动扫描停路规则
6. `cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化：把 cleanup 身份解析（`_resolve_cleanup_task_identity` + `_find_import_correlation`）、inspect 与 execution 主路径、路径校验与 source 删除（`_validate_cleanup_paths` + `_delete_source_asset`）、follow-up 文案组装（`_append_cleanup_follow_up` / `_format_cleanup_inspect_follow_up` 等）和事件落盘 + 中文日志 helper（`_record_event` + `_print_cleanup_*`）继续拆开；目标是不改 cleanup guardrail、删除范围、identity retention、`job_event` 真相和现有 cleanup 文本协议
7. `private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化：把 frustration reset、pending state gate、命令分发和 shared reply 包装继续拆开；目标是不改四渠道共用协议、approval、`jobs` 和 SQLite 真相边界
8. `app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化：把 client 装配、后台任务启停、下载器路由 helper 和启动日志继续拆开；目标是不改启动入口、角色绑定和现有运行时真相
9. `series / anime` 独立名称解析最小实现（结构化解析 + 小型识别词/替换配置）
10. `.ass` 字幕支持评估与最小实现
11. shared private-chat 交付体验收口（图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI）
12. 最小人类可用入口继续补齐（quick start / 配置模板 / 首个渠道 10 分钟跑通）
13. BT 共享确定性评分器
14. Jellyfin / Plex 支持（后续）
15. plugin 体系继续后置
