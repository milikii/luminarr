# Current status (v414)

## Current mainline

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 收工；当前阶段的 **services 层数据结构降本** 已在本轮满足 Done 定义："三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 最新闭环：`app/services/add_execution_follow_up.py` 现在有独立 focused gate；`app/services/add_to_downloader.py` 删除 `job_event / download_monitor` thin wrapper，测试改为直接钉 helper，文件从 `608` 行降到 `574` 行。
- 当前主线：**`services 层数据结构降本 · 收口完成，停在默认分支稳定态`**。
- 三座大山现状：`app/services/add_to_downloader.py` `574` 行 / `app/services/import_to_library.py` `585` 行 / `app/services/search_media.py` `460` 行。
- 默认分支全量回归：`.venv/bin/python -m pytest -q` 为 `1724 passed, 0 skipped, 4 warnings`。

## Current health

- 仓库级 CI：`make quality` / `make verify-mainline` 绿灯。
- downloader focused：`.venv/bin/python -m pytest -q tests/test_add_execution_follow_up.py tests/test_add_to_downloader.py tests/test_private_chat_confirm_runtime.py` 为 `116 passed`。
- 导入链 focused：`48 passed, 100 deselected`；`tests/test_import_to_library.py` 为 `145 passed`。
- 真实 import smoke：`19091 Transmission` 已复验 `approval_pending -> pending_approval job -> import.approval_pending`。
- 当前没有新的默认分支红灯，也没有继续硬拆 downloader 壳文件的必要。

## Latest verification

- `make quality`：`24 passed`。
- downloader focused：`.venv/bin/python -m pytest -q tests/test_add_execution_follow_up.py tests/test_add_to_downloader.py tests/test_private_chat_confirm_runtime.py` 为 `116 passed`。
- import focused：`.venv/bin/python -m pytest -q tests/test_import_pending_write_through_state.py tests/test_import_to_library.py -k "import_by_task_ref or record_pending_approval or pending_state_unavailable or copy_fallback_pending"` 为 `48 passed, 100 deselected`。
- import 全量：`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 为 `145 passed`。
- 真实 smoke：`19091 Transmission` + 临时 SQLite 复验导入申请待确认落盘链路。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1724 passed, 0 skipped, 4 warnings`。

## Current biggest risk

- `services` 三座大山已经全部过线；当前最大风险不再是文件行数，而是后续若没有新的 promoted 主线，容易回到 thin wrapper 搬家式施工。
- `app/services/import_to_library.py` 与 `app/services/add_to_downloader.py` 都不应再为了数字回头硬拆；只有出现新的 focused gate、失败边界或高风险链路真相，才值得继续动。
- shared runtime / channel 层当前没有红灯；下一条 promoted 主线应优先回到真实回归、shared runtime 边界或高风险持久化链，而不是继续磨已达标壳文件。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的"默认 3 轮施工"执行。
```
