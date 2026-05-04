# telegram-first auto-confirm and notification adaptation

## Goal

先把 Telegram 的观影 PT 主链收口成“显式选择之后少打断”的最小自动化版本，并把 Telegram 渠道的关键通知真实跑通、看清样式，再把其他渠道作为后续独立任务逐个适配、优化和测试。

## What I already know

* 用户刚确认新的推进顺序是：
  * 先从 Telegram 开始
  * 每个渠道单独适配、优化、测试
* 用户刚进一步锁定了导入/清理语义：
  * **不做 copy fallback**
  * 默认都是硬链接
  * `PT` 主链：
    * 只要 Emby 里的媒体文件还在，就不删 PT 原文件 / 原任务
  * `BT 成人链`：
    * 也是硬链接
    * 7 天后直接删原文件和下载任务
    * 只保留可查询记录
* 已有自动评审结论表明，这一刀不该继续混入：
  * direct magnet 降问询
  * 字幕翻译验证
  * MoviePilot 级 metadata / poster / cast 成品化
* 当前代码里：
  * 下载确认真相仍建立在 `approval_record + jobs + lease` 之上
  * 下载完成后的后台通知由 `download_follow_up_runtime` 统一调度
  * `shared_private_chat_sender` 已支持：
    * Telegram proactive send
    * Feishu proactive send
    * personal WeChat proactive send
  * `WeCom` 当前明确不支持 proactive send
* 已有文档主线明确：
  * 用户抱怨的是“确认摩擦”和“通知体验”
  * 删除的是用户确认，不是内部恢复/幂等真相

## Assumptions (temporary)

* Telegram-first 这轮的最小交付可以只覆盖观影 PT 链
* 自动下载和自动导入都应继续复用现有 confirm execution tail，而不是复制新流程
* 新的“只做硬链接、不做 copy fallback”是产品级约束，而不是 Telegram 渠道特例

## Open Questions

* 当前没有阻塞性开放问题。

## Requirements (evolving)

* Telegram 观影 PT 链优先推进
* 删除显式选择之后的多余确认环节
* 保留内部 approval / jobs / lease 真相
* 这轮只覆盖当前默认成功路径，不在本轮改造 copy fallback / 存储语义
* Telegram 渠道要有真实通知 smoke
* 其他渠道本轮不并行实现，只保留后续单独任务边界

## Acceptance Criteria (evolving)

* [ ] Telegram 资源选择后不再要求用户手发下载确认
* [ ] 若纳入 auto-import，则下载完成后硬链接路径不再要求用户手发导入确认
* [ ] Telegram 至少完成一轮真实通知 smoke，能看到最终实际文案和时序
* [ ] 不破坏现有 approval / jobs / stale / recovery 真相边界

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* direct magnet 自动识别与降问询
* 字幕翻译质量或 provider 验证
* MoviePilot 级 metadata / NFO / poster / cast 成品化
* Feishu / personal WeChat / WeCom 的同步实现
* `PT` 跟随 Emby 文件状态的长期保种 / 清理编排细化
* `BT 成人链` 7 天后清理策略的完整实现（若本轮只先做 Telegram PT slice）

## Technical Notes

* 候选计划基于 `docs/plans/2026-05-03-telegram-automation-after-explicit-selection.md`
* 通知能力现状受 `app/bot/shared_private_chat_sender.py` 和 `app/bot/download_follow_up_runtime.py` 约束
* WeCom 当前 proactive send 缺口已知，不应作为 Telegram-first 这轮的阻塞项
* “不做 copy fallback” 与“PT / 成人 BT 的不同清理语义”已经上升为产品规则，但已明确后置，不并入 Telegram 第一刀
