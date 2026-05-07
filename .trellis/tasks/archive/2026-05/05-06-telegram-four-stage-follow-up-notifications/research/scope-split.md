# Scope split — Telegram four-stage follow-up notifications

## Current notification seam

- `app/services/import_transfer_execution.py` 在导入成功后调用 `ImportPostProcessingService.run(...)`。
- `ImportPostProcessingService` 目前只返回一个聚合 `reply_suffix`。
- `PostDownloadAutoImportService.run_auto_import_candidates(...)` 只把 `run_for_record()` 返回的单条字符串包装成 1 条 `AutoImportNotification`。
- `app/bot/download_follow_up_runtime.py` 后台轮询对 `result.notifications` 逐条发送，但当前每个任务只会产出 1 条。

## Chosen implementation direction

- 保留后台发送入口不变。
- 把“单条 reply”升级为“多条阶段通知 + 最终总结”。
- 尽量把拆分逻辑收口在 import 后处理链，不重写调度器和 Telegram send path。

## Boundary decisions

- 四段式定义固定为：
  1. 导入 / 硬链接
  2. 字幕翻译
  3. 媒体库刷新
  4. 最终总结
- metadata 不单独发第 5 条，避免扩大通知噪声。
- summary 继续包含 metadata，保证 operator 仍能一次看到完整后处理状态。

## Risks to watch

- 现有 `ImportExecutionResult.reply` 仍被其他路径直接返回，不能把用户即时 confirm 回复误伤成重复噪声。
- 阶段消息的顺序必须和真实执行顺序一致，尤其是“字幕 skipped / refresh skipped”场景。
- 不应改动 Telegram live progress polling 的原消息编辑判断。
