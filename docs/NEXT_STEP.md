# Next step (v99)

## Current baseline

- 四个渠道当前都是正式私聊入口：Telegram / personal WeChat / Feishu / WeCom。
- 四个渠道共用 `shared private-chat text runtime`、workflow、approval、`jobs` 和 SQLite 真相；渠道层只保留各自的验签、解密、轮询、回包和最小展示差异。
- 媒体主链已稳定跑通：`search -> select -> downloader approval -> confirm -> dispatch -> status -> import approval -> confirm -> import -> metadata -> subtitle -> refresh`。
- cleanup 最小文本闭环已落地：discoverability、`cleanup inspect`、`cleanup`、rejection guidance、success follow-up、failure observability、chat-scoped `task_ref` 解析。
- cleanup 执行阶段的阻断分支（correlation 缺失 / target 缺失 / source 已不存在 / guard 拒绝）已补齐显式中文日志和处理建议，不改用户文本协议。
- `tests/test_cleanup_cross_channel_smoke.py` 已落地，当前会聚合验证 Telegram / personal WeChat / Feishu / WeCom 四个公开入口上的英文/中文 bare `cleanup` / bare `cleanup inspect` discoverability、英文/中文原始 `task_id` 与 `task_hash` 的 `cleanup inspect` / `cleanup` smoke、英文/中文 `target missing` rejection guidance smoke，以及英文/中文 `chat-scoped task_ref -> jobs -> import correlation` smoke。
- `tests/test_cleanup_docs_consistency.py` 已落地，当前会校验 `docs/NEXT_STEP.md`、`docs/STATUS.md`、`docs/CLEANUP_VERIFICATION_WINDOW.md` 在验证窗口日期、聚合 smoke gate、`当前结论`、真实私聊 smoke 提示与 `chat-scoped task_ref -> jobs -> import correlation` 描述上保持一致。
- BT 主链已落地：PT / BT 分流、processing-path inquiry、BT classification、TMDB association、`raw_bt` 目标目录、shared source adapter、pure BT single-item ranking、`btsub` scheduler tick。

## Goal

把 cleanup 从“继续观察”收口成“有退出条件的四渠道验证窗口”，不新增任何 cleanup 行为。

## Only do

- 执行一个 7 天真实使用验证窗口。
- 把验证窗口起止日期、四渠道真实私聊 smoke 进度和当前结论持续记录到 `docs/CLEANUP_VERIFICATION_WINDOW.md`，不要让退出条件只留在口头描述。
- Telegram / personal WeChat / Feishu / WeCom 四个渠道各至少完成 1 次真实私聊 smoke，确认“消息进来 -> shared runtime -> 文本回去”不回退。
- 保持 `tests/test_cleanup_cross_channel_smoke.py` 稳定，作为当前四渠道 cleanup discoverability + inspect + execution + target-missing rejection guidance + `chat-scoped task_ref` 关联路径的聚合验收门，并持续覆盖英文/中文协议变体。
- 保持 cleanup 执行阻断分支的显式中文日志和处理建议稳定，不回退到只回用户文本、服务端无日志。
- 保持 cleanup 当前协议和语义不变：
  - `cleanup inspect <任务ID或Hash>` / `清理检查 <任务ID或Hash>`
  - `cleanup <任务ID或Hash>` / `清理 <任务ID或Hash>`
  - bare `cleanup` / `清理`
  - bare `cleanup inspect` / `清理检查`
- 保持 `chat-scoped task_ref -> jobs -> import correlation` 稳定，不回退到只能依赖原始 `task_id / task_hash`；当前聚合 smoke gate 也要覆盖这条路径。
- 若验证期间出现问题，只允许修：
  - shared runtime 回归
  - 渠道适配胶水回归
  - 显式中文日志和修复提示缺口
- 保持 downloader / import approval、copy fallback、completion-monitor、metadata scraping、subtitle auto-translation、Emby refresh、BT 主链现状不回退。
- 新业务协议仍先落 shared runtime 或 service，再补四渠道适配层最小验证；不为同一条业务逻辑维护四套分叉实现。

## Do not do

- 不新增自动 inspect、自动 cleanup、批量 cleanup、删种或新的 cleanup workflow。
- 不放宽现有 cleanup guardrail、删除范围或 correlation 校验。
- 不把四渠道适配重构成通用多渠道平台、通用 webhook 总线、通用 plugin / skill / MCP 平台。
- 不在这一步启动 `series / anime` 实现、BT 共享评分器重写、Jellyfin / Plex 支持或新的下载器 / 媒体服务器接入。
- 不回退现有文本协议：
  - `search/select/status/import/confirm/cleanup/watchlist/btsub`
  - `bt搜 <关键词>` / `bt search <关键词>`
  - `微信登录`

## Done when

- 已完成 7 天验证窗口。
- `docs/CLEANUP_VERIFICATION_WINDOW.md` 已完整记录窗口起止日期、四渠道真实私聊 smoke 日期和当前结论，且 `当前状态`、退出清单、渠道进度彼此一致。
- 四个渠道各至少完成 1 次真实私聊 shared-runtime smoke。
- `tests/test_cleanup_cross_channel_smoke.py` 持续通过，并持续覆盖英文/中文 discoverability / inspect / execution / target-missing rejection guidance 与 `chat-scoped task_ref -> jobs -> import correlation` 路径，不回退到只能靠人工拼多个渠道测试结果。
- cleanup discoverability、inspect、execution、rejection guidance、success follow-up、failure observability 都没有协议回退。
- cleanup 失败路径继续打印显式中文日志和修复提示，不再静默吞错。
- 若验证窗口里出现问题，修复仍保持在现有 cleanup 文本闭环和渠道胶水范围内，没有引入新副作用。
- 文档优先级仍保持一致：`DECISIONS -> NEXT_STEP -> STATUS -> README -> AGENTS`。

## After this step

1. 启动 `series / anime` 独立名称解析最小实现，先落 `title / year / season / episode / quality_tags` 结构。
2. 把 `pure_bt`、`manage_bt_subscription`、后续媒体型 BT 选源收敛到共享确定性评分器。
