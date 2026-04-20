# Persistence closure log (v47)

> 目的：承接已完成的“持久化吞错收口”主线详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环按主题合并进下面分组，**不再逐天或逐字段追加 `### 2026-04-xx 分流缺口` 条目**。具体 commit 轨迹看 `git log`；原始逐条台账已在 v43 做最后一次保留，此后收敛为主题视图。

## 1. Current line

- 上一条主线：持久化吞错收口（已在 2026-04-18 冷启动审计中满足 `Done when` 第 3 条：`git grep 'except Exception:\s*\(pass\|return None\)' app/services app/db app/bot` 命中 `0`）
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`
- shared private-chat runtime 最小抽离已完成；四渠道都先走同一个 shared wrapper

## 2. Recent closed loops

以下按业务主题分组。每个分组列出：覆盖路径 / 三类分流含义 / 可复用的 focused tests 入口。新增一个最小闭环后，优先补进已有分组，而不是新增 dated 小节。

**三类分流约定**：
- **结果缺失**：repo 层直接回 `None` / `0` / `False`，但真相本应存在 → 单独中文日志 + fail-closed。
- **记录损坏**：repo 能查到行、但关键字段被写空 / 写脏 → 单独中文日志 + 保持原停路边界。
- **SQLite 异常**：`except Exception` 路径原有中文日志保留；只是从以上两类里拆开。

### 2.1 下载 / 导入 confirm 主链（`approval_record` + `jobs`）

覆盖路径：`add_to_downloader._record_pending_approval / _record_pending_job / _claim_pending_job / _is_pending_approval_expired / _find_version_stale_rejection_text / _record_executed_lease_version / _record_downloader_approval / _cancel_pending_approval / _restore_pending_approval / _restore_pending_job / _mark_completed_job / _rebuild_confirm_context / has_pending_add / cancel_pending_add / _handle_expired_pending_confirm`；`import_to_library` 同名对偶方法；`approval_repo._approve / _cancel / _restore_pending` 的 row-missing 子分流。

全链已经补齐三类分流，行为边界：
- 待确认创建 / 过期判断 / 任务抢占 / 审批回退 / 取消 / 成功收尾 / 执行版号回写：结果缺失 + 记录损坏 + SQLite 异常各走独立中文日志 + `[处理建议]`。
- confirm 上下文重建、`raw_bt` 判定、历史目标路径查询、命名真相读取也已补齐记录损坏分流；confirm 统一按状态读取失败 fail-closed。
- 用户侧 `ADD_CONFIRM_STATE_UNAVAILABLE_TEXT` / `IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT` / `ADD_FINALIZATION_WARNING_TEXT` / `IMPORT_FINALIZATION_WARNING_TEXT` / `ADD_PENDING_STATE_UNAVAILABLE_TEXT` / `IMPORT_PENDING_STATE_UNAVAILABLE_TEXT` 边界不变。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "record_pending_approval or record_pending_job or claim_pending_job or is_pending_approval_expired or find_version_stale_rejection_text or record_executed_lease_version or record_downloader_approval or cancel_pending_approval or restore_pending_approval or restore_pending_job or mark_completed_job or rebuild_confirm_context or has_pending_add or cancel_pending_add or handle_expired_pending_confirm or is_raw_bt_task"`
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "record_pending_approval or record_pending_job or claim_pending_job or is_pending_approval_expired or find_version_stale_rejection_text or record_executed_lease_version or record_import_approval or cancel_pending_import or restore_pending_approval or restore_pending_job or mark_completed_job or rebuild_confirm_context or is_raw_bt_task or find_latest_import_target_path or resolve_normalized_naming_truth"`
- `.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py -k "approval_repo_approve_raises_when_row_missing or approval_repo_cancel_raises_when_row_missing or approval_repo_restore_pending_raises_when_row_missing"`

### 2.2 事件落盘（`job_event.append_event()`）

覆盖路径：`add_to_downloader._record_event` / `import_to_library._record_event` / `cleanup_downloaded_source._record_event` / `get_download_status._record_status_observation`（完成观察事件）/ `post_download_auto_import._record_skip_event`。

- “空结果”与“写后回读命中坏行”两路独立中文日志。
- 用户侧仍保持原边界：下载 / 导入流程继续执行，cleanup 文本结果继续返回，状态 warning 不变。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "record_event"`
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "record_event"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "event_append_failure or missing_appended_event_result or row_corrupted_appended_event or correlation"`
- `.venv/bin/python -m pytest -q tests/test_get_download_status.py -k "completion_event or skip_event"`

### 2.3 下载监控 / 状态观察 / 自动导入 / 后台轮询

覆盖路径：`add_to_downloader._register_download_monitor`、`get_download_status._record_status_observation`（状态 upsert / 缺字段）、`post_download_auto_import.run_once / _has_terminal_activity / _record_skip_event`、`telegram_bot._poll_pending_download_completion_once`、`telegram_bot._record_message_update / _record_callback_update`。

- `download_monitor.register_download()` / `record_status()` 的写入写后回读 + 记录损坏分流。
- 自动导入已完成列表、终态列表、跳过事件的空结果 + 记录损坏分流。
- 后台下载完成轮询待轮询列表的空结果 + 记录损坏分流，本轮 tick 直接停路。
- Telegram update / callback 去重写入的结果缺失分流，对应入口停路。
- 所有分流不改已投递下载副作用边界。
- 2026-04-20 worthiness 评估结论：这组共享职责值得单开结构降本主线。当前稳定调用方已经固定为 `StatusFollowUpRecorder.record()`、`PostDownloadAutoImportService.run_for_record()`、`telegram_bot._poll_pending_download_completion_once()`；三处都围绕同一份 `download_monitor` / `job_event` 真相推进“状态观察落盘 -> 完成事件查询/追加 -> 自动导入消费”，并共用 `AutoImportStateUnavailableError`、显式中文日志、fail-closed 停路边界。下一条 promoted 主线应优先抽这条 follow-up 推进链，而不是继续让渠道层通过 `get_status_text()` 间接触发共享副作用。
- 2026-04-20 冷启动审计结论：`GetDownloadStatusService.get_status_text()` 已只保留状态查询和回复组装，实际共享 follow-up 已委托给 `StatusFollowUpRecorder.record()`；因此上一条“共享状态 follow-up helper 结构降本”主线已满足 `docs/NEXT_STEP.md` 的退出条件 1/2/3。下一条同职责族最小收口点改成让 `telegram_bot._poll_pending_download_completion_once()` 直接复用共享 helper，不再借 `get_status_text()` 间接推进共享副作用。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "register_download_monitor"`
- `.venv/bin/python -m pytest -q tests/test_get_download_status.py -k "download_monitor or completion_event or auto_import_terminal or completed_list or skip_event"`
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "pending_list or dedup_result_missing or dedup_persist_fails or update_id_invalid or callback_id_missing"`

### 2.4 轻状态路径（search / watchlist / BT 订阅 / Telegram BT 待答）

覆盖路径：`search_media._set_clarification_pending / _load_persisted_clarification_query / _clear_clarification_pending / clear_cached_candidates / search_and_format`；`manage_watchlist._add_item / _list_items / _remove_item / _clear_items`；`manage_bt_subscription._add_item / _list_items / _remove_item / _clear_items / _update_last_seen / _scan_chat_once / run_scheduler_tick`；`telegram_bot` 的四个 BT pending setter 与对应 `_clear_` / `_pop_` helper、以及 TMDB 关联和 raw_bt 目录选择入口。

- 写入 - 回读、清单读取、删除、清空、最近资源回写、扫描读取：所有路径都已把“结果缺失 / 写后回读缺失 / 命中坏行 / SQLite 异常”拆开。
- 搜索 `CANDIDATE_STATE_UNAVAILABLE_TEXT` / `CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT`、watchlist 与 BT 订阅各 `*_FAILED_TEXT`、Telegram `SERVICE_NOT_READY_TEXT` 边界不变。
- Telegram BT 四态（processing_path / classification / tmdb_association / raw_bt_destination）的 `_clear_*` 返回 `None` 时，内存态会放回，runtime 统一回 `SERVICE_NOT_READY_TEXT`。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification or candidate"`
- `.venv/bin/python -m pytest -q tests/test_manage_watchlist.py`
- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py`
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "bt_processing_path or bt_classification or bt_tmdb_association or raw_bt_destination or bt_pending_repo_rejects_empty_stage_after_read"`

