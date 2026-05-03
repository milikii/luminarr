# implement: telegram pt resource cards

## Goal

实现 Telegram PT 资源卡片的 Phase 1 版本。保持现有 `先锁定作品候选 -> 再搜 PT 资源 -> 再进入现有待确认下载路径` 的业务顺序不变，把 PT 资源交互从“文本日志 + select 1”升级到更接近 MoviePilot 的 `poster-first + button-first` 体验。

## What I already know

* 这轮已经通过 `/autoplan` 收口：
  * 不做 MoviePilot 行为克隆，只做选择性适配
  * Phase 1 不做分页
  * Phase 1 不重做 approval 卡协议
* 当前代码现状：
  * `search_resources_for_selected_media()` 会在作品锁定后返回 PT 资源文本，并把资源候选存进现有 chat 级 `candidate_mapping`
  * `telegram_delivery_runtime.py` 已支持 `send_message(parse_mode="HTML")`、`send_photo(..., reply_markup=...)`
  * `telegram_update_runtime.py` 已有 Telegram richer card path，但当前候选按钮和 callback 仍大量依赖裸数字 / 纯文本路由
* 工程 review 已确认：不能复用裸数字 callback + chat 级缓存来承载 PT 资源卡按钮状态，否则旧卡会误点中新搜索的 `selection_index`

## Requirements

* 只覆盖 Telegram 普通影视 PT 资源交互，不改 adult BT，不改其他渠道。
* 保持 candidate-first 主线：先锁定作品，后展示 PT 资源卡。
* Phase 1 只做：
  * Telegram PT 资源卡渲染
  * Telegram 专用 PT card session / snapshot 状态层
  * 资源选择按钮
  * 旧卡失效 / 原消息按钮移除
  * 进入现有 pending approval 路径
* Phase 1 明确不做：
  * 分页
  * 下载确认卡重设计
  * 跨渠道抽象统一
  * adult BT

## PT Card State Contract

最低字段：

* `session_token`
* `chat_id`
* `message_id`
* `resource_snapshot_id`
* `resource_items`
* `selected_index`
* `consumed_at`
* `expires_at`
* `status` (`active / selected / cancelled / expired`)

约束：

* callback data 使用短 token，不复用裸数字
* 同一张卡首次消费后，必须 edit 原消息移除或替换按钮
* 新搜索覆盖 chat 级候选缓存时，旧 PT 资源卡 callback 仍必须安全失效

## UX Requirements

* 有海报时优先 `send_photo(photo=poster, caption=html, reply_markup=keyboard)`
* 无海报时降级 `send_message(text=html, reply_markup=keyboard)`
* 有海报时每页最多展示 `3` 条资源；无海报时最多 `5` 条
* 每条资源最多 `2` 行正文
* 按钮文案目标上限 `18` 个可见字符
* 资源展示的关键字段：
  * 标题
  * 画质 / source shorthand
  * 大小
  * 做种数
  * 站点

## Acceptance Criteria

* [ ] 用户锁定作品后，Telegram 返回 PT 资源卡片，而不是纯文本日志块
* [ ] 用户通过按钮选择资源，不再依赖手打 `select 1`
* [ ] 资源按钮点击后，旧卡会失效，不会误命中新搜索缓存
* [ ] callback token 长度始终 < 64 bytes
* [ ] 资源按钮点击后，进入现有 pending approval 路径，不改 approval 真相
* [ ] 非 Telegram 渠道不回退

## Out of Scope

* PT 资源分页
* approval card 重设计
* adult BT
* Feishu / WeCom / personal WeChat
* 通用 `DeliveryItem` 大改

## Technical Notes

* 参考计划：
  * `docs/plans/2026-05-02-moviepilot-telegram-pt-resource-interaction.md`
  * `docs/plans/2026-05-02-moviepilot-telegram-pt-resource-interaction-test-plan.md`
* 重点文件：
  * `app/services/search_reply_formatter.py`
  * `app/services/search_media.py`
  * `app/runtime/delivery.py`
  * `app/bot/telegram_delivery_runtime.py`
  * `app/bot/telegram_update_runtime.py`
  * `app/bot/private_chat_selection_runtime.py`
  * `app/bot/telegram_runtime_adapter.py`
  * `app/db/candidate_repo.py`
