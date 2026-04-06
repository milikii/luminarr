# Next step (v120)

## Current baseline

- 四个渠道当前都是正式私聊入口：Telegram / personal WeChat / Feishu / WeCom。
- 四个渠道共用 `shared private-chat text runtime`、workflow、approval、`jobs` 和 SQLite 真相；渠道层只保留各自的验签、解密、轮询、回包和最小展示差异。
- 媒体主链已稳定跑通：`search -> select -> downloader approval -> confirm -> dispatch -> status -> import approval -> confirm -> import -> metadata -> subtitle -> refresh`。
- cleanup 最小文本闭环已落地：discoverability、`cleanup inspect`、`cleanup`、rejection guidance、success follow-up、failure observability、chat-scoped `task_ref` 解析。
- cleanup 执行阶段的阻断分支（correlation 缺失 / target 缺失 / source 已不存在 / guard 拒绝）已补齐显式中文日志和处理建议，不改用户文本协议。
- `tests/test_cleanup_cross_channel_smoke.py` 已落地，当前会聚合验证 Telegram / personal WeChat / Feishu / WeCom 四个公开入口上的英文/中文 bare `cleanup` / bare `cleanup inspect` discoverability、英文/中文原始 `task_id` 与 `task_hash` 的 `cleanup inspect` / `cleanup` smoke、英文/中文原始 `task_id` 与 `task_hash` 的 `correlation missing` / `target missing` / `source missing` / `guard rejected` rejection guidance smoke，以及英文/中文 `chat-scoped task_ref -> jobs -> import correlation` smoke。
- `tests/test_cleanup_docs_consistency.py` 与 `tests/test_cleanup_verification_window_doc.py` 已落地，当前会校验 `docs/NEXT_STEP.md`、`docs/STATUS.md`、`docs/CLEANUP_VERIFICATION_WINDOW.md` 在验证窗口日期、窗口标题日期与正文起止/退出清单日期一致性、聚合 smoke gate、`窗口活性`、`当前结论`、真实私聊 smoke 提示、`guard-rejected rejection guidance` 与 `chat-scoped task_ref -> jobs -> import correlation` 描述上保持一致。
- `docs/CLEANUP_VERIFICATION_WINDOW.md` 当前标题直接带 `2026-04-05 to 2026-04-12` 日期，避免窗口起止日期只藏在正文条目里。
- `docs/CLEANUP_VERIFICATION_WINDOW.md` 当前不只记录四渠道真实私聊 smoke 进度，也要记录最近一次聚合 smoke gate 与 cleanup 协议回归验证结果，避免验证窗口只剩“待勾选项”。
- `tests/test_cleanup_verification_window_doc.py` 当前还会要求：只要验证窗口仍处于进行中，`当前结论`、最近一次聚合 smoke gate 与 cleanup 协议回归验证日期就必须同步到当天日期，避免窗口台账停在旧日期。
- `tests/test_cleanup_verification_window_doc.py` 当前还会要求：验证窗口不得早于最早可结束日期就被标记为 `已完成`，避免 7 天窗口被文档提前关闭。
- `tests/test_cleanup_verification_window_doc.py` 当前还会要求：已完成渠道写入的真实私聊 smoke 日期不得早于窗口开始日期，也不得晚于当前结论快照日期，避免把窗口外证据回填进窗口台账。
- `tests/test_cleanup_verification_window_doc.py` 当前还会要求：一旦到达最早可结束日期且四渠道真实私聊 smoke、smoke gate、cleanup 协议回归都已满足，验证窗口就必须立刻改成已完成，避免退出条件已齐但台账仍挂进行中。
- `tests/test_cleanup_verification_window_doc.py` 当前还会要求：只要四渠道里仍有待补项，`当前结论` 就必须显式写出真实私聊 cleanup smoke 仍待补，避免结论退化成笼统的“退出条件未满足”。
- `tests/test_cleanup_verification_window_doc.py` 当前还会要求：当四渠道真实私聊 smoke 已全部补齐后，`当前结论` 就不得继续写“真实私聊 cleanup smoke 仍待补”，避免结论和渠道进度表互相打架。
- cleanup 窗口收口后，当前已经明确的后续主线顺序是：
  1. `series / anime` 独立名称解析最小实现
  2. shared private-chat 交付体验收口（图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI）
  3. 最小人类可用入口（quick start / 配置模板 / 首个渠道 10 分钟跑通）
  4. BT 共享确定性评分器
  5. Jellyfin / Plex 支持（后续）
  6. plugin 体系继续后置
- BT 主链已落地：PT / BT 分流、processing-path inquiry、BT classification、TMDB association、`raw_bt` 目标目录、shared source adapter、pure BT single-item ranking、`btsub` scheduler tick。

## Goal

把 cleanup 从“继续观察”收口成“有退出条件的四渠道验证窗口”，不新增任何 cleanup 行为。

## Only do

