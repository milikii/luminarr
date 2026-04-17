# Persistence closure log (v22)

> 目的：承接当前“持久化吞错收口”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环、focused tests 和 commit 轨迹优先记在这里。

## 1. Current line

- 当前唯一主线：持久化吞错收口
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`
- shared private-chat runtime 最小抽离已完成；四渠道都先走同一个 shared wrapper

## 2. Recent closed loops

### 2026-04-17 导入确认过期结果缺失分流缺口

- 闭环：`import_to_library._is_pending_approval_expired()` 在 `approval_repo.is_import_pending_expired()` 已经出现“待确认审批结果缺失”时，不再和普通 SQLite/approval 查询异常共用同一条“导入确认过期判断失败”日志；现在会单独打印“导入确认过期结果缺失”中文日志与 `[处理建议]`，并继续让 confirm 走原来的 `IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT` fail-closed 边界，不改审批真相和副作用。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "is_pending_approval_expired_logs_approval_lookup_failure or is_pending_approval_expired_logs_missing_approval_result or confirm_import_by_task_ref_returns_state_unavailable_when_expiry_lookup_fails"`

### 2026-04-17 导入目标路径查询结果缺失分流缺口

- 闭环：`import_to_library._find_latest_import_target_path()` 在 `job_event_repo.find_latest_import_correlation()` 返回链路里已经出现“关联查询结果缺失”时，不再和普通 SQLite/job_event 查询异常共用同一条“导入目标路径查询失败”日志；现在会单独打印“导入目标路径结果缺失”中文日志与 `[处理建议]`，并继续让 confirm 走原来的 `IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT` fail-closed 边界，不改导入真相和副作用。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "find_latest_import_target_path_logs_event_lookup_failure or find_latest_import_target_path_logs_missing_event_lookup_result or find_latest_import_target_path_logs_missing_structured_target or find_version_stale_rejection_text_returns_state_unavailable_when_event_lookup_fails"`

### 2026-04-17 导入确认任务回退结果缺失分流缺口

- 闭环：`import_to_library._restore_pending_job()` 在 `jobs.release_lease_to_pending()` 已经找不到任务行时，不再和普通 SQLite lease 回退异常共用同一条“导入确认任务回退失败”日志；现在会单独打印“导入确认任务回退结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的 confirm 错误恢复边界，不改审批真相和副作用。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "restore_pending_job_logs_persistence_failure or restore_pending_job_logs_missing_result or restore_pending_job_logs_rejected_current_state"`；`tests/test_import_to_library.py -k "promotes_pending_to_approved"`

### 2026-04-17 导入审批回退结果缺失分流缺口

- 闭环：`import_to_library._restore_pending_approval()` 在 `approval_repo.restore_import_pending()` 返回 `None` 时，不再把空结果静默当成审批已成功回退；现在会单独打印“导入审批回退结果缺失”中文日志与 `[处理建议]`，并继续让 `confirm` 走原来的 `IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT` fail-closed 边界，不改导入审批真相和副作用。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "restore_pending_approval_logs_persistence_failure or restore_pending_approval_logs_missing_result or restore_pending_approval_logs_rejected_current_state or confirm_import_by_task_ref_returns_state_unavailable_when_execution_cannot_restore_pending_approval or confirm_import_by_task_ref_returns_state_unavailable_when_execution_restore_pending_approval_result_is_missing"`；`tests/test_import_to_library.py -k "promotes_pending_to_approved"`

### 2026-04-17 下载确认任务回退结果缺失分流缺口

- 闭环：`add_to_downloader._restore_pending_job()` 在 `jobs.release_lease_to_pending()` 已经找不到任务行时，不再和普通 SQLite lease 回退异常共用同一条“下载确认任务回退失败”日志；现在会单独打印“下载确认任务回退结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的 confirm 错误恢复边界，不改审批真相和副作用。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py -k "restore_pending_job_logs_persistence_failure or restore_pending_job_logs_missing_result or restore_pending_job_logs_rejected_current_state"`
- commit：`02c864e` `Separate downloader restore-pending-job diagnostics`

### 2026-04-17 下载执行版号结果缺失分流缺口

- 闭环：`add_to_downloader._record_executed_lease_version()` 在 `approval_record.executed_version` 更新时，如果 `approval_record` 行已经不存在，不再和普通 SQLite 更新异常共用同一条“下载执行版号回写失败”日志；现在会单独打印“下载执行版号结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的 `ADD_FINALIZATION_WARNING_TEXT`，不改下载成功真相和 confirm 收尾边界。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py -k "record_executed_lease_version_logs_persistence_failure or record_executed_lease_version_logs_missing_result or confirm_add_by_task_ref_appends_warning_when_executed_version_write_fails"`
- commit：`7b64c4f` `Separate downloader executed-version diagnostics`

### 2026-04-17 下载取消任务结果缺失分流缺口

- 闭环：`add_to_downloader.cancel_pending_add()` 和 `_handle_expired_pending_confirm()` 在 `jobs.cancel_pending_job()` 返回 `None` 或抛出 `job missing during cancel` 时，不再和普通 SQLite 更新异常共用同一条“任务更新失败”日志；现在会单独打印“下载取消任务结果缺失”/“下载确认超时任务结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的状态读取失败文本，不改取消、超时 confirm 和审批边界。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py -k "cancel_pending_add_logs_job_cancel_failure or cancel_pending_add_logs_missing_job_cancel_result or handle_expired_pending_confirm_logs_job_cancel_failure or handle_expired_pending_confirm_logs_missing_job_during_cancel or handle_expired_pending_confirm_logs_job_cancel_state_rejection or cancel_pending_add_logs_job_cancel_state_rejection"`
- commit：`193508e` `Separate downloader cancel result diagnostics`

### 2026-04-17 导入取消任务结果缺失分流缺口

