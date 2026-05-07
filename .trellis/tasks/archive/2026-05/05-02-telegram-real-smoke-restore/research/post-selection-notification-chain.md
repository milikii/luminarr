# Post-Selection Notification Chain Audit

Research date: 2026-05-03

## Goal

Clarify what the code currently does after a Telegram user selects a PT resource and proceeds into the downloader/import pipeline, with emphasis on user-visible notifications versus background-only state transitions.

## Findings

### 1. Resource confirm -> downloader dispatch

- `AddToDownloaderService.confirm_add_by_task_ref()` eventually returns downloader follow-up text from `AddExecutionFollowUpService.dispatch()`.
- Current user-visible success reply is:
  - `已添加下载：{title}`
  - `任务 ID: {task_id}`
  - `任务 Hash: {task_hash}`
- This is a direct reply to the `confirm` action, not a background push.

### 2. Download status

- User-visible status is currently explicit pull, not push:
  - `status <任务ID或Hash>`
- `GetDownloadStatusService.get_status_text()` renders a channel-aware status card/text reply when the user asks for status.
- Status reply includes a “refresh status” affordance rather than autonomous progress pushes.

### 3. Completion polling exists, but does not proactively notify the user

- `app/bot/download_follow_up_runtime.py` starts:
  - `post_download_auto_import_scheduler_loop()`
  - `download_completion_polling_loop()`
- Default interval is `300` seconds from `app/bot/telegram_sidecar_runtime.py`.
- Important behavior detail:
  - `download_completion_polling_loop()` calls `status_service.get_status_text(record.task_hash, chat_id=record.chat_id)`
  - return value is ignored
  - therefore the loop updates truth / follow-up state, but does **not** send periodic progress/completion messages to the user

### 4. Download complete -> auto-import

- When status observation sees a newly completed download, `PostDownloadAutoImportService.run_for_record()` may trigger auto-import.
- User-visible follow-up text can be:
  - `导入待确认：{name} ... 请发送 confirm {task_ref} 执行导入。`
- This can appear when the user manually requests `status`, because `get_status_text()` appends auto-import follow-up text to the status response.
- Background scheduler also computes auto-import candidates, but current scheduler loop does not actively send `result.replies` to the user.

### 5. Import confirm -> hardlink/copy + refresh

- `ImportToLibraryService.confirm_import_by_task_ref()` returns direct user-visible text on success/failure.
- Success reply always includes:
  - `导入成功：{name}`
  - `任务 ID: ...`
  - `任务 Hash: ...`
  - `目标路径: ...`
- If copy fallback is used, it adds:
  - `导入方式: 复制`
- If media server refresh is configured, refresh result is appended to the same reply:
  - `媒体库刷新成功。`
  - or a refresh failure text

### 6. Metadata scrape / subtitle translation

- `ImportPostProcessingService` executes metadata scrape and subtitle translation after import success.
- Both phases write `job_event` truth:
  - `metadata.succeeded` / `metadata.failed`
  - `subtitle.succeeded` / `subtitle.failed` / `subtitle.skipped`
- Current user-visible reply does **not** append metadata scrape success/failure text.
- Current user-visible reply does **not** append subtitle translation success/failure text.
- These are presently operational truth / event-trace facts, not chat-visible notifications.

## Current User-Visible Truth Matrix

| Stage | Current user-visible message? | Current delivery mode |
| --- | --- | --- |
| confirm 下载 | Yes | immediate reply |
| 下载进度更新 | Yes, but only if user sends `status` | manual pull |
| 下载完成 | No dedicated proactive completion push | background truth only unless user pulls `status` |
| auto-import pending | Yes in status-driven path | appended follow-up |
| confirm 导入 | Yes | immediate reply |
| 硬链接 / copy fallback | Yes | immediate reply |
| metadata 刮削 | No | event/log only |
| 字幕翻译 | No | event/log only |
| 媒体库刷新 | Yes | appended to import success reply |

## Implication

The current post-selection pipeline is partially observable in Telegram, but not fully conversational. The system already has backend follow-up state for completion polling and post-import processing, yet several steps remain event/log truth only rather than user-pushed notifications.
