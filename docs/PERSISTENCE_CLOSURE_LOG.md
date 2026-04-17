# Persistence closure log (v2)

> 目的：承接当前“持久化吞错收口”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环、focused tests 和 commit 轨迹优先记在这里。

## 1. Current line

- 当前唯一主线：持久化吞错收口
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`
- shared private-chat runtime 最小抽离已完成；四渠道都先走同一个 shared wrapper

## 2. Recent closed loops

### 2026-04-17 自动导入规则跳过事件缺口

- 闭环：`post_download_auto_import._record_skip_event()` 在低质量资源命中自动跳过规则时，如果 `job_event` 写入失败，不再继续回“已跳过自动导入”，而是抛成状态不可用；`run_once()` 和 `status` follow-up 都会按 fail-closed 停路，避免把 `job_event` 真相缺口混成普通规则命中并在后续轮询里重复提示。
- 代码：`app/services/post_download_auto_import.py`
- 验证：`tests/test_get_download_status.py`
- commit：待补

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

- auto-import skip-event fail-closed tests：2026-04-17，`4 passed, 25 deselected`（`.venv/bin/python -m pytest -q tests/test_get_download_status.py -k "get_status_text_returns_state_unavailable_when_skip_event_write_fails or post_download_auto_import_run_once_marks_state_unavailable_when_skip_event_write_fails or post_download_auto_import_run_for_record_raises_when_skip_event_write_fails"`）

- add to downloader missing-approval-row fail-closed tests：2026-04-17，`3 passed, 58 deselected`（`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "resolve_pending_lease_version_logs_missing_approval_row_with_in_memory_pending or cancel_pending_add_returns_state_unavailable_when_pending_approval_row_missing_with_in_memory_pending or pending_lease_lookup_fails_after_stale_check"`）
- import missing-approval-row fail-closed tests：2026-04-17，`4 passed, 84 deselected`（`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "resolve_pending_lease_version_logs_missing_approval_row_with_in_memory_pending or cancel_pending_import_returns_state_unavailable_when_pending_approval_row_missing_with_in_memory_pending or pending_lease_lookup_fails"`）
- search clarification pending persist fail-closed tests：2026-04-17，`4 passed, 30 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification_pending_logs_persistence_failure or no_result_returns_state_unavailable_when_clarification_persist_fails"`）
- search candidate persist fail-closed tests：2026-04-17，`2 passed, 33 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py -k "candidate_persist_logs_persistence_failure or no_result_returns_state_unavailable_when_candidate_persist_fails"`）
- search clarification clear fail-closed tests：2026-04-17，`2 passed, 34 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py -k "search_success_clears_persisted_clarification_pending or search_success_returns_state_unavailable_when_clarification_clear_fails"`）

## 4. Maintenance rule

- 当前主线新增一个最小闭环后，先把详细变更、focused tests 和 commit 写进这份文档。
- `docs/STATUS.md` 只补一句当前结论或一条最新风险，不再堆同类 focused verification 长列表。
- cleanup 已完成窗口的真实私聊 smoke 证据、窗口日期和 gate 结果继续只维护在 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
