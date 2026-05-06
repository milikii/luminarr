# telegram download card and live progress sync

## Goal

先把 Telegram 渠道里的“已添加下载”成功消息改成更清晰、更可复制、更像卡片的文本样式；实时下载进度编辑后置为下一刀，不在这一轮一起实现。

## What I already know

* 当前“已添加下载”文案来自 `app/services/add_to_downloader.py`
  - 形态是三行纯文本：
    - `已添加下载：标题`
    - `任务 ID: ...`
    - `任务 Hash: ...`
* Telegram 发送能力目前只有统一 `send_message`
  - `app/bot/telegram_delivery_runtime.py`
* 当前没有通用的 Telegram 消息编辑能力
  - 也没有 `task_hash -> message_id` 的持久化真相
* `get_download_status.py` 已经能算出：
  - 进度
  - 下载速度
  - ETA
  但这只是手动 `status` 查询渲染，不是后台编辑已有消息
* 用户希望的完整终态包括：
  - 已添加下载消息更美观
  - 后续同消息实时进度条
* 这两件事已确认应拆成两刀：
  - 本轮只做“已添加下载消息卡片化”
  - 下一轮再做“同消息实时进度更新”
* 用户刚补充了当前 Phase A 的具体观感要求：
  - `status <hash>` 这条下一步命令要做成明显可复制样式
  - 成功消息里要补“这是哪个下载器”的标识
  - 需要给未来进度条留视觉位置，但本轮不真正做实时同步
  - 当前符号和排版还不够好看，需要继续压缩成更清晰的下载卡片
  - 进度区不能伪装成已经有实时刷新，只能诚实做“下一阶段接入”的占位态

## Assumptions (temporary)

* Telegram-specific formatting is acceptable in this slice
* This slice should not change downloader/import truth or background scheduler behavior
* Existing non-Telegram channels should not be expanded in this task

## Open Questions

* 当前没有阻塞性开放问题。

## Requirements (evolving)

* 只改 Telegram 渠道的“已添加下载”成功消息观感
* 标签/值层次要更清晰
* `task id` / `task hash` 要更便于复制
* `status <hash>` 提示要在 Telegram 里呈现成明显的可复制块
* 要显示下载器标识（至少 downloader name / type 的可见信息）
* 要为下一轮进度条预留视觉区块，但不接入实时编辑
* 进度区必须是明确占位态，不能展示虚构的百分比、速度或 ETA
* 不在正文里塞原始长 URL
* 不引入实时编辑、消息跟踪、节流或新的持久化真相

## Acceptance Criteria (evolving)

* [ ] Telegram “已添加下载”成功消息不再是三行平铺纯文本
* [ ] 任务 ID / Hash 在 Telegram 里有明显的可复制视觉区分
* [ ] `status <hash>` 有明显的复制导向展示
* [ ] 消息里能看出当前下载器标识
* [ ] 视觉结构已经为后续进度条预留位置
* [ ] 进度区明确表达“下一阶段接入”，而不是伪装成真实动态数据
* [ ] 现有自动下载成功链路测试继续通过
* [ ] 不改变下载投递真相和后续 auto-import 行为

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* Telegram 同消息实时进度编辑
* 下载进度条、速度、ETA 的后台主动同步
* `task_hash -> message_id` 持久化真相
* Feishu / personal WeChat / WeCom 的下载成功消息改版
* 下载器、导入器、cleanup、scheduler 行为改造

## Technical Notes

* Current text source:
  - `app/services/add_to_downloader.py`
* Current Telegram delivery path:
  - `app/bot/telegram_delivery_runtime.py`
  - `app/bot/telegram_reply_formatter.py`
* Existing status/progress rendering reference:
  - `app/services/get_download_status.py`
* Downloader identity already exists in pending-add/build path and can be reused for presentation:
  - `downloader_name`
  - `downloader_type`
* Preferred Phase A target shape:
  - status header
  - resource title block
  - downloader block
  - task id/hash copy blocks
  - reserved progress block with explicit placeholder copy
  - copy-friendly `status <hash>` footer
