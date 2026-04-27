# Current status (v512)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮连续完成 10 个最小闭环：新增共享 `emit_operational_log`，并把 `add_cancel_state`、`add_pending_persistence`、`add_adult_registry_state`、`import_event_recorder`、`import_raw_bt_guard`、`get_download_status`、`status_follow_up`、`add_execution_follow_up`、`post_download_auto_import` 的手写 ANSI 日志收口到共享 operational formatter 边界。
- 本轮 focused tests、`make quality`、`make verify-mainline` 均已通过；下载/导入/刷新/BT 主线行为、协议和 SQLite 真相边界未变。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 已覆盖 BT direct / processing path / classification / TMDB association / raw destination / read-only / BT source 日志路径。
- `make quality` 通过，`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- BT pending / direct / classification / TMDB / raw destination focused：`77 passed, 194 deselected`
- BT read-only / history / JavLibrary / batch preview focused：`93 passed, 102 deselected`
- BT read-only runtime / BT source focused：`140 passed, 319 deselected`
- 本轮新增 focused：`tests/test_operational_logging.py`、`tests/test_add_to_downloader.py -k cancel_pending_add`、`tests/test_import_to_library.py -k record_event_logs/raw_bt`、`tests/test_get_download_status.py`、`tests/test_add_execution_follow_up.py`
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
