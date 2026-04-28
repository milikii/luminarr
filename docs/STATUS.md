# Current status (v543)

## Current mainline
- **质量硬化** 已收工；当前是在不回退质量硬化结果的前提下推进 **services 层数据结构降本**。
- 当前唯一主线是 **services 层数据结构降本**。
- 本轮已把 `add_pending_persistence.py` 合并回 `app/services/add_to_downloader.py`，删除只被一处消费的待确认落盘薄壳。
- 本轮已把 `add_request_facade.py` 合并回 `app/services/add_to_downloader.py`，删除只被一处消费的请求转发薄壳。
- 本轮已把 `add_confirm_preparation.py` 合并回 `app/services/add_to_downloader.py`，删除只被一处消费的确认准备薄壳。
- 本轮已把 `add_confirm_availability_state.py` 合并回 `app/services/add_to_downloader.py`，删除只被一处消费的确认可用性薄壳。
- 本次连续推进 10 轮已完成一组最小闭环，范围只限 shared helper 收口和单消费者状态壳回收；**没有**改协议、SQLite schema、调度语义、下载/导入/刷新真相边界。
- 本轮主题性收口：
  - watchlist / BT 订阅共享的 `media kind`、`title (year-or-dash)` 展示、命令 tail / action parse 已收口到 `app/services/media_kind.py`、`media_item_display.py`、`command_parsing.py`。
  - `search_media.py` 与 `manage_bt_subscription.py` 的纯转发别名已删除，测试直接指向真实实现。
  - 导入链多组单消费者状态壳已合并回 `app/services/import_to_library.py`：metadata title/year、raw_bt guard、confirm context、event recorder、pending write-through、confirmed media identity、job state、cancel state、confirm expiry、confirm preparation、confirm execution tail。
  - add 链单消费者状态壳已合并回 `app/services/add_to_downloader.py`：pending presence、pending write-through、confirm execution tail、pending persistence、request facade、confirm preparation、confirm availability。
- `cleanup_*_support.py` 当前为 `0` 个。
- `cleanup_*_support.py` 继续保持 `0` 个；`*_support.py` 只剩 `approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py` 这 4 个较大边界，当前不机械强拆。

## Current health
- 十轮 focused tests 均已通过。
- 最近一轮稳定总 gate 基线仍是 `make quality` -> `27 passed, 0 skipped`。
- 收尾阶段暴露的 `render_add_pending_reply` 漏导入与 `STATUS.md` 长度超限都已修正。
- 当前总 gate 已恢复可复验：`make quality` 通过，`make verify-mainline` 通过。
- 本轮 focused tests：`tests/test_add_to_downloader.py -k "approval_pending or add_pending_state_unavailable or persist_pending_add or pending_add"`，`15 passed, 97 deselected`。
- 本轮 focused tests：`tests/test_add_to_downloader.py -k "add_by_selection or add_by_batch_selection or add_candidate_source or add_bt_source"`，`17 passed, 95 deselected`。
- 本轮 focused tests：`tests/test_add_to_downloader.py -k "confirm_add_by_task_ref or expired_pending or confirm_not_pending or state_unavailable"`，`47 passed, 65 deselected`。

## Latest verification
- `make quality` 通过（`27 passed, 0 skipped`）。
- `make verify-mainline` 通过。
- `tests/test_add_to_downloader.py -k "approval_pending or add_pending_state_unavailable or persist_pending_add or pending_add"` 通过（`15 passed, 97 deselected`）。
- `tests/test_add_to_downloader.py -k "add_by_selection or add_by_batch_selection or add_candidate_source or add_bt_source"` 通过（`17 passed, 95 deselected`）。
- `tests/test_add_to_downloader.py -k "confirm_add_by_task_ref or expired_pending or confirm_not_pending or state_unavailable"` 通过（`47 passed, 65 deselected`）。
- `tests/test_import_pending_write_through_state.py tests/test_import_to_library.py -k "import_by_task_ref or record_pending_approval or pending_state_unavailable or copy_fallback_pending"` 通过（`50 passed, 106 deselected`）。
- `tests/test_import_confirmed_media_identity.py tests/test_import_to_library.py -k "resolve_metadata_title_year or extract_title_year_for_scrape or import_confirmed_media_identity"` 通过（`9 passed, 148 deselected`）。
- `tests/test_import_to_library.py -k "record_pending_job or claim_pending_job or restore_pending_job or mark_completed_job or confirm_import_by_task_ref_executes_after_pending or finalization_warning"` 通过（`14 passed, 139 deselected`）。
- `tests/test_import_to_library.py tests/test_private_chat_runtime.py -k "cancel_pending_import or import_cancel_state_unavailable"` 通过（`12 passed, 198 deselected`，有既有三方库 warning）。
- `tests/test_import_to_library.py -k "is_pending_approval_expired or handle_expired_pending_confirm or 导入确认超时"` 通过（`7 passed, 146 deselected`）。
- `tests/test_import_to_library.py -k "confirm_import_by_task_ref or confirm_not_pending or stale_rejected or handle_expired_pending_confirm or is_pending_approval_expired"` 通过（`40 passed, 113 deselected`）。
- `tests/test_import_to_library.py -k "confirm_execute or confirm_finalize or copy_fallback_pending or finalization_warning or pending_copy_approval or import_failed"` 通过（`6 passed, 147 deselected`）。
- `tests/test_add_to_downloader.py -k "has_pending_add"` 通过（`3 passed, 109 deselected`）。
- `tests/test_add_to_downloader.py -k "approval_pending or add_pending_state_unavailable or persist_pending_add or pending_add"` 通过（`15 passed, 97 deselected`）。
- `tests/test_add_to_downloader.py -k "confirm_finalize or approval_confirmed or add_confirm_state_unavailable or mark_completed_job or confirm"` 通过（`41 passed, 71 deselected`）。

## Current biggest risk
- 当前风险不是业务回归，而是 services 层仍有剩余重复结构；下一轮仍需维持“小 diff + focused tests + 文档同步”的节奏，避免重新把 STATUS/NEXT_STEP 写回历史流水账。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线仍是 services 层数据结构降本。优先找剩余单消费者状态壳、重复 parse/display helper 或稳定数据结构收口点；不要重建已删的小文件，不改协议或 SQLite 真相边界。
```
