# Current status (v509)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮按文档连续完成 10 个最小闭环：成人归档操作失败明确为 `AdultArchiveOperationError`，并收口下载状态 completion/auto-import 日志、refresh 日志、导入后处理 metadata/subtitle/refresh 日志、BT 订阅 list/run/scheduler 读取日志边界。
- 成人归档上层不再用泛 `Exception` 判断归档/清理失败；文件搬运、下载器删除和本地源清理失败进入明确操作失败文本，持久化失败仍保持状态不可用边界。
- 默认分支协议、SQLite schema、下载/导入/审批语义未变化；本轮主要是异常类型和日志边界收口。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 覆盖 adult archive operation failure、status follow-up、refresh、import post-processing 和 BT subscription 日志路径。
- `make quality` 通过，`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
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

## Current biggest risk
- 剩余 broad `except Exception` 中仍有一部分是外部服务降级、网络/LLM/TMDB/search wrapper、后台 task loop 或 webhook 边界；不能机械替换。
- 继续施工时应优先挑有 focused tests 的 repo/SQLite 持久化边界，或先补最小测试再收口。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是质量债硬化。优先从剩余 broad except、日志打印边界或 `main()` DI 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
