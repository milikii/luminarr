# Current status (v376)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。
- shared runtime / channel 解耦已收掉 49 条最小直连；本轮最新闭环是把 `telegram_bot.py` 里的剩余纯 wrapper 清零，应用构建入口已直接复用 `telegram_runtime_adapter.py`，无调用点的 Telegram 私聊查询薄包装也已移除。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库级 CI：已补 GitHub Actions `Quality` workflow，在 `push` / `pull_request` 上运行 `make quality` + `make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；本轮 Telegram build focused 为 `8 passed, 186 deselected`，补充 Telegram import 面 focused 为 `2 passed, 192 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。

## Latest verification

- `quality`：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- 当前闭环 focused 1：`tests/test_telegram_bot.py -k "build_application_applies_outbound_proxy or handle_message_replies_search_result or handle_callback_query"` 为 `8 passed, 186 deselected`。
- 当前闭环 focused 2：`tests/test_telegram_bot.py -k "handle_message_replies_search_result or build_application_applies_outbound_proxy"` 为 `2 passed, 192 deselected`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债已转到 `app/bot/private_chat_runtime.py`：文件仍为 `325` 行；`app/bot/telegram_bot.py` 已降到 `256` 行，主文件里的纯 wrapper 已基本清空。
- 当前更小也更直接的下一块热点，是 `private_chat_runtime.py` 里的 `dispatch_private_chat_text()` 仍只是把共享入口兼容名转发到 `handle_private_chat_query_text()`；这块比直接切更大的 service 文件更适合作为下一条 shared runtime / channel 解耦闭环。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
