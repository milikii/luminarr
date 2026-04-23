# Current status (v414)

## Current mainline

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 收工；当前阶段的 **services 层数据结构降本** 保持 Done 状态："三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 最新闭环：`Makefile` 已新增 `test-downloader-focused`、`test-import-focused`、`verify-quality-gates`；Feishu / WeCom 本地 webhook smoke 已补最小起服重试，减少端口监听偶发抖动。
- 当前主线：**`固定质量入口已落地，但 verify-quality-gates 仍暴露本地 webhook 监听 skip`**。
- 三座大山现状：`app/services/add_to_downloader.py` `574` 行 / `app/services/import_to_library.py` `585` 行 / `app/services/search_media.py` `460` 行。
- 默认分支全量回归：`.venv/bin/python -m pytest -q -rs` 单独复验为 `1725 passed, 4 warnings`。

## Current health

- 仓库级 CI：`make quality` / `make verify-mainline` 绿灯；`make verify-quality-gates` 仍会偶发落到 `1723 passed, 2 skipped, 4 warnings`。
- 固定质量入口：`Makefile` 已新增 `test-downloader-focused`、`test-import-focused`、`verify-quality-gates`，后续不必再手敲长 pytest 命令。
- downloader focused：`.venv/bin/python -m pytest -q tests/test_add_execution_follow_up.py tests/test_add_to_downloader.py tests/test_private_chat_confirm_runtime.py` 为 `116 passed`。
- 导入链 focused：`48 passed, 100 deselected`；`tests/test_import_to_library.py` 为 `145 passed`。
- 真实 import smoke：`19091 Transmission` 已复验 `approval_pending -> pending_approval job -> import.approval_pending`。
- 当前没有新的业务红灯，但固定质量入口还有一处环境型不稳定项。

## Latest verification

- `make quality`：`25 passed`。
- `make verify-quality-gates`：全量阶段复现 `1723 passed, 2 skipped, 4 warnings`，随后 downloader focused `116 passed`、import focused `48 passed, 100 deselected`。
- downloader focused：`.venv/bin/python -m pytest -q tests/test_add_execution_follow_up.py tests/test_add_to_downloader.py tests/test_private_chat_confirm_runtime.py` 为 `116 passed`。
- import focused：`.venv/bin/python -m pytest -q tests/test_import_pending_write_through_state.py tests/test_import_to_library.py -k "import_by_task_ref or record_pending_approval or pending_state_unavailable or copy_fallback_pending"` 为 `48 passed, 100 deselected`。
- import 全量：`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 为 `145 passed`。
- 真实 smoke：`19091 Transmission` + 临时 SQLite 复验导入申请待确认落盘链路。
- 全量回归：`.venv/bin/python -m pytest -q -rs` 为 `1725 passed, 4 warnings`。

## Current biggest risk

- `services` 三座大山已经全部过线；当前最大风险不再是文件行数，而是后续若没有新的 promoted 主线，容易回到 thin wrapper 搬家式施工。
- `app/services/import_to_library.py` 与 `app/services/add_to_downloader.py` 都不应再为了数字回头硬拆；只有出现新的 focused gate、失败边界或高风险链路真相，才值得继续动。
- 当前最大新增风险是 [tests/test_feishu_adapter.py](/home/alex/projects/luminarr/tests/test_feishu_adapter.py) / [tests/test_wecom_adapter.py](/home/alex/projects/luminarr/tests/test_wecom_adapter.py) 的本地 webhook 监听 smoke 在 full gate 里仍会偶发 skip；下一条最小主线应优先把这处环境型波动收稳。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的"默认 3 轮施工"执行。
```