### 2.5 最小 trace 基线

`app/trace_logging.py` 把 shared private-chat runtime 的入站/回包、以及下载/导入 confirm 关键节点轻量写入 `logs/trace.log`；不替代中文故障日志，不改 workflow 真相。对应验证：`tests/test_trace_logging.py`、`tests/test_private_chat_runtime.py -k trace_log`、`tests/test_add_to_downloader.py -k trace_log`、`tests/test_import_to_library.py -k trace_log`。

### 2.6 历史 commit 轨迹锚点

下列是当前主线最早一批 fail-closed 闭环的 commit 标题，保留以便 docs 一致性校验和 `git log` 对照：

- `e0eb760` Fail closed missing downloader approval row
- `47a28cc` Fail closed missing import approval row
- `11be57a` Fail closed search clarification persistence
- `adb610e` Fail closed search candidate persistence
- `3fdf5c8` Fail closed search clarification clear
- `c8e2fea` Fail closed telegram BT pending persistence
- `04268f5` Fail closed auto-import skip event persistence
- `188677b` Warn on downloader finalization persistence gap
- `06ab7c1` Warn on import finalization persistence gap
- `4c8a19d` Add minimal trace logging baseline

其余“Separate X diagnostics”类微 commit 不再单独登记；通过 `git log --oneline --grep="Separate"` 检索即可。