- 闭环：`import_to_library.cancel_pending_import()` 和 `_handle_expired_pending_confirm()` 在 `jobs.cancel_pending_job()` 返回 `None` 或抛出 `job missing during cancel` 时，不再和普通 SQLite 更新异常共用同一条“任务更新失败”日志；现在会单独打印“导入取消任务结果缺失”/“导入确认超时任务结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的状态读取失败文本，不改取消、超时 confirm 和审批边界。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "cancel_pending_import_logs_job_cancel_failure or cancel_pending_import_logs_missing_job_cancel_result or handle_expired_pending_confirm_logs_job_cancel_failure or handle_expired_pending_confirm_logs_missing_job_during_cancel or handle_expired_pending_confirm_logs_job_cancel_state_rejection or cancel_pending_import_logs_job_cancel_state_rejection"`
- commit：`c3ec7b0` `Separate import cancel result diagnostics`

### 2026-04-17 下载审批回退结果缺失分流缺口

- 闭环：`add_to_downloader._restore_pending_approval()` 在 `approval_repo.restore_downloader_pending()` 返回 `None` 时，不再把空结果混成普通“审批回退失败”日志；现在会单独打印“下载审批回退结果缺失”中文日志与 `[处理建议]`，并继续让 dispatch 失败后的 confirm 走原来的 `ADD_CONFIRM_STATE_UNAVAILABLE_TEXT` fail-closed 边界，不改待确认身份回退和审批真相边界。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py -k "restore_pending_approval_logs_persistence_failure or restore_pending_approval_logs_missing_result or restore_pending_approval_logs_rejected_current_state or confirm_add_by_task_ref_returns_state_unavailable_when_dispatch_failure_cannot_restore_pending_approval"`
- commit：`9604e0c` `Separate downloader restore-approval diagnostics`

### 2026-04-17 导入确认任务抢占状态冲突分流缺口

- 闭环：`import_to_library._claim_pending_job()` 在 `jobs.claim_lease()` 返回 `False` 时，不再静默交给后续 stale check 混成普通 `IMPORT_CONFIRM_NOT_PENDING_TEXT`；现在会先打印“导入确认任务抢占失败”中文日志与 `[处理建议]`，但用户侧仍保持原来的 stale check / not pending 边界，不改 confirm workflow 真相。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "claim_pending_job_logs_persistence_failure or claim_pending_job_logs_rejected_current_state or confirm_import_by_task_ref_returns_state_unavailable_when_claim_lease_fails or confirm_import_by_task_ref_returns_not_pending_when_claim_lease_is_rejected"`
- commit：`b8719ae` `Log rejected import lease claim`

### 2026-04-17 下载确认任务抢占状态冲突分流缺口

- 闭环：`add_to_downloader._claim_pending_job()` 在 `jobs.claim_lease()` 返回 `False` 时，不再静默交给后续 stale check 混成普通 `ADD_CONFIRM_NOT_PENDING_TEXT`；现在会先打印“下载确认任务抢占失败”中文日志与 `[处理建议]`，但用户侧仍保持原来的 stale check / not pending 边界，不改 confirm workflow 真相。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py -k "claim_pending_job_logs_persistence_failure or claim_pending_job_logs_rejected_current_state or confirm_add_by_task_ref_returns_state_unavailable_when_claim_lease_raises or confirm_add_by_task_ref_returns_not_pending_when_claim_lease_is_rejected"`
- commit：`987ff93` `Log rejected downloader lease claim`

### 2026-04-17 最小 trace 基线落地

- 闭环：shared private-chat runtime 的入站/回包，以及下载/导入待确认与 confirm 关键节点，都会通过 `app/trace_logging.py` 追加轻量文本轨迹到 `logs/trace.log`；这层 trace 只补可追溯串联，不替代现有中文故障日志，也不改变 workflow 真相和副作用边界。
- 代码：`app/trace_logging.py`、`app/bot/private_chat_runtime.py`、`app/services/add_to_downloader.py`、`app/services/import_to_library.py`
- 验证：`tests/test_trace_logging.py`、`tests/test_private_chat_runtime.py -k trace_log`、`tests/test_add_to_downloader.py -k trace_log`、`tests/test_import_to_library.py -k trace_log`
- commit：`4c8a19d` `Add minimal trace logging baseline`

### 2026-04-17 导入执行版号结果缺失分流缺口

- 闭环：`import_to_library._record_executed_lease_version()` 在 `approval_record.executed_version` 更新时，如果 `approval_record` 行已经不存在，不再和普通 SQLite 更新异常共用同一条“导入执行版号回写失败”日志；现在会单独打印“导入执行版号结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的 `IMPORT_FINALIZATION_WARNING_TEXT`，不改导入成功真相和 confirm 收尾边界。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "record_executed_lease_version_logs_persistence_failure or record_executed_lease_version_logs_missing_result"`
- commit：`bd47df2` `Separate import executed-version diagnostics`

### 2026-04-17 导入待确认审批结果缺失分流缺口

- 闭环：`import_to_library._record_pending_approval()` 在 `approval_record` 已写入、但写入后立即回读不到当前待确认导入审批的 `lease_version` 时，不再和普通 SQLite 写入异常共用同一条“导入待确认审批落盘失败”日志；现在会单独打印“导入待确认审批结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的 `IMPORT_PENDING_STATE_UNAVAILABLE_TEXT`，不改导入审批 fail-closed 边界。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "record_pending_approval_logs_persistence_failure or record_pending_approval_logs_missing_pending_result"`
- commit：`397a1f7` `Separate import approval diagnostics`；follow-up：`080fd81` `Fix import approval result reason`

### 2026-04-17 下载待确认审批结果缺失分流缺口

- 闭环：`add_to_downloader._record_pending_approval()` 在 `approval_record` 已写入、但写入后立即回读不到当前待确认审批的 `lease_version` 时，不再和普通 SQLite 写入异常共用同一条“下载待确认审批落盘失败”日志；现在会单独打印“下载待确认审批结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的 `ADD_PENDING_STATE_UNAVAILABLE_TEXT`，不改下载审批 fail-closed 边界。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py -k "record_pending_approval_logs_persistence_failure or record_pending_approval_logs_missing_pending_result"`
- commit：`dd2db74` `Separate downloader approval diagnostics`

### 2026-04-17 下载监控登记结果缺失分流缺口

- 闭环：`add_to_downloader._register_download_monitor()` 在 `download_monitor` 已写入、但写入后立即回读不到刚登记的状态记录时，不再和普通 SQLite 写入异常共用同一条“下载监控登记失败”日志；现在会单独打印“下载监控登记结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的继续执行边界，不改下载已投递成功后的副作用真相。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py -k "register_download_monitor_logs_persistence_failure or register_download_monitor_logs_missing_registered_result"`
- commit：`8b02620` `Separate download monitor register diagnostics`

### 2026-04-17 导入待确认任务结果缺失分流缺口

