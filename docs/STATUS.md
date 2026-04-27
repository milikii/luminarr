# Current status (v507)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮按文档连续完成 10 个最小代码闭环：收窄 `post_download_auto_import` 终态查询、skip event、completed list，`search_candidate_state` 候选读取，`cleanup_correlation_lookup` 关联查询/job 解析，`private_chat_frustration_runtime` 待处理 job 查询，以及 BT `processing_path` / `classification` / `tmdb_association` / `raw_bt_destination` pending 状态边界。
- 这些路径不再吞泛 `Exception`，只兜明确的 repo persistence 异常、`sqlite3.Error`，或原有业务状态异常；外部搜索、TMDB/网络、后台 loop 的隔离性宽捕获未机械替换。
- 默认分支协议、SQLite schema、下载/导入/审批语义未变化；本轮主要是异常边界和测试模拟同步。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 覆盖 auto-import、候选读取、cleanup correlation、frustration pending job、BT pending 四段状态链路。
- `make quality` 通过，`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- `tests/test_get_download_status.py -k "auto_import_terminal or terminal_lookup"`：`3 passed, 42 deselected`
- `tests/test_get_download_status.py -k "skip_event"`：`10 passed, 35 deselected`
- `tests/test_get_download_status.py -k "completed_list"`：`3 passed, 42 deselected`
- `tests/test_private_chat_runtime.py -k "cached_candidate_lookup_failure"`：`1 passed, 56 deselected`
- `tests/test_search_media.py -k "cached_candidates_distinguishes_lookup_failure"`：`1 passed, 184 deselected`
- `tests/test_add_to_downloader.py -k "candidate_lookup_fails"`：`1 passed, 111 deselected`
- `tests/test_cleanup_downloaded_source.py -k "correlation_query_failure or correlation_lookup_result_missing or logs_job_lookup_failure"`：`7 passed, 42 deselected`
- `tests/test_private_chat_frustration_runtime.py -k "pending_job_lookup_failure"`：`1 passed, 4 deselected`
- `tests/test_telegram_bot.py -k "bt_classification_pending or enter_media_import_bt_flow_returns_service_not_ready_when_classification_persist_fails"`：`13 passed, 181 deselected`
- `tests/test_private_chat_runtime.py -k "bt_classification"`：`5 passed, 52 deselected`
- `tests/test_telegram_bot.py -k "bt_processing_path_pending or enter_media_import_bt_flow_returns_service_not_ready_when_processing_path_persist_fails"`：`12 passed, 182 deselected`
- `tests/test_private_chat_runtime.py -k "bt_processing_path"`：`6 passed, 51 deselected`
- `tests/test_telegram_bot.py -k "bt_tmdb_association_pending or set_bt_tmdb_association_pending or clear_bt_tmdb_association_pending"`：`9 passed, 185 deselected`
- `tests/test_private_chat_runtime.py -k "bt_tmdb"`：`5 passed, 52 deselected`
- `tests/test_telegram_bot.py -k "raw_bt_destination_pending or set_raw_bt_destination_pending or clear_raw_bt_destination_pending or enter_pure_bt_flow_returns_service_not_ready_when_destination_persist_fails or enter_media_import_bt_flow_returns_service_not_ready_when_tmdb_pending_persist_fails"`：`11 passed, 183 deselected`
- `tests/test_private_chat_runtime.py -k "raw_bt_destination"`：`4 passed, 53 deselected`
- `tests/test_private_chat_bt_direct_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "handle_bt_direct_intent_query or magnet_routes_to_bt_direct_split or bt_processing_path_persist_fails"`：`7 passed, 248 deselected`
- `tests/test_private_chat_frustration_runtime.py tests/test_private_chat_runtime.py -k "handle_frustration_query or cancel or pending_job_lookup_failure"`：`16 passed, 46 deselected`
- `tests/test_config.py`：`39 passed, 0 skipped`
- `make quality`：通过（`27 passed`）
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
