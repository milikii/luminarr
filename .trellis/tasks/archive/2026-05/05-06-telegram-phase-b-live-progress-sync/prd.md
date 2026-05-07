# telegram phase b live progress sync

## Goal

在 Telegram 渠道里，把“已添加下载”成功消息升级成**同消息实时进度同步**：下载开始后记录可编辑消息 `message_id`，后台状态轮询时优先编辑这一条消息，展示真实进度、速度和 ETA，而不是再额外刷一堆新消息。

## What I already know

* Phase A 已经完成：
  * Telegram 下载成功消息已卡片化
  * `task id/hash` 可复制
  * 下载器标识可见
  * 进度区当前只是占位态
* 当前并没有：
  * `task_hash -> message_id` 的持久化真相
  * 通用 `edit_message_text` Telegram 发送能力
  * 后台状态同步节流策略
* 当前已有可复用能力：
  * `download_monitor` 能持久化任务进度真相
  * `get_download_status.py` 能计算并渲染真实进度、速度、ETA
  * Telegram PT 资源卡已经会记录 `message_id`
  * `download_follow_up_runtime` 已有后台轮询节拍

## Assumptions (temporary)

* 本轮只支持 Telegram
* Phase B 允许新增最小的消息跟踪真相
* 实时进度同步以“编辑已有消息”为主，不额外生成高频新消息

## Open Questions

* 当前没有阻塞性开放问题。

## Requirements (evolving)

* 为 Telegram 下载成功消息记录可编辑 `message_id`
* 建立 `task_hash / task_id / chat_id -> telegram message id` 的最小可恢复真相
* 后台下载状态轮询时，优先编辑该消息
* 进度文案至少包含：
  * 百分比
  * 下载速度
  * ETA
* 需要有节流/去重策略，避免高频编辑
* 下载完成后切到完成态，不再继续编辑

## Acceptance Criteria (evolving)

* [ ] Telegram 下载成功消息的 `message_id` 被成功记录
* [ ] 后台轮询能编辑该消息并展示真实进度
* [ ] 编辑频率有节流，不会每次轮询都硬刷
* [ ] 下载完成后消息能进入稳定完成态
* [ ] 现有下载/导入真相与非 Telegram 渠道不回退

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* Feishu / personal WeChat / WeCom 的同消息进度同步
* 下载器、导入器、cleanup 业务语义改造
* Telegram 进度图表、图片卡片、复杂交互按钮体系
* 跨渠道统一消息跟踪平台

## Technical Notes

* Current Telegram send path:
  - `app/bot/telegram_delivery_runtime.py`
* Current status/progress data:
  - `app/services/get_download_status.py`
  - `app/db/download_monitor_repo.py`
* Existing Telegram message id precedent:
  - `app/services/telegram_pt_resource_cards.py`
  - `app/bot/telegram_update_runtime.py`
* Existing background polling path:
  - `app/bot/download_follow_up_runtime.py`