- 闭环：`import_to_library._record_pending_job()` 在 `jobs` 导入待确认任务已写入、但写入后立即回读不到待确认任务时，不再和普通 SQLite 写入异常共用同一条“导入待确认任务落盘失败”日志；现在会单独打印“导入待确认任务结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的 `IMPORT_PENDING_STATE_UNAVAILABLE_TEXT`，不改导入审批 fail-closed 边界。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "record_pending_job_logs_persistence_failure or record_pending_job_logs_missing_pending_job_result"`
- commit：`a9ed216` `Separate import pending-job diagnostics`

### 2026-04-17 下载待确认任务结果缺失分流缺口

- 闭环：`add_to_downloader._record_pending_job()` 在 `jobs` 待确认任务已写入、但写入后立即回读不到待确认任务时，不再和普通 SQLite 写入异常共用同一条“下载待确认任务落盘失败”日志；现在会单独打印“下载待确认任务结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的 `ADD_PENDING_STATE_UNAVAILABLE_TEXT`，不改下载审批 fail-closed 边界。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py -k "record_pending_job_logs_persistence_failure or record_pending_job_logs_missing_pending_job_result"`
- commit：`93ded37` `Separate downloader pending-job diagnostics`

### 2026-04-17 cleanup 事件结果缺失分流缺口

- 闭环：`cleanup_downloaded_source._record_event()` 在 `job_event.append_event()` 已执行、但写入后立即回读不到 cleanup 事件时，不再和普通 SQLite 写入异常共用同一条“cleanup 事件写入失败”日志；现在会单独打印“cleanup 事件结果缺失”中文日志与 `[处理建议]`，但 cleanup 文本结果仍保持原来的继续返回边界，不改 guardrail 和副作用真相。
- 代码：`app/services/cleanup_downloaded_source.py`
- 验证：`tests/test_cleanup_downloaded_source.py -k "event_append_failure or missing_appended_event_result"`
- commit：`9e1bd14` `Separate cleanup event result diagnostics`

### 2026-04-17 导入事件结果缺失分流缺口

- 闭环：`import_to_library._record_event()` 在 `job_event.append_event()` 已执行、但写入后立即回读不到导入事件时，不再和普通 SQLite 写入异常共用同一条“导入事件落盘失败”日志；现在会单独打印“导入事件结果缺失”中文日志与 `[处理建议]`，但导入流程仍保持原来的继续执行边界，不改导入副作用。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "record_event_logs_persistence_failure or record_event_logs_missing_appended_event_result"`
- commit：`eef4768` `Separate import event result diagnostics`

### 2026-04-17 下载完成观察事件结果缺失分流缺口

- 闭环：`get_download_status._record_status_observation()` 在 `job_event.append_event()` 已执行、但写入后立即回读不到 `downloader.completed_observed` 事件时，不再和普通 SQLite 写入异常共用同一条“下载完成观察事件落盘失败”日志；现在会单独打印“下载完成观察事件结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的状态 warning，不改状态查询和自动导入 follow-up 边界。
- 代码：`app/services/get_download_status.py`
- 验证：`tests/test_get_download_status.py -k "completion_event_write_fails or completion_event_result_is_missing"`
- commit：`68a73cb` `Separate completion event result diagnostics`

### 2026-04-17 下载事件结果缺失分流缺口

- 闭环：`add_to_downloader._record_event()` 在 `job_event.append_event()` 已执行但写入后立即回读不到下载事件时，不再和普通 SQLite 写入异常共用同一条“下载事件落盘失败”日志；现在会单独打印“下载事件结果缺失”中文日志与 `[处理建议]`，但当前下载流程仍保持原来的继续执行边界，不抬成新的状态失败。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py -k "record_event_logs_persistence_failure or record_event_logs_missing_appended_event_result"`
- commit：`974506d` `Separate downloader event result diagnostics`

### 2026-04-17 导入目标路径缺失分流缺口

