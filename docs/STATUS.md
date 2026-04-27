# Current status (v512)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮连续完成 10 个最小闭环：把 `import_confirmed_media_identity`、`import_confirm_context_guard`、`add_confirm_context_state`、`add_confirm_job_state`、`import_cancel_state`、`import_confirm_expiry_state`、`import_job_state`、`add_pending_context`、`add_confirm_approval_state`、`import_approval_state` 的手写 ANSI 日志收口到共享 `emit_operational_log` 边界。
- 本轮 focused tests 已通过；`make quality`、`make verify-mainline` 已通过。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 已覆盖 BT direct / processing path / classification / TMDB association / raw destination / read-only / BT source 日志路径。
- `make quality` 通过（`27 passed in 0.15s`），`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- 导入相关 focused：`tests/test_import_confirmed_media_identity.py tests/test_import_to_library.py -k media_identity`
- 导入相关 focused：`tests/test_import_to_library.py -k rebuild_confirm_context or confirm_import_by_task_ref_returns_state_unavailable_when_stale_target_lookup_fails`
- 下载相关 focused：`tests/test_add_to_downloader.py -k rebuild_confirm_context or handle_expired_pending_confirm or confirm_add_by_task_ref_returns_state_unavailable_on_context_lookup_failure`
- 下载相关 focused：`tests/test_add_to_downloader.py -k claim_pending_job or restore_pending_job or mark_completed_job`
- 导入相关 focused：`tests/test_import_to_library.py -k cancel_pending_import or handle_expired_pending_confirm or import_cancel`
- 导入相关 focused：`tests/test_import_to_library.py -k confirm_import_by_task_ref_returns_state_unavailable_when_expiry_lookup_fails or handle_expired_pending_confirm`
- 导入相关 focused：`tests/test_import_to_library.py -k record_pending_job or import_job_state`
- 下载 / 选择 context focused：`tests/test_add_pending_context.py tests/test_add_to_downloader.py -k pending_job_result_missing or build_from_source`
- 下载审批 focused：`tests/test_add_to_downloader.py -k resolve_pending_lease_version or find_version_stale_rejection_text`
- 导入审批 focused：`tests/test_import_to_library.py -k record_pending_approval or record_import_approval`
- 上轮质量门快照：`27 passed, 0 skipped`
- 本轮质量门：`27 passed in 0.15s`
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
