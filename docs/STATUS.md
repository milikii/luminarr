# Current status (v513)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮连续完成 10 个最小闭环：把 `import_pending_write_through_state`、`add_pending_presence_state`、`refresh_media_server`、`import_prepare_state`、`search_candidate_state`、`search_clarification_state`、`bt_sources`、`import_post_processing`、`search_media`、`bt_read_only_display` 的手写 ANSI 日志收口到共享 `emit_operational_log` 边界。
- 本轮同时修复下载器投递失败边界：`add_torrent_func` 抛出运行时 / HTTP 错误时，`confirm add` 重新返回明确失败文本并触发既有审批回退，不再把 downloader dispatch 异常泄出到调用方。
- 本轮 focused tests 已通过；`make quality`、`make verify-mainline` 已通过。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 已覆盖导入待确认、下载待确认、媒体刷新、导入准备、搜索候选/澄清态、BT source、导入后处理、BT read-only 展示和 downloader dispatch 失败路径。
- `tests/test_add_to_downloader.py` 通过（`112 passed in 0.69s`）。
- `make quality` 通过（`27 passed in 0.14s`），`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- 导入待确认 focused：`tests/test_import_pending_write_through_state.py`
- 下载待确认 focused：`tests/test_add_to_downloader.py::test_has_pending_add_logs_job_lookup_failure tests/test_add_to_downloader.py::test_has_pending_add_uses_in_memory_pending_when_job_lookup_fails`
- 私聊下载待确认 focused：`tests/test_private_chat_runtime.py::test_dispatch_private_chat_text_stops_on_downloader_pending_lookup_failure`
- 媒体刷新 focused：`tests/test_refresh_media_server.py`
- 导入准备 / 后处理 focused：`tests/test_import_to_library.py::test_prepare_import_logs_query_failure tests/test_import_to_library.py::test_prepare_import_logs_source_missing tests/test_import_to_library.py::test_confirm_import_metadata_scrape_exception_does_not_break_import tests/test_import_to_library.py::test_confirm_import_subtitle_translate_exception_does_not_break_import tests/test_import_to_library.py::test_confirm_import_by_task_ref_success_with_refresh_success tests/test_import_to_library.py::test_confirm_import_by_task_ref_success_with_refresh_failure_text tests/test_import_to_library.py::test_confirm_import_by_task_ref_success_with_refresh_exception`
- 搜索状态 focused：`tests/test_search_media.py` candidate / clarification / BT read-only / BT batch preview 相关 focused tests 通过。
- BT source / BT read-only display focused：`tests/test_bt_sources.py`、`tests/test_bt_read_only_display.py`
- 下载确认回归：`tests/test_add_to_downloader.py`（`112 passed in 0.69s`）
- 本轮质量门快照：`27 passed, 0 skipped`
- 本轮质量门：`27 passed in 0.14s`
- 本轮主线门：`make verify-mainline` 通过

## Current biggest risk
- 剩余 broad `except Exception` 中仍有一部分是外部服务降级、网络/LLM/TMDB/search wrapper、后台 task loop 或 webhook 边界；不能机械替换。
- 继续施工时应优先挑有 focused tests 的 repo/SQLite 持久化边界，或先补最小测试再收口。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是质量债硬化。优先从剩余 broad except、日志打印边界或 `main()` DI 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