- 闭环：`import_to_library._find_latest_import_target_path()` 在已经读到 import 关联对象、但 `target_path` 与 `message` 都为空时，不再和普通“没有历史导入终态”混成静默空结果；现在会单独打印“导入目标路径缺失”中文日志与 `[处理建议]`，但 stale confirm 判定仍保持原来的 `IMPORT_CONFIRM_NOT_PENDING_TEXT` 边界，不改审批或导入副作用。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "find_latest_import_target_path_logs_missing_structured_target or find_version_stale_rejection_text_logs_missing_structured_target"`
- commit：`b684f18` `Separate import target-path diagnostics`

### 2026-04-17 cleanup 关联路径缺失分流缺口

- 闭环：`cleanup_downloaded_source._find_import_correlation()` 在 `import.succeeded` 事件已存在、但 `source_path` 或 `target_path` 为空时，不再和普通“未找到 import 关联”混成静默 `None`；现在会单独打印“cleanup 关联路径缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的关联缺失拒绝文案，不改 cleanup guardrail 和副作用边界。
- 代码：`app/services/cleanup_downloaded_source.py`
- 验证：`tests/test_cleanup_downloaded_source.py -k "missing_structured_source_path or missing_structured_target_path"`
- commit：`e430a8e` `Separate cleanup correlation path diagnostics`

### 2026-04-17 自动导入跳过事件结果缺失分流缺口

- 闭环：`post_download_auto_import._record_skip_event()` 在 `job_event.append_event()` 已执行但写入后立即回读不到事件时，不再和普通 SQLite 写入异常共用同一条“自动导入跳过事件落盘失败”日志；现在会单独打印“自动导入跳过事件结果缺失”中文日志与 `[处理建议]`，但 `run_for_record()` / `run_once()` / `status` follow-up 仍保持原来的状态不可用停路，不改自动导入副作用边界。
- 代码：`app/services/post_download_auto_import.py`
- 验证：`tests/test_get_download_status.py -k "skip_event_result_is_missing or skip_event_write_fails"`
- commit：`e30e1ed` `Separate auto-import skip event result diagnostics`

### 2026-04-17 搜索候选写入结果缺失分流缺口

- 闭环：`search_media.search_and_format()` 在 `candidate_mapping` 保存后的计数查询直接返回 `None` 时，不再和普通 SQLite 写入异常或“条数不一致”共用同一条日志；现在会单独打印“搜索候选写入结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持 `CANDIDATE_STATE_UNAVAILABLE_TEXT`，不改候选回滚和 fail-closed 协议。
- 代码：`app/services/search_media.py`
- 验证：`tests/test_search_media.py -k "search_candidate_persist_logs_missing_count_result or search_candidate_persist_logs_count_mismatch_after_save"`
- commit：`7ae80a6` `Separate candidate count-result diagnostics`

### 2026-04-17 BT 订阅最近资源回写结果缺失分流缺口

- 闭环：`manage_bt_subscription._update_last_seen()` 在 `bt_subscription_item` 最近资源回写返回 `False` 或 `None` 时，不再和普通 SQLite/更新异常共用同一条“BT 订阅最近资源回写失败”日志；现在会把“回写结果缺失”和普通回写失败拆开成更明确的中文日志与 `[处理建议]`，但用户侧仍保持原来的 warning：已创建的下载待确认保留，最近资源真相未更新提示不变，不改 `btsub run` 的副作用边界。
- 代码：`app/services/manage_bt_subscription.py`
- 验证：`tests/test_manage_bt_subscription.py -k "last_seen_truth_is_not_updated or last_seen_truth_update_returns_none or missing_row_during_last_seen_update"`
- commit：`9e087dd` `Separate btsub last_seen result diagnostics`

### 2026-04-17 想看写入结果缺失分流缺口

- 闭环：`manage_watchlist._add_item()` 在 `watchlist_repo.add_item()` 返回 `None` 时，不再和普通 SQLite 写入异常共用同一条“想看写入失败”日志；现在会把“写入结果缺失”和普通写入失败拆开成更明确的中文日志与 `[处理建议]`，但用户侧仍保持原来的失败文本，不改 watchlist workflow。
- 代码：`app/services/manage_watchlist.py`
- 验证：`tests/test_manage_watchlist.py -k "add_returns_failure_text_when_repo_returns_none or add_logs_missing_row_after_insert or add_returns_failure_text_when_repo_raises"`
- commit：`26c3de1` `Separate watchlist add result diagnostics`

### 2026-04-17 搜索澄清态清理结果缺失分流缺口

- 闭环：`search_media._clear_clarification_pending()` 在 `clarification_repo.clear_pending()` 返回 `None` 时，不再和普通 SQLite 删除异常共用同一条“搜索澄清态清理失败”日志；现在会把“清理结果缺失”和普通清理失败拆开成更明确的中文日志与 `[处理建议]`，但 fail-closed 行为保持不变：当前进程会恢复内存里的待澄清状态，不把缺失真相误判成已清理成功。
- 代码：`app/services/search_media.py`
- 验证：`tests/test_search_media.py -k "clear_clarification_pending_logs_missing_clear_result or clear_clarification_pending_logs_persistence_failure"`
- commit：`7936701` `Separate clarification clear result diagnostics`

### 2026-04-17 搜索候选清理结果缺失分流缺口

- 闭环：`search_media.clear_cached_candidates()` 在 `candidate_repo.clear_candidates()` 返回 `None` 时，不再和普通 SQLite 删除异常共用同一条“搜索候选清理失败”日志；现在会把“清理结果缺失”和普通清理失败拆开成更明确的中文日志与 `[处理建议]`，但 fail-closed 行为保持不变：当前进程会恢复内存里的候选缓存，不把缺失真相误判成已清理成功。
- 代码：`app/services/search_media.py`
- 验证：`tests/test_search_media.py -k "clear_cached_candidates_logs_missing_candidate_clear_result or clear_cached_candidates_logs_candidate_persistence_failure"`
- commit：`0f25f60` `Separate candidate clear result diagnostics`

### 2026-04-17 搜索候选回滚清理结果缺失分流缺口

- 闭环：`search_media.search_and_format()` 在候选写入失败后的回滚删除返回 `None` 时，不再和普通 SQLite 删除异常共用同一条“搜索候选清理失败”日志；现在会把“回滚清理结果缺失”和普通回滚清理失败拆开成更明确的中文日志与 `[处理建议]`，但 fail-closed 行为保持不变：当前请求仍直接返回候选状态写入失败，不继续暴露坏候选缓存。
- 代码：`app/services/search_media.py`
- 验证：`tests/test_search_media.py -k "candidate_persist_rollback_logs_missing_clear_result or search_candidate_persist_logs_persistence_failure"`
- commit：`bc5625d` `Separate candidate rollback clear result diagnostics`

### 2026-04-17 下载状态观察缺字段分流缺口

- 闭环：`get_download_status._record_status_observation()` 在 `download_monitor_repo.record_status()` 返回的 update 缺 `record`、或缺 `newly_completed` 标记时，不再都只打印同一类“下载状态观察落盘失败”日志；现在会把“观察结果缺失”“完成标记缺失”和普通 SQLite/调用异常拆开成更明确的中文日志与 `[处理建议]`，但用户侧仍保持原来的 `STATUS_OBSERVATION_WARNING_TEXT`，不改状态查询和自动导入 follow-up 的 fail-closed 边界。
- 代码：`app/services/get_download_status.py`
- 验证：`tests/test_get_download_status.py -k "download_monitor_returns_missing_update or download_monitor_returns_missing_record or download_monitor_returns_missing_completion_flag"`
- commit：`61d36de` `Separate download monitor observation diagnostics`

### 2026-04-17 下载状态观察空结果分流缺口

- 闭环：`get_download_status._record_status_observation()` 在 `download_monitor_repo.record_status()` 直接返回空 update 时，不再和普通 SQLite/调用异常共用同一条“下载状态观察落盘失败”日志；现在也会落到“下载状态观察结果缺失”中文日志与 `[处理建议]`，但用户侧仍保持原来的 `STATUS_OBSERVATION_WARNING_TEXT`，不改状态查询和自动导入 follow-up 的 fail-closed 边界。
- 代码：`app/services/get_download_status.py`
- 验证：`tests/test_get_download_status.py -k "download_monitor_returns_missing_update or download_monitor_returns_missing_record or download_monitor_returns_missing_completion_flag"`
- commit：`eaca4d8` `Separate download monitor empty-result diagnostics`

### 2026-04-17 导入命名真相结果缺失分流缺口

- 闭环：`import_to_library._resolve_normalized_naming_truth()` 在 `job_event` 查询返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“导入命名真相查询失败”日志；现在会把“查询结果缺失”和普通查询失败拆开成更明确的中文日志与 `[处理建议]`，但导入链仍保持原来的 fallback：退回下载源名称做命名，不改导入副作用边界。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py -k "resolve_normalized_naming_truth_logs_missing_result or resolve_normalized_naming_truth_logs_query_failure"`
- commit：`65fb8b2` `Separate import naming truth diagnostics`

### 2026-04-17 自动导入终态结果缺失分流缺口

- 闭环：`post_download_auto_import._has_terminal_activity()` 在 `job_event` 查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“自动导入终态查询失败”日志；现在会把“终态结果缺失”和普通查询失败拆开成更明确的中文日志与 `[处理建议]`，但自动导入仍保持原来的 fail-closed：当前条目直接停路，不把读取缺口误判成“没有终态事件”。
- 代码：`app/services/post_download_auto_import.py`
- 验证：`tests/test_get_download_status.py -k "terminal_lookup_fails or terminal_lookup_returns_none"`
- commit：`c666327` `Separate auto import terminal diagnostics`

### 2026-04-17 BT 订阅扫描结果缺失分流缺口

