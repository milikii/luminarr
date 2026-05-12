# restore telegram candidate poster cards

## Goal

恢复 Telegram 搜索影片信息时的候选海报图片卡片消息流：每个候选继续走图片卡片/失败退文，最后只保留精简确认文本；不要再走“首个候选单独海报 + 聚合纯文本确认”的错误方向。

## What I already know

* 用户反馈：发送搜索影片信息后，候选确认被错误改成“首个候选海报 + 聚合纯文本”，不再是逐候选图片卡片。
* 相关 contracts 在 `.trellis/spec/backend/telegram-candidate-card-contracts.md`。
* 相关代码集中在：
  * `app/services/search_reply_formatter.py`
  * `app/bot/telegram_reply_formatter.py`
  * `app/bot/telegram_update_runtime.py`
  * `tests/test_search_media.py`
  * `tests/test_telegram_reply_formatter.py`

## Requirements

* 修复后恢复预期的 Telegram 候选海报卡片/图片交付。
* 恢复“逐候选图片卡片 + 最后一条精简确认文本”这一条 UX，不再保留首候选 special-case aggregate 路线。
* 保持后续的数字选择语义、候选排序、TMDB/fanart 补全和资源搜索时序不变。
* 不顺手改 PT 资源卡、成人资源卡、下载成功卡等无关链路。

## Acceptance Criteria

* [x] Telegram 搜索影片信息时恢复逐候选海报图片卡片行为
* [x] 相关测试新增/更新并通过
* [x] `make lint`、`make quality`、`make verify-mainline` 继续通过

## Out of Scope

* PT 资源卡链路
* 成人 BT 卡片链路
* 搜索结果排序/候选选择业务逻辑改造

## Technical Notes

* 相关 spec：
  * `.trellis/spec/backend/index.md`
  * `.trellis/spec/backend/telegram-candidate-card-contracts.md`
  * `.trellis/spec/backend/quality-guidelines.md`
