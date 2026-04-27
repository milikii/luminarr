# Current status (v506)

## Current mainline
- **质量硬化** 继续保持完成态；**文档入口收口 / 当前真相对齐** 已完成并推送；当前切回 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮连续 9 个代码闭环继续收口下载确认/取消、导入确认/取消、shared confirm 路由、下载 follow-up、watchlist、BT subscription repo support、导入 job 和导入命名真相边界；这些路径不再吞泛 `Exception`，只兜明确 `ApprovalPersistenceError` / `JobPersistenceError` / `JobEventPersistenceError` / `DownloadMonitorPersistenceError` / `WatchlistPersistenceError` / `BtSubscriptionPersistenceError` 或 `sqlite3.Error`。第 10 个闭环同步当前文档和会话落盘。
- 本轮继续收口 5 处状态/下载 follow-up 边界：`status_follow_up` 的下载观察、完成观察事件，`post_download_auto_import` 的成人资源历史查找，`get_download_status` 的下载器查询，`download_follow_up_runtime` 的待完成轮询列表；这些路径不再吞泛 `Exception`，只兜明确 repo persistence、SQLite、下载器/路由/HTTP 或本地状态异常。
- 本轮继续收口 12 处小异常边界：`search_request_context` 的搜索源失败日志、`web_source` 的搜索/分页/详情 HTTP 边界、`bt_read_only_display` 的 JavLibrary 只读补全和成人历史查询、`import_confirmed_media_identity` 的 job_event 回读、`add_adult_registry_state` 的成人待确认/下载状态登记、`import_context_lookup` 的 job/approval/raw BT 回读；这些路径不再吞泛 `Exception`，只兜明确 HTTP、JSON、repo persistence 或 SQLite 异常。
- 本轮继续收口 10 处状态边界：`search_candidate_state` 的持久化/回读/回滚边界、`search_clarification_state` 的持久化/回读/清理边界，统一收窄为 `CandidatePersistenceError` / `ClarificationPersistenceError` 和 `sqlite3.Error`，不再吞泛 `Exception`。
- 本轮继续收口 Telegram 出站与去重边界：`telegram_update_runtime` 只兜 `TelegramUpdatePersistenceError` / `sqlite3.Error`，去重结果缺失也改为专用异常；`telegram_delivery_runtime` 只兜 `TelegramError`。
- 本轮连续收掉 10 处持久化/回读边界：`ImportEventRecorder`、`ImportApprovalState` 的 pending / approve / restore / executed / pending lease / stale target / expiry / event lookup 分支，以及 `ImportPendingWriteThroughState` 的取消回退分支；都改成只兜 `ApprovalPersistenceError`、`JobEventPersistenceError` 或 `sqlite3.Error`，不再吞泛 `Exception`。
- 本轮已收掉 5 个小单消费者 support 文件：`bt_subscription_dispatch_support.py`、`bt_subscription_last_seen_support.py`、`bt_subscription_scan_support.py`、`bt_subscription_scheduler_support.py`、`search_media_batch_preview_support.py`。
- 本轮已收窄 3 处异常边界：import transfer 残留清理只捕获文件 I/O 异常，TMDB fallback 只捕获 HTTP/JSON 响应异常，WeCom base64 解码只捕获 `binascii.Error`。
- 成人 BT 不是空白：当前已有 PT/BT 分流、BT 成人链问询、成人归档目录配置、`adult_content_registry`、归档保留期清理、只读补全和展示基础；但成人 BT 继续扩功能不是本轮主线。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支最近业务回归保持绿灯；本轮 focused tests 已覆盖 add/download confirm、import confirm/cancel、watchlist、BT subscription、导入命名真相和 private confirm 路由。
- 下一轮如果继续质量债，优先挑 `post_download_auto_import` 剩余成人归档/终态/skip event 边界、`status_follow_up` 剩余终态事件边界、日志打印边界或 `main()` DI；不要为了凑数字强拆剩余大 support 文件。

## Latest verification
- `tests/test_add_to_downloader.py`：`112 passed`
- `tests/test_import_to_library.py`：`149 passed`
- `tests/test_add_execution_follow_up.py`：`10 passed`
- `tests/test_manage_watchlist.py`：`20 passed`
- `tests/test_manage_bt_subscription.py`：`38 passed`
- `tests/test_private_chat_confirm_runtime.py`：`3 passed, 4 warnings`
- `tests/test_private_chat_frustration_runtime.py tests/test_private_chat_runtime.py -k "handle_frustration_query or cancel or pending_job_lookup_failure"`：`16 passed, 46 deselected, 4 warnings`
- `make quality`：通过（`27 passed`）
- `make verify-mainline`：通过
- `tests/test_get_download_status.py tests/test_download_follow_up_runtime.py`：`58 passed, 4 warnings`
- `make quality`：通过（`27 passed`）
- `make verify-mainline`：通过
- `tests/test_bt_sources.py tests/test_bt_read_only_display.py tests/test_import_confirmed_media_identity.py tests/test_import_context_lookup.py`：`31 passed`
- `tests/test_search_media.py -k "javlibrary_lookup_fails or search_backend_failure or tmdb_failed or tmdb_failure" tests/test_add_to_downloader.py -k "adult_pending_registry_failure" tests/test_add_execution_follow_up.py -k "adult_content_downloading_failure" tests/test_import_to_library.py -k "correlation_lookup or raw_bt or rebuild_confirm_context"`：`14 passed, 442 deselected`
- `make quality`：通过（`27 passed`）
- `make verify-mainline`：通过
- `tests/test_search_media.py -k "candidate or clarification"`：`48 passed, 137 deselected`
- `tests/test_telegram_runtime_adapter.py tests/test_telegram_delivery_runtime.py`：`13 passed, 4 warnings`
- `tests/test_telegram_bot.py -k "telegram_media_sender"`：`4 passed, 190 deselected`
- `make quality`：通过（`27 passed`）
- `make verify-mainline`：通过
- `tests/test_import_pending_write_through_state.py`：`3 passed`
- `tests/test_import_to_library.py tests/test_import_pending_write_through_state.py`：`152 passed`
- `tests/test_cleanup_docs_consistency.py`：`8 passed`
- `tests/test_import_to_library.py -k "copy_fallback or hardlink or target_exists or import_transfer"`：`12 passed, 137 deselected`
- `tests/test_persistence_sqlite.py -k "copy_fallback_pending_survives_restart_and_second_confirm_copies or unexpected_hardlink"`：`1 passed, 110 deselected`
- `tests/test_search_media.py -k "tmdb_failed or tmdb_failure"`：`2 passed, 183 deselected`
- `tests/test_manage_bt_subscription.py tests/test_bt_subscription_*_support.py`：`48 passed`
- `tests/test_search_media_batch_preview_support.py tests/test_search_media.py -k "bt_batch_preview or batch_preview or page_url"`：`70 passed, 118 deselected`
- `tests/test_wecom_adapter.py`：`33 passed, 4 warnings`
- `tests/test_config.py`：`39 passed, 0 skipped`
- `tests/test_config.py tests/test_downloader_route_lookup.py tests/test_main.py`：`71 passed, 4 warnings`
## Current biggest risk
- 剩余 broad `except Exception` 里还有一部分是外部服务降级边界和若干运行时 wrapper，不能机械替换；下一步必须逐个按真实异常类型和测试覆盖判断。
- 当前成人 BT 后续仍可作为候选主线，但默认不切功能；继续质量债时以“最小、可验证、不扩协议”为准。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是质量债硬化。优先从剩余 broad except、日志打印边界或 `main()` DI 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
