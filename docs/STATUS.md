# Current status (v351)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。
- shared runtime / channel 解耦已收掉 19 条最小直连；本轮最新闭环是把 `post_download_auto_import` / `download_completion_polling` 调度从 `telegram_bot.py` 抽到 `app/bot/download_follow_up_runtime.py`，Telegram 渠道文件只保留启动/停止这条 follow-up 链的薄包装。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 等价命令结果为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；本次 download follow-up runtime focused 回归为 `14 passed, 192 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。

## Latest verification

- `quality` 等价命令：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- download follow-up runtime focused 回归：`tests/test_download_follow_up_runtime.py tests/test_telegram_bot.py -k "download_completion or post_download_auto_import_scheduler or bt_subscription_scheduler or build_application_applies_outbound_proxy" -q` 为 `14 passed, 192 deselected`。
- Telegram adapter focused 回归：`tests/test_telegram_runtime_adapter.py -q` 为 `10 passed`。
- Telegram confirm / digit / reminder 相关 focused 回归：`tests/test_telegram_bot.py -k "confirm or digit or pending_returns_reminder or deduplicate or update_id_invalid or callback_id_missing" -q` 为 `45 passed, 161 deselected`。
- BT TMDB / raw_bt / reminder focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "bt_tmdb_association or raw_bt_destination or pending_returns_reminder" -q` 为 `34 passed, 238 deselected`。
- BT processing / classification focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "processing_path or classification" -q` 为 `43 passed, 229 deselected`。
- `tests/test_get_download_status.py -q` 为 `42 passed`。
- frustration / cancel focused 回归：`tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "frustration or clear_fails_on_cancel or clear_result_is_missing_on_cancel or cancel_state_unavailable or pending_job_lookup_failure" -q` 为 `18 passed, 254 deselected`。
- Telegram frustration focused 回归：`tests/test_telegram_bot.py -k "frustration" -q` 为 `7 passed, 209 deselected`。
- BT 批量确认 focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "bt_batch_confirm" -q` 为 `34 passed, 238 deselected`。
- BT 只读探索 / cleanup focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "bt_read_only or cleanup" -q` 为 `35 passed, 235 deselected`。
- BT processing path pending focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "processing_path" -q` 为 `20 passed, 250 deselected`。
- BT classification pending focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "classification" -q` 为 `24 passed, 246 deselected`。
- BT TMDB association pending focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "bt_tmdb_association" -q` 为 `15 passed, 255 deselected`。
- raw BT destination pending focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "raw_bt_destination" -q` 为 `18 passed, 252 deselected`。
- BT 流程入口 focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "processing_path or bt_classification or enter_media_import_bt_flow or enter_pure_bt_flow" -q` 为 `43 passed, 227 deselected`。
- BT TMDB / raw BT follow-up focused 回归：`tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "bt_tmdb_association or raw_bt_destination" -q` 为 `33 passed, 237 deselected`。
- 下载审批重启回归：`tests/test_persistence_sqlite.py -k "downloader_pending_approval_persists_for_restart or downloader_confirm_stale_guard_blocks_duplicate_after_restart"` 为 `2 passed`。
- 导入 restart / copy-fallback 回归：`tests/test_persistence_sqlite.py -k "completed_download_truth_after_restart_can_progress_to_import_pending or confirm_rebuilds_context_from_persisted_job_after_restart or copy_fallback_pending_survives_restart_and_second_confirm_copies or cancel_pending_import_updates_persisted_truth"` 为 `4 passed`。
- 跨渠道 shared delivery 文案回归：`tests/test_feishu_adapter.py tests/test_personal_wechat_text.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k "handle_feishu_private_text_event_routes_into_shared_runtime or personal_wechat_text_service_polls_single_saved_account_and_replies or handle_wecom_private_text_event_routes_into_shared_runtime or handle_wecom_callback_http_request_routes_post_into_shared_runtime_and_returns_encrypted_reply or handle_message_replies_search_result or handle_message_digit_routes_to_add_service or handle_callback_query_digit_routes_to_add_service or handle_callback_query_digit_uses_callback_context_when_effective_context_missing or handle_message_frustration_without_state_still_routes_to_search or handle_message_frustration_cancels_pending_import"` 为 `10 passed, 314 deselected`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债不再是 Telegram follow-up 调度边界，而是 `app/bot/private_chat_runtime.py` 仍有 `1421` 行、`app/bot/telegram_bot.py` 仍有 `1105` 行，并继续承载 BT 路由和渠道调度入口。
- 当前更直接的质量缺口不是实现边界，而是现有 `make verify-mainline` 还没直接指向新拆出的 `tests/test_download_follow_up_runtime.py`；如果不补这条固定入口，后续回归仍可能先在全量 pytest 才暴露。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
