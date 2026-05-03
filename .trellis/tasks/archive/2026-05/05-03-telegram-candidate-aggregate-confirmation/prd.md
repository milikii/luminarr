# brainstorm: telegram candidate aggregate confirmation

## Goal

把 Telegram 的作品候选确认体验从“每个候选一张独立海报卡片”改成“单条聚合消息”。新格式要求：消息最上面直接放首候选海报预览入口，候选标题直接链接到 TMDB，候选正文只保留“名称 / 年份 / 类型”，去掉简介、原名等次要信息，后续候选按序号在同一条消息里连续列出，尽量把能搜到的候选都放进一条消息里。

## What I already know

* 用户明确推翻了之前“每个候选都要独立海报卡片”的方向。
* 新目标是候选确认层，不是 PT 资源卡层。
* 用户接受的目标格式是：
  - 单条消息
  - 标题直接做 TMDB 链接
  - 消息最上面放首候选海报预览入口
  - 候选列表连续排列
  - “能搜到的结果都搜过来”
  - 去掉简介、原名等冗余信息，只保留名称、年份、类型
* 当前候选确认仍走：
  - `app/services/search_reply_formatter.py` 生成候选文本
  - `app/bot/telegram_reply_formatter.py` 格式化
  - `app/bot/telegram_update_runtime.py` 拆成多海报卡片发送
* 当前服务层候选条数默认仍被截到较小上限，不符合“尽量全量候选”的新方向。

## Assumptions (temporary)

* 这条新需求只改 Telegram 候选确认层，不立即改 PT 资源卡层。
* Telegram 的单条消息优先走 `send_message(parse_mode="HTML")`，而不是 `send_photo`，因为用户要“聚合消息”而不是海报主消息。
* 海报继续用可点击预览入口表达，不强求真实大图内联。

## Open Questions

* 当前无阻塞开放问题。

## Requirements (evolving)

* 候选确认改成 Telegram 单条聚合消息。
* 标题行要显式显示“【查询词】共找到 N 条相关信息，请选择操作”。
* 消息最上方先放首候选海报预览入口。
* 每个候选标题直接链接到 TMDB 详情页。
* 每个候选正文只保留：
  * 名称（标题即链接）
  * 年份
  * 类型（电影 / 电视剧 / 动漫 / 纪录片等）
* 候选按序号连续排列，而不是拆成多条海报消息。
* 尽量把能搜到的候选都收进一条消息。
* 若候选内容超过 Telegram 单条消息 `4096` 字硬上限，自动续发第二条消息，而不是直接截断。
* 仍保持 candidate-first 主线，不改成资源优先。

## Acceptance Criteria (evolving)

* [ ] Telegram 候选确认不再发送多张候选海报卡片。
* [ ] Telegram 候选确认改为一条聚合消息。
* [ ] 消息头展示查询词与总候选数。
* [ ] 海报预览入口在消息最上方。
* [ ] 候选标题是可点击 TMDB 链接。
* [ ] 候选正文不再带简介 / 原名，只保留名称、年份、类型。
* [ ] 超过 `4096` 字时，会自动续发第二条候选消息。
* [ ] 现有 candidate-first 主线不回退。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* PT 资源卡 Phase 1 现有实现方向
* 下载确认卡重设计
* adult BT
* 非 Telegram 渠道

## Technical Notes

* 重点文件：
  - `app/services/search_reply_formatter.py`
  - `app/bot/telegram_reply_formatter.py`
  - `app/bot/telegram_update_runtime.py`
  - `app/services/search_media.py`
* 当前在途的 PT 资源卡 task 是另一条实现线，提交时必须和这条候选确认线分组隔离。
