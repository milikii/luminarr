# Current status (v360)

## Current mainline

- 当前阶段已切到 **质量硬化**。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1670 passed, 2 skipped`。
- shared runtime / channel 解耦已收掉 32 条最小直连；本轮最新闭环是把 `private_chat_runtime.py` 里的 BT read-only helper / batch preview 抽到 `app/bot/private_chat_bt_read_only_runtime.py`，并把对应 focused tests 补进 `verify-mainline`。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：当前代码已通过编译和 focused 测试，`quality` 唯一红灯是 `docs/STATUS.md` 超过 6000 字限制；本次压短后需重跑确认。
- 当前主线 focused 验证入口：绿灯；本次 `verify-mainline` 11 组回归全部通过，其中新增 BT read-only 组为 `38 passed, 217 deselected`，search 组为 `6 passed, 248 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1670 passed, 2 skipped`。

## Latest verification

- `quality`：`python3 -m compileall app tests` 通过，`tests/test_makefile.py` 与 cleanup 文档门通过；唯一失败是 `tests/test_cleanup_docs_consistency.py::test_status_stays_short_snapshot_and_points_to_operator_flow`，原因是 `docs/STATUS.md` 长度达到 `6244` 字。
- `verify-mainline`：status / download follow-up / trace / personal WeChat login / BT read-only / search / import / watchlist / BT subscription / cleanup 共 11 组 focused 回归全部通过。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1670 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支已恢复“全量 pytest 稳绿”，当前最大结构债仍在 `app/bot/private_chat_runtime.py`：文件已降到 `977` 行，但仍承载 BT follow-up、BT batch confirm 和兜底调度等多段共享逻辑；`app/bot/telegram_bot.py` 保持 `661` 行。
- 当前更小也更直接的下一块热点，是 `private_chat_runtime.py` 里的 BT batch confirm 仍留在主文件里直接拿 `AddToDownloaderService`、做 downloader 绑定解析并执行 gate；这块比继续深入 BT follow-up 更贴近 shared runtime / service 解耦目标。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
