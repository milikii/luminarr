# Current status (v335)

## Current mainline

- 当前唯一 promoted 主线仍是 **Telegram 后台 completion polling 直连共享 follow-up helper 收口**。
- 这条主线的目标不变：让 `telegram_bot._poll_pending_download_completion_once()` 直接复用共享 follow-up helper，而不是再通过 `get_status_text()` 的间接副作用推进状态观察、完成事件和自动导入。
- 非技术操作者入口已单独收口到 `docs/HUMAN_START_HERE.md` 与 `docs/OPERATOR_RUNBOOK.md`；`README.md` 不再承担历史台账索引角色。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 等价命令结果为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；本次 `verify-mainline` 等价命令结果为 `25 passed, 17 deselected` + `12 passed, 204 deselected`。
- 全量回归：黄灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1597 passed, 16 failed, 2 skipped`，失败集中在跨渠道文案断言和 persistence restart 回归。

## Latest verification

- `quality` 等价命令：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- `verify-mainline` 等价命令：`tests/test_get_download_status.py` focused 为 `25 passed, 17 deselected`，`tests/test_telegram_bot.py` focused 为 `12 passed, 204 deselected`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- 默认分支还不能宣称“全量 pytest 稳绿”；当前最大缺口不是入口文档，而是历史测试现实与当前实现之间还有回归未收口。
- shared runtime 仍直接复用 Telegram 内部 helper，这会继续抬高 fork 维护成本。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