- 闭环：`manage_bt_subscription._scan_chat_once()` 在 `bt_subscription_item` 列表查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“BT 订阅扫描读取失败”日志；现在会把“扫描结果缺失”和普通查询失败拆开成更明确的中文日志与 `[处理建议]`，但 `run_once()` / scheduler tick 仍保持原来的 fail-closed：本轮扫描直接按失败停路，不把缺失真相误判成“没有可扫描条目”。
- 代码：`app/services/manage_bt_subscription.py`
- 验证：`tests/test_manage_bt_subscription.py -k "scan_items_return_none or scheduler_tick_returns_none_when_scan_items_return_none"`
- commit：`2f28a2c` `Separate btsub scan result diagnostics`

### 2026-04-17 BT 订阅 chat 列表结果缺失分流缺口

- 闭环：`manage_bt_subscription.run_scheduler_tick()` 在 `bt_subscription_item` chat 列表查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“BT 订阅扫描 chat 列表读取失败”日志；现在会把“chat 列表结果缺失”和普通查询失败拆开成更明确的中文日志与 `[处理建议]`，但 scheduler tick 仍保持原来的 fail-closed：本轮直接停路，不把缺失真相误判成“当前没有订阅 chat”。
- 代码：`app/services/manage_bt_subscription.py`
- 验证：`tests/test_manage_bt_subscription.py -k "chat_id_lookup_fails or chat_id_lookup_returns_none"`
- commit：`2a843cf` `Separate btsub chat list diagnostics`

### 2026-04-17 想看清单结果缺失分流缺口

- 闭环：`manage_watchlist._list_items()` 在 `watchlist_item` 列表查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“想看清单读取失败”日志；现在会把“清单结果缺失”和普通查询失败拆开成更明确的中文日志与 `[处理建议]`，但用户侧仍保持原来的 `WATCHLIST_LIST_FAILED_TEXT`，不改 watchlist workflow。
- 代码：`app/services/manage_watchlist.py`
- 验证：`tests/test_manage_watchlist.py -k "list_returns_failure_text_when_repo_raises or list_returns_failure_text_when_repo_returns_none"`
- commit：`703dc31` `Separate watchlist list diagnostics`

### 2026-04-17 想看删除结果缺失分流缺口

- 闭环：`manage_watchlist._remove_item()` 在 `watchlist_item` 删除查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“想看删除失败”日志；现在会把“删除结果缺失”和普通查询失败拆开成更明确的中文日志与 `[处理建议]`，但用户侧仍保持原来的 `WATCHLIST_REMOVE_FAILED_TEXT`，不改 watchlist workflow。
- 代码：`app/services/manage_watchlist.py`
- 验证：`tests/test_manage_watchlist.py -k "remove_returns_failure_text_when_repo_raises or remove_returns_failure_text_when_repo_returns_none"`
- commit：`863234d` `Separate watchlist remove diagnostics`

### 2026-04-17 想看清空结果缺失分流缺口

- 闭环：`manage_watchlist._clear_items()` 在 `watchlist_item` 清空查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“想看清单清空失败”日志；现在会把“清空结果缺失”和普通查询失败拆开成更明确的中文日志与 `[处理建议]`，但用户侧仍保持原来的 `WATCHLIST_CLEAR_FAILED_TEXT`，不改 watchlist workflow。
- 代码：`app/services/manage_watchlist.py`
- 验证：`tests/test_manage_watchlist.py -k "clear_returns_failure_text_when_repo_raises or clear_returns_failure_text_when_repo_returns_none"`
- commit：`68bb5f4` `Separate watchlist clear diagnostics`

### 2026-04-17 BT 订阅清单结果缺失分流缺口

- 闭环：`manage_bt_subscription._list_items()` 在 `bt_subscription_item` 列表查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“BT 订阅清单读取失败”日志；现在会把“清单结果缺失”和普通查询失败拆开成更明确的中文日志与 `[处理建议]`，但用户侧仍保持原来的 `BT_SUBSCRIPTION_LIST_FAILED_TEXT`，不改订阅清单 workflow。
- 代码：`app/services/manage_bt_subscription.py`
- 验证：`tests/test_manage_bt_subscription.py -k "list_returns_failure_text_when_repo_raises or list_returns_failure_text_when_repo_returns_none"`
- commit：`15ddf2f` `Separate btsub list diagnostics`

### 2026-04-17 BT 订阅删除结果缺失分流缺口

- 闭环：`manage_bt_subscription._remove_item()` 在 `bt_subscription_item` 删除查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“BT 订阅删除失败”日志；现在会把“删除结果缺失”和普通查询失败拆开成更明确的中文日志与 `[处理建议]`，但用户侧仍保持原来的 `BT_SUBSCRIPTION_REMOVE_FAILED_TEXT`，不改订阅删除 workflow。
- 代码：`app/services/manage_bt_subscription.py`
- 验证：`tests/test_manage_bt_subscription.py -k "remove_returns_failure_text_when_repo_raises or remove_returns_failure_text_when_repo_returns_none"`
- commit：`6c9ee51` `Separate btsub remove diagnostics`

### 2026-04-17 BT 订阅清空结果缺失分流缺口

- 闭环：`manage_bt_subscription._clear_items()` 在 `bt_subscription_item` 清空查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“BT 订阅清单清空失败”日志；现在会把“清空结果缺失”和普通查询失败拆开成更明确的中文日志与 `[处理建议]`，但用户侧仍保持原来的 `BT_SUBSCRIPTION_CLEAR_FAILED_TEXT`，不改订阅清空 workflow。
- 代码：`app/services/manage_bt_subscription.py`
- 验证：`tests/test_manage_bt_subscription.py -k "clear_returns_failure_text_when_repo_raises or clear_returns_failure_text_when_repo_returns_none"`
- commit：`08c9086` `Separate btsub clear diagnostics`

### 2026-04-17 自动导入候选结果缺失分流缺口

- 闭环：`post_download_auto_import.run_once()` 在 `download_monitor` 已完成列表查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“自动导入候选读取失败”日志；现在会把“候选结果缺失”和普通读取失败拆开成更明确的中文日志与 `[处理建议]`，但本轮自动导入仍保持原来的 fail-closed：直接停路，不把缺失真相误判成“当前没有可导入候选”。
- 代码：`app/services/post_download_auto_import.py`
- 验证：`tests/test_get_download_status.py -k "run_once_logs_completed_list_failure or run_once_logs_completed_list_missing_result"`
- commit：`d42bdf3` `Separate auto-import completed list diagnostics`

### 2026-04-17 BT 订阅写入结果缺失分流缺口

