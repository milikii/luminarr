# Next step (v202)

## Current goal

- 当前唯一主线：**持久化吞错收口**
- 上一条主线完成态：**shared private-chat runtime 最小抽离已完成**
- 更早完成态：**cleanup 四渠道验证窗口已完成**
- 当前窗口：`2026-04-05 to 2026-04-12`（上一条 cleanup 主线的完成窗口）
- cleanup 已完成窗口的详细台账和证据统一写在 `docs/CLEANUP_VERIFICATION_WINDOW.md`
- 当前主线的详细闭环、focused tests 和最近 commit 轨迹统一写在 `docs/PERSISTENCE_CLOSURE_LOG.md`
- 当前最小闭环：继续把剩余 `except Exception: pass/return None`、`None/False` 混写异常态收口成“区分真缺数据和 SQLite / 配置异常”的显式中文日志与 `[处理建议]`，不改 workflow 真相和副作用边界

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线详细台账：`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 继续收口当前主线剩余持久化吞错路径；每轮只做一个最小闭环，不顺手清理不相关模块
- 保持 Telegram / personal WeChat / Feishu / WeCom 四个渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持当前已经落下来的 fail-closed 方向不回退：
  - 下载审批链
  - 导入审批链
  - 搜索待澄清状态链
  - 搜索候选状态链
- 涉及真实 downloader / import / refresh 行为的任务，继续使用本地 Transmission / Emby 联调栈验证，不拿 mock 代替真实链路
- 文档继续分层：
  - `docs/STATUS.md` 只保留当前快照
  - `docs/PERSISTENCE_CLOSURE_LOG.md` 承接当前主线详细闭环
  - `docs/CLEANUP_VERIFICATION_WINDOW.md` 只承接 cleanup 已完成窗口证据
- 保持 cleanup 完成态文档结论稳定：`README.md`、`docs/NEXT_STEP.md`、`docs/STATUS.md` 不要回退成“cleanup 仍在进行中”
- 保持 verification docs gate 可持续通过；当前 docs gate 只需要锁住入口一致性、状态页短快照结构、固定验证快照和当前主线台账入口

## Do not do

- 不新增自动 inspect、自动 cleanup、批量 cleanup、删种或新的 cleanup workflow
- 不放宽现有 cleanup guardrail、删除范围或 correlation 校验
- 不把四渠道适配重构成通用多渠道平台、通用 webhook 总线或通用 plugin / skill / MCP 平台
- 不在这一步启动 `series / anime` 实现、shared private-chat 交付体验 polish、最小人类可用入口之外的新产品面、BT 共享评分器重写、Jellyfin / Plex 支持或其他新集成
- 不回退现有 `confirm` / approval / `jobs` / lease/version / SQLite 真相边界

## Done when

- 剩余持久化路径里的 `except Exception: pass/return None`、`None/False` 混写异常态已基本收口成显式中文日志与 `[处理建议]`
- 当前主线下已经改过的下载 / 导入 / 搜索 fail-closed 协议没有回退
- shared runtime、approval、`jobs`、SQLite 真相和四渠道现有 cleanup / search / import / status / watchlist / btsub 协议没有回退
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `docs/PERSISTENCE_CLOSURE_LOG.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 继续保持分层一致，不重新写回长台账

## After this step

1. Feishu 长连接私有 API 风险收口
2. Feishu 私聊事件解析器去重
3. 独立后台下载完成轮询剩余少量回归与验证收口
4. `telegram_bot.py` 渠道层瘦身 / 模块化：把 Telegram 收包回包、后台生命周期、BT pending helper 和 shared runtime 包装继续拆开；目标是让渠道层更接近“协议差异 + 调 shared runtime”，但不改 shared runtime、approval、`jobs`、SQLite 真相和现有副作用边界
5. `import_to_library.py` 导入编排层瘦身 / 模块化：把导入前上下文重建与 raw_bt 判定、执行模式 / copy-fallback、文件系统导入执行、metadata / subtitle / refresh 收尾继续拆开；目标是不改 approval、`jobs`、`job_event`、导入成功真相和现有副作用边界
6. `add_to_downloader.py` 下载编排层瘦身 / 模块化：把候选选择 / 来源解析、待确认写入、confirm 执行、下载监控登记和事件落盘继续拆开；目标是不改 search、approval、`jobs`、`download_monitor`、`job_event` 和现有下载副作用边界
7. `search_media.py` 搜索编排层瘦身 / 模块化：把 query 解析、TMDB / Prowlarr 查询、歧义澄清与候选持久化、回复格式化继续拆开；目标是不改 clarification / candidate 状态协议、shared runtime 入口和 SQLite 真相边界
8. `manage_bt_subscription.py` 订阅编排层瘦身 / 模块化：把清单增删、扫描候选筛选、`last_seen` 更新和 scheduler tick 收口继续拆开；目标是不改 `bt_subscription_item` 真相、downloader approval 边界和自动扫描停路规则
9. `private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化：把 frustration reset、pending state gate、命令分发和 shared reply 包装继续拆开；目标是不改四渠道共用协议、approval、`jobs` 和 SQLite 真相边界
10. `app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化：把 client 装配、后台任务启停、下载器路由 helper 和启动日志继续拆开；目标是不改启动入口、角色绑定和现有运行时真相
11. `series / anime` 独立名称解析最小实现（结构化解析 + 小型识别词/替换配置）
12. `.ass` 字幕支持评估与最小实现
13. shared private-chat 交付体验收口（图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI）
14. 最小人类可用入口继续补齐（quick start / 配置模板 / 首个渠道 10 分钟跑通）
15. BT 共享确定性评分器
16. Jellyfin / Plex 支持（后续）
17. plugin 体系继续后置
