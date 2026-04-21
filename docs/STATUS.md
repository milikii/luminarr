# Current status (v372)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。
- shared runtime / channel 解耦已收掉 45 条最小直连；本轮最新闭环是把 `telegram_bot.py` 里的 download follow-up wrapper 从主文件移除，download follow-up 调度只保留在 `app/bot/download_follow_up_runtime.py`。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；本轮 download follow-up / Telegram build focused 回归为 `11 passed, 196 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。

## Latest verification

- `quality`：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- 当前闭环 focused：`tests/test_download_follow_up_runtime.py tests/test_telegram_bot.py -k "download_completion or post_download_auto_import_scheduler or build_application_applies_outbound_proxy"` 为 `11 passed, 196 deselected`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债仍在 `app/bot/telegram_bot.py`：文件已降到 `359` 行；`app/bot/private_chat_runtime.py` 已降到 `325` 行，当前主要剩 Telegram 侧 delivery / formatter 薄包装。
- 当前更小也更直接的下一块热点，是 `telegram_bot.py` 里的 `build_telegram_send_media_func()` / `build_telegram_send_text_func()` / `_format_telegram_reply()` 仍只是把 Telegram 兼容名转发到专用 runtime / formatter 模块；这块比直接切更大的 service 文件更适合作为下一条 shared runtime / channel 解耦闭环。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
