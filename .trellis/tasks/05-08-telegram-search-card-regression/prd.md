# restore telegram preferred poster search card

## Goal

恢复 Telegram 搜索影片信息时的首选海报图片卡片消息：先发首选海报图片卡片，再给候选确认文本；不要再退回成只有海报预览链接的普通文本消息。

## What I already know

* 用户反馈：发送搜索影片信息后，“又转回去”成没有首选海报图片的普通消息。
* 相关 contracts 在 `.trellis/spec/backend/telegram-candidate-card-contracts.md`。
* 相关代码集中在：
  * `app/services/search_reply_formatter.py`
  * `app/bot/telegram_reply_formatter.py`
  * `app/bot/telegram_update_runtime.py`
  * `tests/test_search_media.py`
  * `tests/test_telegram_reply_formatter.py`

## Requirements

* 修复后恢复预期的 Telegram 首选海报卡片/图片交付。
* 只恢复“首选海报图片卡片 + 候选确认文本”这一条 UX，不把所有候选都改成图片消息。
* 保持后续的候选确认文本、TMDB 链接和数字选择语义不变。
* 不顺手改 PT 资源卡、成人资源卡、下载成功卡等无关链路。

## Acceptance Criteria

* [ ] Telegram 搜索影片信息时恢复首选海报图片卡片行为
* [ ] 相关测试新增/更新并通过
* [ ] `make lint`、`make quality`、`make verify-mainline` 继续通过

## Out of Scope

* PT 资源卡链路
* 成人 BT 卡片链路
* 搜索结果排序/候选选择业务逻辑改造

## Technical Notes

* 相关 spec：
  * `.trellis/spec/backend/index.md`
  * `.trellis/spec/backend/telegram-candidate-card-contracts.md`
  * `.trellis/spec/backend/quality-guidelines.md`
