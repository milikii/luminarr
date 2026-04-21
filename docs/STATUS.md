# Current status (v357)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1666 passed, 2 skipped`。
- shared runtime / channel 解耦已收掉 29 条最小直连；本轮最新闭环是把 `private_chat_runtime.py` 里的 BT subscription 路由抽到 `app/bot/private_chat_bt_subscription_runtime.py`，并把 subscription focused tests 补进 `verify-mainline`。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 等价命令结果为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；本次 `verify-mainline` 为 `25 passed, 17 deselected` + `14 passed, 193 deselected` + `3 passed, 55 deselected` + `5 passed, 248 deselected` + `8 passed, 245 deselected` + `6 passed, 247 deselected` + `7 passed, 247 deselected` + `7 passed, 248 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1666 passed, 2 skipped`。

## Latest verification

- `quality` 等价命令：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- `verify-mainline`：`tests/test_get_download_status.py -k "parse_status_query or get_status_text_success or personal_wechat_channel or render_status_reply or download_monitor or completion_event or auto_import_terminal or skip_event" -q` 为 `25 passed, 17 deselected`；`tests/test_download_follow_up_runtime.py tests/test_telegram_bot.py -k "download_completion or post_download_auto_import_scheduler or bt_subscription_scheduler or build_application_applies_outbound_proxy" -q` 为 `14 passed, 193 deselected`；`tests/test_private_chat_trace_runtime.py tests/test_private_chat_runtime.py -k trace -q` 为 `3 passed, 55 deselected`；`tests/test_private_chat_login_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k personal_wechat_login -q` 为 `5 passed, 248 deselected`；`tests/test_private_chat_status_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k status -q` 为 `8 passed, 245 deselected`；`tests/test_private_chat_import_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "handle_import_query or import_routes_to_import_service or import_formats_import_approval_for_telegram or import_replies_service_not_ready" -q` 为 `6 passed, 247 deselected`；`tests/test_private_chat_watchlist_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "handle_watchlist_query or watchlist_routes_to_watchlist_service or watchlist_series_routes_to_watchlist_service or watchlist_replies_service_not_ready" -q` 为 `7 passed, 247 deselected`；`tests/test_private_chat_bt_subscription_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "handle_bt_subscription_query or bt_subscription_routes_to_service or bt_subscription_run_uses_bound_downloader_context or bt_subscription_replies_service_not_ready or bt_subscription_run_replies_config_missing" -q` 为 `7 passed, 248 deselected`。
- private chat import focused 回归：`tests/test_private_chat_import_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "handle_import_query or import_routes_to_import_service or import_formats_import_approval_for_telegram or import_replies_service_not_ready" -q` 为 `6 passed, 247 deselected`。
- private chat watchlist focused 回归：`tests/test_private_chat_watchlist_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "handle_watchlist_query or watchlist_routes_to_watchlist_service or watchlist_series_routes_to_watchlist_service or watchlist_replies_service_not_ready" -q` 为 `7 passed, 247 deselected`。
- private chat BT subscription focused 回归：`tests/test_private_chat_bt_subscription_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "handle_bt_subscription_query or bt_subscription_routes_to_service or bt_subscription_run_uses_bound_downloader_context or bt_subscription_replies_service_not_ready or bt_subscription_run_replies_config_missing" -q` 为 `7 passed, 248 deselected`。
- private chat status focused 回归：`tests/test_private_chat_status_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k status -q` 为 `8 passed, 245 deselected`。
- private chat login focused 回归：`tests/test_private_chat_login_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k personal_wechat_login -q` 为 `5 passed, 248 deselected`。
- private chat trace focused 回归：`tests/test_private_chat_trace_runtime.py tests/test_private_chat_runtime.py -k trace -q` 为 `3 passed, 55 deselected`。
- download follow-up runtime focused 回归：`tests/test_download_follow_up_runtime.py tests/test_telegram_bot.py -k "download_completion or post_download_auto_import_scheduler or bt_subscription_scheduler or build_application_applies_outbound_proxy" -q` 为 `14 passed, 192 deselected`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1666 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债仍在 `app/bot/private_chat_runtime.py`：文件已降到 `1161` 行，但仍承载 BT follow-up、cleanup 路由和搜索兜底等多段共享逻辑；`app/bot/telegram_bot.py` 保持 `661` 行。
- 当前更小也更直接的下一块热点，是 `private_chat_runtime.py` 里的 cleanup inspect / cleanup 路由仍留在主调度里直接拼 side-effect action 和 cleanup runner；这块比继续深入 BT follow-up 更贴近 shared runtime / service 解耦目标。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