## 3. Focused verification

为了 docs gate 与常用回归入口，保留下面这几条可直接粘贴运行的 focused verification：

- telegram bt-pending fail-closed tests：`.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "bt_processing_path_persist_fails or set_bt_processing_path_pending_logs_persistence_failure or set_bt_classification_pending_logs_persistence_failure or set_bt_tmdb_association_pending_logs_persistence_failure or set_raw_bt_destination_pending_logs_persistence_failure or enter_media_import_bt_flow_returns_service_not_ready or enter_pure_bt_flow_returns_service_not_ready"`
- search clarification pending persist fail-closed tests：`.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification_pending_logs_persistence_failure or no_result_returns_state_unavailable_when_clarification_persist_fails"`
- search candidate persist fail-closed tests：`.venv/bin/python -m pytest -q tests/test_search_media.py -k "candidate_persist_logs_persistence_failure or no_result_returns_state_unavailable_when_candidate_persist_fails"`
- search clarification clear fail-closed tests：`.venv/bin/python -m pytest -q tests/test_search_media.py -k "search_success_clears_persisted_clarification_pending or search_success_returns_state_unavailable_when_clarification_clear_fails"`
- confirm / approval row-missing fail-closed tests：`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py tests/test_import_to_library.py tests/test_persistence_sqlite.py -k "missing_approval_row or approval_repo_approve_raises_when_row_missing or approval_repo_cancel_raises_when_row_missing or approval_repo_restore_pending_raises_when_row_missing"`
- downloader / import finalization warning tests：`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py tests/test_import_to_library.py -k "executed_version_write_fails or job_completion_write_fails or record_executed_lease_version_logs_persistence_failure or mark_completed_job_logs"`
- cleanup correlation diagnostics tests：`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "correlation"`
- auto-import completed/terminal/skip tests：`.venv/bin/python -m pytest -q tests/test_get_download_status.py -k "completed_list or auto_import_terminal or skip_event or completion_event_row"`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.5 哪个主题分组，把路径或行为差异合并进去；不要再开新的 `### 2026-04-xx 分流缺口` 小节。
- 如果闭环标志着一个全新主题（例如 Feishu 长连接风险、series/anime 名称解析、BT 共享评分器），再新增一个编号子 section，并补对应 focused tests 入口。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账，不逐天 “截至 20xx-xx-xx” 追加。
- cleanup 已完成窗口的真实私聊 smoke 证据、窗口日期和 gate 结果继续只维护在 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- 每次压缩旧台账前，确认 docs consistency 测试（`tests/test_cleanup_docs_consistency.py`）和其他 docs gate 仍全绿。
