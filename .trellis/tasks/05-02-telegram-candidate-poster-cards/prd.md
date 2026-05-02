# brainstorm: telegram candidate poster cards

## Goal

重做 Telegram 里的作品候选确认体验，但不改主业务顺序。用户输入片名后，必须先锁定作品候选；只有用户明确选中作品后，系统才开始搜索资源。这个任务只吸收更好的排版、美化和交互效果，把候选确认阶段升级为海报卡片化、按钮化、富文本化。

## What I already know

* 当前仓库的 Telegram 候选确认消息由 `app/services/search_reply_formatter.py` 和 `app/bot/telegram_reply_formatter.py` 生成，再由 `app/bot/telegram_update_runtime.py` 发送。
* 当前普通影视候选确认仍是“多张候选海报消息 + 一条文本 follow-up”，测试已固定这一行为。
* 当前 adult BT 路径已经支持 `send_photo + HTML caption + InlineKeyboard`，说明 Telegram 卡片化能力在仓库内已存在可复用实现。
* 仓库已经内置 `app.clients.fanart.FanartClient`，`app/main.py` 里也已有 `FANART_API_KEY` / `FANART_BASE_URL` 配置接线，说明 fanart 回退能力不是新基础设施。
* 用户明确要求：主业务逻辑必须是“先锁定作品候选，确定作品后才能搜索资源”，不能吸收外部方案里混杂的其它流程改造。
* 用户明确要求：候选确认阶段每个候选都必须有海报卡片，不能退化成“只有一张主海报，其余只有名字按钮”。
* 用户明确要求：候选没有 TMDB 海报时，优先尝试从 fanart 找图。

## Assumptions (temporary)

* 候选确认阶段继续沿用当前 top-N 候选的基本范围，不在本任务里扩大会话状态机。
* Telegram 交互仍基于现有 callback query / reply 流程，不重做底层 transport。
* 本任务优先改 Telegram 呈现层与候选确认主线，不扩到 WeChat / Feishu / WeCom。

## Open Questions

* 当前无阻塞开放问题。

## Requirements (evolving)

* Telegram 里作品候选确认必须发生在资源搜索之前。
* 普通影视候选确认必须是“每个候选一个独立海报卡片”，且每张卡片都带该候选自己的选择交互。
* 候选卡片使用 Telegram HTML 富文本展示标题、年份、类型、简介等信息。
* 优先使用 TMDB 海报；TMDB 缺图时回退 fanart。
* 如果 TMDB 和 fanart 都缺图，必须继续展示该候选，并使用统一占位图保持“每个候选都有海报卡片”。
* 本任务只优化展示层和交互层，不引入新的搜索业务分支，不把候选确认改成资源优先。

## Acceptance Criteria (evolving)

* [ ] 用户输入存在歧义的作品名时，Telegram 先返回候选作品卡片，而不是直接搜索资源。
* [ ] 每个候选作品都以独立海报卡片展示，不出现“只有名字无海报”的常规候选项。
* [ ] 候选卡片支持按钮化选择，不要求用户手打序号。
* [ ] 候选锁定后，系统才进入资源搜索阶段。
* [ ] TMDB 无海报时会尝试 fanart 回退。
* [ ] TMDB 和 fanart 都缺图时仍展示候选卡片，并使用统一占位图兜底。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* 改写 downloader / approval / import 的底层业务逻辑
* 引入外部方案里的新状态协议、sentinel 文本协议或额外流程分支
* 改造非 Telegram 渠道的消息展示
* 在本任务里重做整条资源搜索与审批产品链路

## Technical Notes

* 已检查候选确认结构：`app/services/search_reply_formatter.py`、`app/bot/telegram_reply_formatter.py`、`app/bot/telegram_update_runtime.py`
* 已检查 Telegram 发送层现状：`app/bot/telegram_delivery_runtime.py`
* 已检查 fanart 现状：`app/main.py`、`app/clients/fanart.py`
* 已检查现有测试基线：`tests/test_telegram_reply_formatter.py`、`tests/test_telegram_delivery_runtime.py`
* 现有 adult BT 路径已经实现单卡片 + HTML + InlineKeyboard，可作为普通影视候选确认的实现参考，但不能把 adult BT 逻辑直接套过来
