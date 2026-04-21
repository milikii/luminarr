# Current status (v344)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1630 passed, 2 skipped`。
- shared runtime / channel 解耦已先收掉 8 条最小直连：`raw_bt` 目录问询改为复用 `app/bot/raw_bt_destination_runtime.py`，BT TMDB 关联问询改为复用 `app/bot/bt_tmdb_association_runtime.py`，下载器角色绑定解析改为复用 `app/bot/downloader_execution_runtime.py`，execution gate / sync policy helper 改为复用 `app/bot/execution_runtime.py`，frustration / BT intent / BT choice 文本解析 helper 改为复用 `app/bot/query_text_runtime.py`，search reactive recovery helper 改为复用 `app/bot/search_recovery_runtime.py`，BT processing path pending state helper 改为复用 `app/bot/bt_processing_path_runtime.py`，BT classification pending state helper 改为复用 `app/bot/bt_classification_runtime.py`。
- 非技术操作者入口已单独收口到 `docs/HUMAN_START_HERE.md` 与 `docs/OPERATOR_RUNBOOK.md`；`README.md` 不再承担历史台账索引角色。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 等价命令结果为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；本次 `verify-mainline` 等价命令结果为 `25 passed, 17 deselected` + `12 passed, 204 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1630 passed, 2 skipped`。

## Latest verification

- `quality` 等价命令：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- `verify-mainline` 等价命令：`tests/test_get_download_status.py` focused 为 `25 passed, 17 deselected`，`tests/test_telegram_bot.py` focused 为 `12 passed, 204 deselected`。
- execution runtime / shared runtime focused 回归：`tests/test_execution_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -q` 为 `274 passed`。
- query text runtime / shared runtime focused 回归：`tests/test_query_text_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -q` 为 `275 passed`。
- search recovery runtime / shared runtime focused 回归：`tests/test_search_recovery_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -q` 为 `275 passed`。
- BT processing path pending focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "processing_path" -q` 为 `20 passed, 250 deselected`。
- BT classification pending focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "classification" -q` 为 `24 passed, 246 deselected`。
- 下载审批重启回归：`tests/test_persistence_sqlite.py -k "downloader_pending_approval_persists_for_restart or downloader_confirm_stale_guard_blocks_duplicate_after_restart"` 为 `2 passed`。
- 导入 restart / copy-fallback 回归：`tests/test_persistence_sqlite.py -k "completed_download_truth_after_restart_can_progress_to_import_pending or confirm_rebuilds_context_from_persisted_job_after_restart or copy_fallback_pending_survives_restart_and_second_confirm_copies or cancel_pending_import_updates_persisted_truth"` 为 `4 passed`。
- 跨渠道 shared delivery 文案回归：`tests/test_feishu_adapter.py tests/test_personal_wechat_text.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k "handle_feishu_private_text_event_routes_into_shared_runtime or personal_wechat_text_service_polls_single_saved_account_and_replies or handle_wecom_private_text_event_routes_into_shared_runtime or handle_wecom_callback_http_request_routes_post_into_shared_runtime_and_returns_encrypted_reply or handle_message_replies_search_result or handle_message_digit_routes_to_add_service or handle_callback_query_digit_routes_to_add_service or handle_callback_query_digit_uses_callback_context_when_effective_context_missing or handle_message_frustration_without_state_still_routes_to_search or handle_message_frustration_cancels_pending_import"` 为 `10 passed, 314 deselected`。
- raw BT 目录问询 focused 回归：`tests/test_private_chat_runtime.py -k raw_bt_destination -q` 为 `4 passed, 50 deselected`，`tests/test_telegram_bot.py -k raw_bt_destination -q` 为 `14 passed, 202 deselected`。
- BT TMDB / raw BT follow-up focused 回归：`tests/test_private_chat_runtime.py -k "bt_tmdb_association or raw_bt_destination" -q` 为 `4 passed, 50 deselected`，`tests/test_telegram_bot.py -k "bt_tmdb_association or raw_bt_destination" -q` 为 `29 passed, 187 deselected`。
- shared runtime / 下载器解析 focused 回归：`tests/test_private_chat_runtime.py -q` 为 `54 passed`，`tests/test_telegram_bot.py -k "bt_tmdb_association or raw_bt_destination or bt_subscription" -q` 为 `33 passed, 183 deselected`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1630 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债不再是测试红灯，而是 shared runtime 仍直接复用 `telegram_bot.py` 里的 BT TMDB association pending state helper。
- `app/bot/private_chat_runtime.py`、`app/bot/telegram_bot.py` 仍是热点大文件；BT classification pending state helper 已先收口，下一段更小也更中性的边界是 `_set_bt_tmdb_association_pending`、`_get_bt_tmdb_association_pending`、`_clear_bt_tmdb_association_pending` 这一组 BT TMDB association pending state helper。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
