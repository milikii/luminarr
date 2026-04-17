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
5. `series / anime` 独立名称解析最小实现（结构化解析 + 小型识别词/替换配置）
6. `.ass` 字幕支持评估与最小实现
7. shared private-chat 交付体验收口（图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI）
8. 最小人类可用入口继续补齐（quick start / 配置模板 / 首个渠道 10 分钟跑通）
9. BT 共享确定性评分器
10. Jellyfin / Plex 支持（后续）
11. plugin 体系继续后置