- 闭环：`manage_bt_subscription._add_item()` 在 `bt_subscription_item` 插入查询直接返回 `None` 时，不再和普通 SQLite 查询异常共用同一条“BT 订阅写入失败”日志；现在会把“写入结果缺失”和普通写入失败拆开成更明确的中文日志与 `[处理建议]`，但用户侧仍保持原来的 `BT_SUBSCRIPTION_ADD_FAILED_TEXT`，不改订阅新增 workflow。
- 代码：`app/services/manage_bt_subscription.py`
- 验证：`tests/test_manage_bt_subscription.py -k "add_returns_failure_text_when_repo_raises or add_returns_failure_text_when_repo_returns_none"`
- commit：`7d9355c` `Separate btsub add result diagnostics`

### 2026-04-17 搜索候选写入后真相不一致缺口

- 闭环：`search_media` 在 `candidate_mapping` 保存候选后，如果持久化表里的条数和预期不一致，不再和普通 SQLite 写入失败共用同一条日志；现在会打印“搜索候选写入后记录不一致”中文日志和单独的 `[处理建议]`，但用户侧仍保持 `CANDIDATE_STATE_UNAVAILABLE_TEXT`，不改候选回滚和 fail-closed 协议。
- 代码：`app/services/search_media.py`
- 验证：`tests/test_search_media.py -k "candidate_persist_logs_persistence_failure or no_result_returns_state_unavailable_when_candidate_persist_fails"`
- commit：`d7f8da7` `Separate candidate count mismatch diagnostics`

### 2026-04-17 Telegram BT 待答写入后回读缺口

- 闭环：`telegram_bot` 的四个 BT pending setter（processing_path / classification / tmdb_association / raw_bt_destination）在 `bt_pending_state` upsert 成功后，如果立即回读不到记录，不再和普通 SQLite 写入失败共用同一条日志；现在会打印“BT 待处理写入后记录缺失”中文日志和单独的 `[处理建议]`，但用户侧仍保持原来的 `SERVICE_NOT_READY_TEXT`，不改 BT follow-up workflow。
- 代码：`app/bot/telegram_bot.py`
- 验证：`tests/test_telegram_bot.py -k "set_bt_processing_path_pending_logs_persistence_failure or set_bt_processing_path_pending_logs_missing_row_after_upsert or set_bt_classification_pending_logs_persistence_failure"`
- commit：`788290a` `Separate BT pending missing-row diagnostics`

### 2026-04-17 搜索待澄清写入后回读缺口

- 闭环：`search_media._set_clarification_pending()` 在 `clarification_state` upsert 成功后，如果立即回读不到记录，不再和普通 SQLite 写入失败共用同一条日志；现在会打印“搜索澄清态写入后记录缺失”中文日志和单独的 `[处理建议]`，把“真缺数据 / 回读缺口”与一般持久化异常拆开，但用户侧仍保持 `CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT`，不改搜索 workflow。
- 代码：`app/services/search_media.py`
- 验证：`tests/test_search_media.py -k "clarification_pending_logs_persistence_failure or no_result_returns_state_unavailable_when_clarification_persist_fails"`
- commit：`7979d38` `Separate clarification missing-row diagnostics`

### 2026-04-17 BT 订阅写入后回读缺口

- 闭环：`manage_bt_subscription._add_item()` 在 `bt_subscription_item` 插入成功后，如果立即回读不到新条目，不再和普通 SQLite 写入失败共用同一条日志；现在会打印“BT 订阅写入后条目缺失”中文日志和单独的 `[处理建议]`，把“真缺数据 / 回读缺口”与一般持久化异常拆开，但用户侧仍保持原来的失败文本，不改订阅 workflow。
- 代码：`app/services/manage_bt_subscription.py`
- 验证：`tests/test_manage_bt_subscription.py -k "add_logs_missing_row_after_insert or add_returns_failure_text_when_repo_raises or add_returns_failure_text_when_repo_returns_none"`
- commit：`0db8d00` `Separate btsub missing-row diagnostics`

### 2026-04-17 想看清单写入后回读缺口

- 闭环：`manage_watchlist._add_item()` 在 `watchlist_item` 插入成功后，如果立即回读不到新条目，不再和普通 SQLite 写入失败共用同一条日志；现在会打印“想看写入后条目缺失”中文日志和单独的 `[处理建议]`，把“真缺数据 / 回读缺口”与一般持久化异常拆开，但用户侧仍保持原来的失败文本，不改 workflow。
- 代码：`app/services/manage_watchlist.py`
- 验证：`tests/test_manage_watchlist.py -k "missing_row_after_insert or add_returns_failure_text_when_repo_raises or add_returns_failure_text_when_repo_returns_none"`
- commit：`8f0f50f` `Separate watchlist missing-row diagnostics`

### 2026-04-17 BT 订阅最近资源回写缺口

- 闭环：`manage_bt_subscription._update_last_seen()` 现在会区分两类真相缺口：如果 `bt_subscription_item` 条目在回写前已不存在，会打印“条目缺失”中文日志，并把用户 warning 改成“本轮待确认已创建，但该订阅已不存在”；只有 SQLite 或其它持久化异常，才继续走“最近资源真相未更新”的状态不可用 warning，避免把真缺数据和写库异常混成一类。
- 代码：`app/services/manage_bt_subscription.py`
- 验证：`tests/test_manage_bt_subscription.py -k last_seen`
- commit：`58d3471` `Distinguish btsub last-seen missing row`

### 2026-04-17 自动导入规则跳过事件缺口

- 闭环：`post_download_auto_import._record_skip_event()` 在低质量资源命中自动跳过规则时，如果 `job_event` 写入失败，不再继续回“已跳过自动导入”，而是抛成状态不可用；`run_once()` 和 `status` follow-up 都会按 fail-closed 停路，避免把 `job_event` 真相缺口混成普通规则命中并在后续轮询里重复提示。
- 代码：`app/services/post_download_auto_import.py`
- 验证：`tests/test_get_download_status.py`
- commit：`04268f5` `Fail closed auto-import skip event persistence`

### 2026-04-17 下载审批回退缺口

- 闭环：`add_to_downloader.confirm_add_by_task_ref()` 在下载投递失败后，如果 `approval_record` 的 pending 回退也失败，不再继续回普通 `ADD_FAILED_TEXT`，而会直接返回下载确认状态读取失败；避免把审批真相未回退混成普通下载器报错。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py`
- commit：`8b6bbb3` `Fail closed downloader approval restore gap`

### 2026-04-17 导入审批回退缺口

- 闭环：`import_to_library.confirm_import_by_task_ref()` 在导入执行失败或进入 copy-fallback 待确认后，如果 `approval_record` 的 pending 回退失败，不再继续回普通导入失败或普通 copy-fallback 提示，而会直接返回导入确认状态读取失败；避免把审批真相未回退混成普通导入执行结果。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py`
- commit：`a163ace` `Fail closed import approval restore gap`

