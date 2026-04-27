# Current status (v510)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮按文档连续完成 10 个最小闭环：`search_clarification_state`、`add_pending_presence_state`、`import_pending_write_through_state`、`add_confirm_job_state`、`import_cancel_state`、`import_confirm_expiry_state`、`search_candidate_state`、`add_confirm_context_state`、`import_prepare_state`、`private_chat_cleanup_runtime` 的日志边界统一到共享 operational logging helper；同时把几个测试夹具的通用 `RuntimeError("db down")` 收回到明确的 persistence error 类型。
- 成人归档上层不再用泛 `Exception` 判断归档/清理失败；文件搬运、下载器删除和本地源清理失败进入明确操作失败文本，持久化失败仍保持状态不可用边界。
- 默认分支协议、SQLite schema、下载/导入/审批语义未变化；本轮主要是异常类型和日志边界收口。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 已覆盖 search clarification、pending add、import pending write-through、downloader confirm/job、import cancel/expiry、candidate、confirm context、import prepare 和 cleanup runtime 日志路径。
- `make quality` 通过，`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- `tests/test_trace_logging.py`：`3 passed`
- `tests/test_cleanup_smoke_logging.py tests/test_trace_logging.py`：`9 passed`
- `tests/test_refresh_media_server.py`：`4 passed`
- `tests/test_import_to_library.py -k "metadata or subtitle_translate_exception or refresh_exception or refresh_failure_text or refresh_success"`：`11 passed, 139 deselected`
- `tests/test_search_media.py -k "bt_read_only or bt_batch_preview"`：`83 passed, 102 deselected`
- `tests/test_bt_read_only_display.py`：`5 passed`
- `tests/test_get_download_status.py -k "auto_import_terminal or completion_event or parse_status_query or get_status_text_success"`：`7 passed, 40 deselected`
- `tests/test_download_follow_up_runtime.py`：`13 passed`
- `tests/test_bt_sources.py`：`18 passed`
- `tests/test_manage_bt_subscription.py -k "scan or scheduler or list"`：`18 passed, 20 deselected`
- `make quality`：通过（`27 passed, 0 skipped`）
- `make verify-mainline`：通过
- `tests/test_private_chat_confirm_runtime.py tests/test_private_chat_frustration_runtime.py tests/test_private_chat_bt_read_only_runtime.py tests/test_private_chat_runtime.py -k "handle_confirm_query or handle_frustration_query or handle_bt_read_only_query or bt_processing_path"`：`19 passed, 51 deselected`
- `make quality`：通过（`27 passed, 0 skipped`）
- `make verify-mainline`：通过
- `tests/test_adult_archive_service.py tests/test_get_download_status.py -k "adult_archive_service or adult_archive"`：`7 passed, 45 deselected`
- `tests/test_get_download_status.py -k "completion_event"`：`4 passed, 43 deselected`
- `tests/test_get_download_status.py -k "auto_import_terminal or adult_archive_state_is_unavailable or auto_import_follow_up or completion_event"`：`5 passed, 42 deselected`
- `tests/test_refresh_media_server.py`：`4 passed`
- `tests/test_import_to_library.py -k "metadata or subtitle_translate_exception or refresh_exception"`：`9 passed, 141 deselected`
- `tests/test_import_to_library.py -k "subtitle_translate"`：`2 passed, 148 deselected`
- `tests/test_import_to_library.py -k "refresh_exception or refresh_failure_text or refresh_success"`：`3 passed, 147 deselected`
- `tests/test_manage_bt_subscription.py -k "list"`：`6 passed, 32 deselected`
- `tests/test_manage_bt_subscription.py tests/test_bt_subscription_scan_support.py -k "scan"`：`10 passed, 32 deselected`
- `tests/test_manage_bt_subscription.py tests/test_bt_subscription_scheduler_support.py -k "scheduler or chat"`：`12 passed, 29 deselected`
- `make quality`：通过（`27 passed, 0 skipped`）
- `make verify-mainline`：通过
- `tests/test_private_chat_runtime.py tests/test_search_media.py -k "clarification"`：`15 passed`
- `tests/test_private_chat_runtime.py -k "downloader_pending_lookup_failure or confirm_routes"`：`1 passed`
- `tests/test_import_pending_write_through_state.py`：`3 passed`
- `tests/test_add_to_downloader.py -k "claim_pending_job or restore_pending_job or mark_completed_job"`：`9 passed, 103 deselected`
- `tests/test_import_to_library.py -k "cancel_pending_import or import_cancel"`：`11 passed, 139 deselected`
- `tests/test_import_to_library.py -k "expired or expiry or approval_expired or confirm_import_by_task_ref_returns_expired"`：`9 passed, 141 deselected`
- `tests/test_search_media.py tests/test_private_chat_runtime.py -k "candidate or digit_stops_on_clarification_lookup_failure or candidate_clear_failure"`：`39 passed, 203 deselected`
- `tests/test_add_to_downloader.py -k "context_lookup or context_row_corruption or context_payload_corruption or approval_lookup_fails or approval_row_missing or expiry_lookup_fails or expired"`：`16 passed, 96 deselected`
- `tests/test_import_to_library.py -k "import_by_task_ref or import_source_missing or import_query_failed or import_target_exists or prepare_target"`：`44 passed, 106 deselected`
- `tests/test_private_chat_runtime.py tests/test_private_chat_cleanup_runtime.py -k "cleanup_replies_service_not_ready or cleanup_routes_to_cleanup_service or handle_cleanup_query"`：`4 passed, 57 deselected`
- `make quality`：通过（`27 passed, 0 skipped`）
- `make verify-mainline`：通过

## Current biggest risk
- 剩余 broad `except Exception` 中仍有一部分是外部服务降级、网络/LLM/TMDB/search wrapper、后台 task loop 或 webhook 边界；不能机械替换。
- 继续施工时应优先挑有 focused tests 的 repo/SQLite 持久化边界，或先补最小测试再收口。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是质量债硬化。优先从剩余 broad except、日志打印边界或 `main()` DI 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
