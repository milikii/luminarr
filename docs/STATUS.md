# Current status (v355)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。
- shared runtime / channel 解耦已收掉 19 条最小直连；本轮最新闭环是把 BT scheduler loop / 日志 / downloader resolution 也并入 `app/bot/telegram_sidecar_runtime.py`，Telegram 生命周期编排现在不再回看 `telegram_bot.py` 内部 helper。

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
- Telegram confirm / digit / reminder 相关 focused 回归：`tests/test_telegram_bot.py -k "confirm or digit or pending_returns_reminder or deduplicate or update_id_invalid or callback_id_missing" -q` 为 `45 passed, 161 deselected`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1632 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债不再是 Telegram 生命周期编排，而是 `app/bot/private_chat_runtime.py` 仍有 `1421` 行、`app/bot/telegram_bot.py` 仍有 `819` 行，并继续承载 BT 路由与 Telegram 发送 / 格式化细节。
- 当前更小也更直接的下一块热点，是 `telegram_bot.py` 剩余发送媒资、reply 格式化和 Telegram 特有文案拼接仍挤在同一文件；这块比回头继续拆 `private_chat_runtime.py` 更容易切成新的最小闭环。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
