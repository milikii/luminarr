# Current status (v373)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。
- shared runtime / channel 解耦已收掉 46 条最小直连；本轮最新闭环是把 `telegram_bot.py` 里的 delivery / formatter 薄包装从主文件移除，`telegram_runtime_adapter.py` 与 tests 已直接复用专用 runtime / formatter 模块。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；本轮 Telegram delivery / formatter / entry focused 回归为 `12 passed, 189 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。

## Latest verification

- `quality`：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- 当前闭环 focused：`tests/test_telegram_delivery_runtime.py tests/test_telegram_reply_formatter.py tests/test_telegram_bot.py -k "handle_message_replies_search_result or handle_callback_query or build_application_applies_outbound_proxy or telegram_media_sender"` 为 `12 passed, 189 deselected`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债仍在 `app/bot/telegram_bot.py`：文件已降到 `338` 行；`app/bot/private_chat_runtime.py` 已降到 `325` 行，当前主要剩 Telegram 侧 entry wrapper。
- 当前更小也更直接的下一块热点，是 `telegram_bot.py` 里的 `handle_message()` / `handle_callback_query()` / `build_application()` 仍只是把 Telegram 兼容名转发到 `telegram_runtime_adapter.py`；这块比直接切更大的 service 文件更适合作为下一条 shared runtime / channel 解耦闭环。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
