# Current status (v379)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。
- shared runtime / channel 解耦已收掉 51 条最小直连；本轮最新闭环是把 `private_chat_runtime.py` 里 BT follow-up 前的 query 解析、pending 读取和 service-not-ready 早退抽到 `_resolve_bt_follow_up_precheck()`。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库级 CI：已补 GitHub Actions `Quality` workflow，在 `push` / `pull_request` / `workflow_dispatch` 上运行 `make quality` + `make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；本轮 private-chat BT pending focused 为 `20 passed, 45 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。

## Latest verification

- `quality`：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- `verify-mainline` 已补进多渠道 shared runtime / Telegram adapter focused：`tests/test_telegram_runtime_adapter.py tests/test_feishu_adapter.py tests/test_personal_wechat_text.py tests/test_wecom_adapter.py -k "routes_into_shared_runtime or routes_through_dispatch_private_chat_text or polls_single_saved_account_and_replies or callback_http_request_routes_post_into_shared_runtime_and_returns_encrypted_reply"`。
- 当前闭环 focused：`tests/test_private_chat_runtime.py tests/test_private_chat_bt_processing_runtime.py tests/test_private_chat_bt_classification_runtime.py -k "bt_processing_path or bt_classification"` 为 `20 passed, 45 deselected`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债仍在 `app/bot/private_chat_runtime.py`：文件当前为 `321` 行；`app/bot/telegram_bot.py` 已降到 `256` 行，主文件里的纯 wrapper 已基本清空。
- 当前更小也更直接的下一块热点，是 `private_chat_runtime.py` 开头的 `tg / execution_gate / traced reply` 装配仍直接堆在主函数里；这块比直接切更大的 service 文件更适合作为下一条 shared runtime / channel 解耦闭环。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
