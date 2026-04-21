# Current status (v355)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1642 passed, 2 skipped`。
- shared runtime / channel 解耦已收掉 22 条最小直连；本轮最新闭环是把 `private_chat_runtime.py` 里的 confirm 路由抽到 `app/bot/private_chat_confirm_runtime.py`，job 关联查询、workflow 分流和 pending add fallback 现在有独立 focused tests，不改审批语义。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 等价命令结果为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；本次 `verify-mainline` 为 `25 passed, 17 deselected` + `14 passed, 192 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。

## Latest verification

- `quality` 等价命令：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- `verify-mainline`：`tests/test_get_download_status.py -k "parse_status_query or get_status_text_success or personal_wechat_channel or render_status_reply or download_monitor or completion_event or auto_import_terminal or skip_event" -q` 为 `25 passed, 17 deselected`；`tests/test_download_follow_up_runtime.py tests/test_telegram_bot.py -k "download_completion or post_download_auto_import_scheduler or bt_subscription_scheduler or build_application_applies_outbound_proxy" -q` 为 `14 passed, 192 deselected`。
- personal WeChat 登录回归补测：`tests/test_private_chat_runtime.py::test_dispatch_private_chat_text_routes_personal_wechat_login_without_telegram_context tests/test_telegram_bot.py::test_handle_message_routes_personal_wechat_login_and_sends_qr_result -q` 为 `2 passed`。
- download follow-up runtime focused 回归：`tests/test_download_follow_up_runtime.py tests/test_telegram_bot.py -k "download_completion or post_download_auto_import_scheduler or bt_subscription_scheduler or build_application_applies_outbound_proxy" -q` 为 `14 passed, 192 deselected`。
- Telegram adapter focused 回归：`tests/test_telegram_runtime_adapter.py -q` 为 `10 passed`。
- Telegram reply formatter focused 回归：`tests/test_telegram_reply_formatter.py tests/test_telegram_bot.py -k "import_formats_import_approval_for_telegram or digit_routes_to_add_service or handle_message_replies_search_result or build_telegram_send_media_func" -q` 为 `4 passed, 193 deselected`。
- Telegram delivery focused 回归：`tests/test_telegram_delivery_runtime.py tests/test_telegram_bot.py -k "telegram_media_sender or build_application_applies_outbound_proxy or handle_message_routes_personal_wechat_login_and_sends_qr_result" -q` 为 `6 passed, 190 deselected`。
- private chat confirm focused 回归：`tests/test_private_chat_confirm_runtime.py tests/test_private_chat_runtime.py -k "confirm" -q` 为 `7 passed, 52 deselected`。
- Telegram confirm / digit / reminder 相关 focused 回归：`tests/test_telegram_bot.py -k "confirm or digit or pending_returns_reminder or deduplicate or update_id_invalid or callback_id_missing" -q` 为 `45 passed, 161 deselected`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1642 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债仍在 `app/bot/private_chat_runtime.py`：文件已降到 `1305` 行，但仍承载 BT follow-up、digit-selection、trace 包装和搜索兜底等多段共享逻辑；`app/bot/telegram_bot.py` 保持 `661` 行。
- 当前更小也更直接的下一块热点，是 `private_chat_runtime.py` 的 digit-selection 路由仍同时处理澄清态读取、下载器解析和 add_to_downloader 调度；这条链是 confirm 之后的下一段审批前置编排。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