- 执行一个 7 天真实使用验证窗口。
- 把验证窗口起止日期、四渠道真实私聊 smoke 进度和当前结论持续记录到 `docs/CLEANUP_VERIFICATION_WINDOW.md`，不要让退出条件只留在口头描述。
- 把验证窗口当前是否仍处于“未到最早可结束日期”还是“已到最早可结束日期但待补退出条件”显式写进 `docs/CLEANUP_VERIFICATION_WINDOW.md`，不要让窗口活性只靠人工脑补。
- 当窗口仍处于 `未到最早可结束日期` 时，`当前结论` 也要显式写出“尚未到最早可结束日期 <绝对日期>”，不要只写笼统的进行中。
- 当窗口已到 `最早可结束日期` 但仍未完成时，`当前结论` 也要显式写出“已到最早可结束日期 <绝对日期>，但退出条件仍未满足”，不要继续沿用未到期文案。
- 把最近一次聚合 smoke gate 与 cleanup 协议回归验证的日期、结果和命令持续记录到 `docs/CLEANUP_VERIFICATION_WINDOW.md`，让退出清单有对应证据。
- 只要验证窗口仍处于进行中，`当前结论`、最近一次聚合 smoke gate 与 cleanup 协议回归验证日期就必须同步到当天日期，避免窗口台账和 `docs/STATUS.md` 快照停在旧日期。
- 即使四渠道真实私聊 smoke 和 cleanup 协议回归都已满足，也不得早于最早可结束日期把验证窗口标记为 `已完成`。
- 已完成渠道写入的真实私聊 smoke 日期不得早于窗口开始日期，也不得晚于当前结论快照日期，避免把窗口外日期误记成当前验证窗口证据。
- 一旦到达最早可结束日期且四渠道真实私聊 smoke、smoke gate、cleanup 协议回归三类退出条件都满足，验证窗口就必须立刻改成已完成，不能继续保留进行中文案。
- 只要四渠道里仍有待补项，`当前结论` 就必须显式写出真实私聊 cleanup smoke 仍待补，不能退化成笼统的“退出条件未满足”。
- 当四渠道真实私聊 smoke 已全部补齐后，`当前结论` 就不得继续写“真实私聊 cleanup smoke 仍待补”；若窗口仍未完成，只能改写成日期或其他剩余缺口。
- 让 exit checklist 里的 smoke gate / cleanup 协议两项直接跟随上述证据同步；仍待补的只保留真实私聊 smoke 和窗口起止条件。
- `docs/STATUS.md` 只保留与 `docs/CLEANUP_VERIFICATION_WINDOW.md` 同步的当前状态快照、四渠道当前快照和当前结论快照；逐项备注和证据继续只写在验证窗口台账里，不要两边各写一套状态。
- `docs/STATUS.md` 还要同步保留 `窗口活性` 快照，避免最早可结束日期前后仍写成同一类进行中。
- Telegram / personal WeChat / Feishu / WeCom 四个渠道各至少完成 1 次真实私聊 smoke，确认“消息进来 -> shared runtime -> 文本回去”不回退。
- 保持 `tests/test_cleanup_cross_channel_smoke.py` 稳定，作为当前四渠道 cleanup discoverability + inspect + execution + correlation-missing rejection guidance + target-missing rejection guidance + source-missing rejection guidance + guard-rejected rejection guidance + `chat-scoped task_ref` 关联路径的聚合验收门，并持续覆盖英文/中文协议变体。
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
- 不在这一步启动 `series / anime` 实现、shared private-chat 交付体验 polish、最小人类可用入口、BT 共享评分器重写、Jellyfin / Plex 支持或新的下载器 / 媒体服务器接入。
- 不把“给别人用的体验”误解成 Web UI 主线；这一步之后的体验增强继续优先走私聊渠道回包层。
- 不回退现有文本协议：
  - `search/select/status/import/confirm/cleanup/watchlist/btsub`
  - `bt搜 <关键词>` / `bt search <关键词>`
  - `微信登录`

## Done when

- 已完成 7 天验证窗口。
- `docs/CLEANUP_VERIFICATION_WINDOW.md` 已完整记录窗口起止日期、四渠道真实私聊 smoke 日期、窗口活性和当前结论，且 `窗口活性`、`当前状态`、窗口标题日期、退出清单、渠道进度彼此一致。
- `docs/CLEANUP_VERIFICATION_WINDOW.md` 已同步记录最近一次聚合 smoke gate 与 cleanup 协议回归验证的日期、结果和命令，避免“测试已跑过但窗口台账没有证据”。
- exit checklist 里的 smoke gate / cleanup 协议两项已与上述证据保持同步，不会继续停留在未勾选状态。
- 四个渠道各至少完成 1 次真实私聊 shared-runtime smoke。
- `tests/test_cleanup_cross_channel_smoke.py` 持续通过，并持续覆盖英文/中文 discoverability / inspect / execution / correlation-missing rejection guidance / target-missing rejection guidance / source-missing rejection guidance / guard-rejected rejection guidance 与 `chat-scoped task_ref -> jobs -> import correlation` 路径，不回退到只能靠人工拼多个渠道测试结果。
- cleanup discoverability、inspect、execution、rejection guidance、success follow-up、failure observability 都没有协议回退。
- cleanup 失败路径继续打印显式中文日志和修复提示，不再静默吞错。
- 若验证窗口里出现问题，修复仍保持在现有 cleanup 文本闭环和渠道胶水范围内，没有引入新副作用。
- 文档优先级仍保持一致：`DECISIONS -> NEXT_STEP -> STATUS -> README -> AGENTS`。

## After this step

1. 启动 `series / anime` 独立名称解析最小实现，先落 `title / year / season / episode / quality_tags` 结构。
2. 收口 shared private-chat 交付体验，优先补图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI。
3. 补最小人类可用入口，至少包含 quick start、配置模板和首个渠道 bring-up。
4. 把 `pure_bt`、`manage_bt_subscription`、后续媒体型 BT 选源收敛到共享确定性评分器。
5. 在 Emby 主线稳定后，再推进 Jellyfin / Plex 支持。
6. plugin 体系继续后置，不作为当前主线阻塞项。