### 2026-04-17 下载成功收尾缺口

- 闭环：`add_to_downloader.confirm_add_by_task_ref()` 在下载器已经真实接单后，如果 `approval_record.executed_version` 或 `jobs` 完结态回写失败，不再继续回纯成功文本，而会在成功回复后追加显式 warning，提醒不要重复 `confirm`，避免把“已执行但真相未落稳”混成“全链已落盘”。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py`
- commit：`188677b` `Warn on downloader finalization persistence gap`

### 2026-04-17 导入成功收尾缺口

- 闭环：`import_to_library.confirm_import_by_task_ref()` 在导入已经成功后，如果 `approval_record.executed_version` 或 `jobs` 完结态回写失败，不再继续回纯成功文本，而会在成功回复后追加显式 warning，提醒不要重复 `confirm`，避免把“已导入但真相未落稳”混成“全链已落盘”。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py`
- commit：`06ab7c1` `Warn on import finalization persistence gap`

### 2026-04-17 Telegram BT 待答持久化缺口

- 闭环：`telegram_bot` 的 BT processing/classification/tmdb/raw-destination 四个 pending setter 在写 `bt_pending_state` 失败时，不再保留刚写入的 in-memory 状态，也不再继续发下一步 prompt；`private_chat_runtime` 的直接 BT 入口和 `telegram_bot` 的 BT flow helper 会统一回 `SERVICE_NOT_READY_TEXT`。
- 代码：`app/bot/telegram_bot.py`、`app/bot/private_chat_runtime.py`
- 验证：`tests/test_telegram_bot.py`、`tests/test_private_chat_runtime.py`
- commit：`c8e2fea` `Fail closed telegram BT pending persistence`

### 2026-04-17 Telegram BT processing_path 清理缺口

- 闭环：`telegram_bot._clear_bt_processing_path_pending()` 和 `_pop_bt_processing_path_pending()` 在清理 `bt_pending_state` 失败时，不再把旧 processing_path 当成“已取消”或“已弹出”；它们会把 in-memory 状态放回，并让 `private_chat_runtime` 回 `SERVICE_NOT_READY_TEXT`。
- 代码：`app/bot/telegram_bot.py`、`app/bot/private_chat_runtime.py`
- 验证：`tests/test_telegram_bot.py`、`tests/test_private_chat_runtime.py`
- commit：`a2f8d92` `Fail closed telegram BT processing cleanup gap`

### 2026-04-17 Telegram BT classification 清理缺口

- 闭环：`telegram_bot._clear_bt_classification_pending()` 和 `_pop_bt_classification_pending()` 在清理 `bt_pending_state` 失败时，不再把旧 classification 当成“已取消”或“已弹出”；它们会把 in-memory 状态放回，并让 `private_chat_runtime` 回 `SERVICE_NOT_READY_TEXT`。
- 代码：`app/bot/telegram_bot.py`、`app/bot/private_chat_runtime.py`
- 验证：`tests/test_telegram_bot.py`、`tests/test_private_chat_runtime.py`
- commit：`92a4df0` `Fail closed telegram BT classification cleanup gap`

### 2026-04-17 Telegram BT tmdb_association 清理缺口

- 闭环：`telegram_bot._clear_bt_tmdb_association_pending()` 在清理 `bt_pending_state` 失败时，不再把旧 TMDB 关联态当成“已取消”或让后续媒体入库链继续推进；它会把 in-memory 状态放回，并让 `private_chat_runtime` 回 `SERVICE_NOT_READY_TEXT`。
- 代码：`app/bot/telegram_bot.py`、`app/bot/private_chat_runtime.py`
- 验证：`tests/test_telegram_bot.py`、`tests/test_private_chat_runtime.py`
- commit：`dcd59f6` `Fail closed telegram BT tmdb cleanup gap`

### 2026-04-17 Telegram BT raw_bt_destination 清理缺口

- 闭环：`telegram_bot._clear_raw_bt_destination_pending()` 在清理 `bt_pending_state` 失败时，不再把旧 raw_bt 目标目录选择当成“已取消”或让后续媒体入库链继续推进；它会把 in-memory 状态放回，并让 `private_chat_runtime` 回 `SERVICE_NOT_READY_TEXT`。
- 代码：`app/bot/telegram_bot.py`、`app/bot/private_chat_runtime.py`
- 验证：`tests/test_telegram_bot.py`、`tests/test_private_chat_runtime.py`
- commit：`842e065` `Fail closed telegram BT raw destination cleanup gap`

### 2026-04-17 下载审批缺口

- 闭环：`add_to_downloader._resolve_pending_lease_version()` 在已配置 `approval_repo` 且当前进程仍留有 in-memory pending 身份时，如果 `approval_record` 行缺失，也会记成显式中文日志，并让 `cancel_pending_add()` 直接按状态读取失败停路。
- 代码：`app/services/add_to_downloader.py`
- 验证：`tests/test_add_to_downloader.py`
- commit：`e0eb760` `Fail closed missing downloader approval row`

### 2026-04-17 导入审批缺口

- 闭环：`import_to_library._resolve_pending_lease_version()` 在已配置 `approval_repo` 且当前进程仍留有 in-memory pending 身份时，如果 `approval_record` 行缺失，也会记成显式中文日志，并让 `cancel_pending_import()` 直接按状态读取失败停路。
- 代码：`app/services/import_to_library.py`
- 验证：`tests/test_import_to_library.py`
- commit：`47a28cc` `Fail closed missing import approval row`

### 2026-04-17 搜索待澄清写入缺口

- 闭环：`search_media._set_clarification_pending()` 在 `clarification_repo.upsert_pending()` 写入失败时，直接清掉本次 in-memory pending，并回“搜索待澄清状态写入失败，请稍后重试。”
- 代码：`app/services/search_media.py`
- 验证：`tests/test_search_media.py`、`tests/test_private_chat_runtime.py -k clarification`
- commit：`11be57a` `Fail closed search clarification persistence`

### 2026-04-17 搜索候选写入缺口

- 闭环：`search_media` 在 `candidate_repo.save_candidates()` 写入失败时，直接清掉本次 in-memory candidate，并做 best-effort 持久化回滚；当前请求回“搜索候选状态写入失败，请稍后重试。”
- 代码：`app/services/search_media.py`
- 验证：`tests/test_search_media.py`
- commit：`adb610e` `Fail closed search candidate persistence`

