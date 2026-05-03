# brainstorm: telegram pt candidate layout smoke

## Goal

把“锁定作品后返回的 Telegram PT 资源卡”升级成双消息结构：第一条继续保留海报卡与按钮入口，第二条改成在 Telegram `4096` 文本预算内尽量展开的资源详情消息，并去掉当前全局 `5` 条资源上限，改为按站点分组展示更多候选。

## What I already know

* 用户刚刚要求“现在开始实测 搜索 PT 资源 返回候选的排版”，并已明确这轮目标是 `2`：锁定作品后的 `Telegram PT 资源卡`。
* 当前仓库里与这条链路直接相关的已知代码路径是：
  - `app/services/search_media.py`
  - `app/services/telegram_pt_resource_cards.py`
  - `app/bot/telegram_update_runtime.py`
  - `app/bot/telegram_runtime_adapter.py`
* 现有测试与计划已经把 PT 资源卡层定义为：
  - 作品锁定后返回 `photo/text card + buttons`
  - 用户点击按钮进入现有 pending approval 主线
  - 旧卡 / 重复点击 / 失败路径要安全降级
* 本轮真实 smoke 已确认：
  - `2026-05-03 12:53:47+08:00` Telegram 入站数字 `6`
  - `2026-05-03 12:53:55+08:00` 返回 `【PT资源卡】 82c2ee5a`
  - 当前卡片可用，但首屏只展示了 `PTP` 前 `3` 条资源
  - `candidate_mapping` 显示实际至少拿到了 `5` 条资源，其中已包含 `PassThePopcorn` 与 `Beyond-HD`
* 用户新的明确产品要求是：
  - 第一条海报卡保留
  - 资源详情放到第二条长文本消息
  - 利用 Telegram `sendMessage` 的 `4096` 字预算尽量多展开
  - 每个站点如果有资源，就给 `5-6` 条
  - 尽量同时覆盖 `4K / 2K / 1080`
  - 解除当前全局 `5` 条限制
* `Makefile` 已有 focused gate：`make verify-stage1-telegram-delivery`，其中第二段覆盖 PT 资源卡相关测试。
* `docs/STATUS.md` / `docs/NEXT_STEP.md` 当前都明确：新的真实 Telegram smoke 仍受两个环境前提制约
  - `api.telegram.org` 可达
  - 本地 `app.main` 在运行
* 历史 task `05-03-telegram-candidate-aggregate-confirmation` 是“作品候选聚合消息”方向，不等同于本轮目标。

## Assumptions (temporary)

* 首条海报卡继续承担视觉入口与按钮交互，不把所有资源信息重新塞回 caption。
* 第二条长文本消息主要承担“展开更多候选”的职责，仍要与按钮编号语义保持一致。
* 若需要具体实现取舍，默认首卡 caption 只保留作品摘要与“去看下一条详情/点击按钮选择”的短提示，不再承载资源明细行。
* “每站 `5-6` 条”是目标上限，但最终发送量仍必须受 Telegram `4096` 字限制保护。

## Open Questions

* 当前无新的产品范围问题；主要是实现层如何在 `4096` 内做站点分组与分辨率覆盖。

## Requirements (evolving)

* 第一条 Telegram PT 资源卡继续保持：
  - 有海报时优先 `send_photo + caption + buttons`
  - 无法发图时安全退回 text card
  - caption 保持简短，不再消耗预算逐条列资源
  - 按钮语义清晰，可进入现有 pending approval 主线
* 新增第二条 Telegram 资源详情消息：
  - 使用 `sendMessage(parse_mode="HTML")`
  - 在 `4096` 字预算内尽量展开
  - 按站点分组展示资源
  - 每个站点目标展示 `5-6` 条
  - 尽量覆盖 `4K / 2K / 1080`
  - 展开的编号与按钮编号保持一一对应
* 解除当前 `SearchMediaService limit=5` 对 PT 资源卡路径的硬限制，避免只保留全局前 `5` 条。
* 优先保证第二条里展开的资源都可被第一条按钮直接选择，而不是展示大量不可点资源。
* 若超出 Telegram 单条 `4096` 字预算，必须安全截断或分页，而不是发送失败。

## Acceptance Criteria (evolving)

* [ ] 已完成至少一轮 Telegram PT 资源卡真实 smoke。
* [ ] 第一条海报卡与按钮继续可用。
* [ ] 第二条长文本详情成功发送，并在 Telegram `4096` 限制内稳定可读。
* [ ] 至少验证一个多站点场景，确认不再只露出单站点前 `3` 条。
* [ ] 已记录当前 PT 资源卡的实际排版结果与预期差异。
* [ ] 若存在问题，已收口为明确回修范围或 blocker。
* [ ] 若环境不满足 smoke，已明确记录阻塞点。

## Definition of Done (team quality bar)

* Real smoke evidence is current-session evidence
* If code changes happen, focused tests and relevant quality gates stay green
* Docs/notes updated if behavior truth changes

## Out of Scope (explicit)

* 不把这轮任务自动扩成新的大规模交互重设计。
* 不把 adult BT、非 Telegram 渠道、下载确认卡一起混进来。
* 不回到作品候选聚合消息层做顺手修改。
* 不把按钮 callback 协议改成另一套与现有 pending approval 不兼容的形态。

## Technical Notes

* Relevant plan:
  - `docs/plans/2026-05-02-moviepilot-telegram-pt-resource-interaction-test-plan.md`
  - `.trellis/tasks/archive/2026-05/05-02-telegram-pt-resource-cards/prd.md`
* Relevant codepaths:
  - `app/services/search_media.py`
  - `app/services/telegram_pt_resource_cards.py`
  - `app/bot/telegram_update_runtime.py`
  - `app/bot/telegram_runtime_adapter.py`
* Relevant focused tests:
  - `tests/test_search_media.py`
  - `tests/test_telegram_pt_resource_cards.py`
  - `tests/test_telegram_runtime_adapter.py`
