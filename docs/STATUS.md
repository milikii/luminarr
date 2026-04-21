# Current status (v361)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1670 passed, 2 skipped`。
- shared runtime / channel 解耦已收掉 33 条最小直连；本轮最新闭环是把 `private_chat_runtime.py` 里的 BT batch confirm 执行 helper 抽到 `app/bot/private_chat_bt_batch_confirm_runtime.py`，并把对应 focused tests 补进 `verify-mainline`。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；本次 `verify-mainline` 12 组回归全部通过，其中新增 BT batch confirm 组为 `39 passed, 216 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1670 passed, 2 skipped`。

## Latest verification

- `quality`：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- `verify-mainline`：status / download follow-up / trace / personal WeChat login / BT batch confirm / BT read-only / search / import / watchlist / BT subscription / cleanup 共 12 组 focused 回归全部通过。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1670 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债仍在 `app/bot/private_chat_runtime.py`：文件已降到 `932` 行，但仍承载 frustration cancel/reset、BT follow-up 和兜底调度等多段共享逻辑；`app/bot/telegram_bot.py` 保持 `661` 行。
- 当前更小也更直接的下一块热点，是 `private_chat_runtime.py` 里的 frustration cancel / reset helper 仍留在主文件里直接拿多个 service/repo 做取消与清理判断；这块比继续深入 BT follow-up 更贴近 shared runtime / service 解耦目标。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