### 2026-04-17 搜索旧澄清态清理缺口

- 闭环：成功搜索命中候选、但 `clarification_repo.clear_pending()` 清理旧澄清态失败时，直接清掉本次 in-memory candidate，并回“搜索待澄清状态清理失败，请稍后重试。”
- 代码：`app/services/search_media.py`
- 验证：`tests/test_search_media.py`
- commit：`3fdf5c8` `Fail closed search clarification clear`

## 3. Focused verification

- telegram raw-bt-destination cleanup fail-closed tests：2026-04-17，`3 passed, 182 deselected`（`.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "clear_raw_bt_destination_pending_logs_persistence_failure or raw_bt_destination_clear_fails_on_cancel or raw_bt_destination_clear_fails_before_media_import_flow"`）
- telegram bt-tmdb cleanup fail-closed tests：2026-04-17，`3 passed, 180 deselected`（`.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "clear_bt_tmdb_association_pending_logs_persistence_failure or bt_tmdb_clear_fails_on_cancel or bt_tmdb_clear_fails_before_media_import_flow"`）
- telegram bt-classification cleanup fail-closed tests：2026-04-17，`4 passed, 177 deselected`（`.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "clear_bt_classification_pending_logs_persistence_failure or pop_bt_classification_pending_logs_persistence_failure or bt_classification_clear_fails_on_cancel or bt_classification_pop_clear_fails"`）
- telegram bt-processing-path cleanup fail-closed tests：2026-04-17，`4 passed, 175 deselected`（`.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "clear_bt_processing_path_pending_logs_persistence_failure or pop_bt_processing_path_pending_logs_persistence_failure or bt_processing_path_clear_fails_on_cancel or bt_processing_path_pop_clear_fails"`）
- telegram bt-pending fail-closed tests：2026-04-17，`8 passed, 169 deselected`（`.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "bt_processing_path_persist_fails or set_bt_processing_path_pending_logs_persistence_failure or set_bt_classification_pending_logs_persistence_failure or set_bt_tmdb_association_pending_logs_persistence_failure or set_raw_bt_destination_pending_logs_persistence_failure or enter_media_import_bt_flow_returns_service_not_ready or enter_pure_bt_flow_returns_service_not_ready"`）
- import finalization warning tests：2026-04-17，`5 passed, 87 deselected`（`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "executed_version_write_fails or job_completion_write_fails or record_executed_lease_version_logs_persistence_failure or mark_completed_job_logs"`）
- downloader finalization warning tests：2026-04-17，`5 passed, 60 deselected`（`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "executed_version_write_fails or job_completion_write_fails or record_executed_lease_version_logs_persistence_failure or mark_completed_job_logs"`）
- downloader executed-version diagnostics tests：2026-04-17，`3 passed, 74 deselected`（`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "record_executed_lease_version_logs_persistence_failure or record_executed_lease_version_logs_missing_result or confirm_add_by_task_ref_appends_warning_when_executed_version_write_fails"`）
- downloader restore-pending-job diagnostics tests：2026-04-17，`3 passed, 75 deselected`（`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "restore_pending_job_logs_persistence_failure or restore_pending_job_logs_missing_result or restore_pending_job_logs_rejected_current_state"`）
- import approval-restore fail-closed tests：2026-04-17，`4 passed, 86 deselected`（`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "restore_pending_approval_logs or execution_cannot_restore_pending_approval"`）
- downloader approval-restore fail-closed tests：2026-04-17，`5 passed, 58 deselected`（`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "restore_pending_approval_logs or dispatch_failure_cannot_restore_pending_approval or confirm_add_by_task_ref_returns_failed_when_downloader_errors"`）
- auto-import skip-event fail-closed tests：2026-04-17，`4 passed, 25 deselected`（`.venv/bin/python -m pytest -q tests/test_get_download_status.py -k "get_status_text_returns_state_unavailable_when_skip_event_write_fails or post_download_auto_import_run_once_marks_state_unavailable_when_skip_event_write_fails or post_download_auto_import_run_for_record_raises_when_skip_event_write_fails"`）
- auto-import completed-list diagnostics tests：2026-04-17，`2 passed, 27 deselected`（`.venv/bin/python -m pytest -q tests/test_get_download_status.py -k "run_once_logs_completed_list_failure or run_once_logs_completed_list_missing_result"`）
- btsub add result diagnostics tests：2026-04-17，`2 passed, 25 deselected`（`.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "add_returns_failure_text_when_repo_raises or add_returns_failure_text_when_repo_returns_none"`）
- btsub remove result diagnostics tests：2026-04-17，`2 passed, 25 deselected`（`.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "remove_returns_failure_text_when_repo_raises or remove_returns_failure_text_when_repo_returns_none"`）
- btsub clear result diagnostics tests：2026-04-17，`2 passed, 25 deselected`（`.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "clear_returns_failure_text_when_repo_raises or clear_returns_failure_text_when_repo_returns_none"`）

- add to downloader missing-approval-row fail-closed tests：2026-04-17，`3 passed, 58 deselected`（`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "resolve_pending_lease_version_logs_missing_approval_row_with_in_memory_pending or cancel_pending_add_returns_state_unavailable_when_pending_approval_row_missing_with_in_memory_pending or pending_lease_lookup_fails_after_stale_check"`）
- import missing-approval-row fail-closed tests：2026-04-17，`4 passed, 84 deselected`（`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "resolve_pending_lease_version_logs_missing_approval_row_with_in_memory_pending or cancel_pending_import_returns_state_unavailable_when_pending_approval_row_missing_with_in_memory_pending or pending_lease_lookup_fails"`）
- search clarification pending persist fail-closed tests：2026-04-17，`4 passed, 30 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification_pending_logs_persistence_failure or no_result_returns_state_unavailable_when_clarification_persist_fails"`）
- search candidate persist fail-closed tests：2026-04-17，`2 passed, 33 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py -k "candidate_persist_logs_persistence_failure or no_result_returns_state_unavailable_when_candidate_persist_fails"`）
- search clarification clear fail-closed tests：2026-04-17，`2 passed, 34 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py -k "search_success_clears_persisted_clarification_pending or search_success_returns_state_unavailable_when_clarification_clear_fails"`）

## 4. Maintenance rule

- 当前主线新增一个最小闭环后，先把详细变更、focused tests 和 commit 写进这份文档。
- `docs/STATUS.md` 只补一句当前结论或一条最新风险，不再堆同类 focused verification 长列表。
- cleanup 已完成窗口的真实私聊 smoke 证据、窗口日期和 gate 结果继续只维护在 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
