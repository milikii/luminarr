# Current status (v414)

## Current mainline

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 收工；当前阶段继续做 **services 层数据结构降本**，Done 仍锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 最新闭环：`app/services/import_pending_write_through_state.py` + `app/services/import_trace_logger.py` 已承接 `import_by_task_ref()` 的待确认写入 / trace wrapper；`app/services/import_to_library.py` 已从 `654` 行降到 `585` 行，并新增 `tests/test_import_pending_write_through_state.py` focused gate。
- 当前主线：**`services 层数据结构降本 · add_to_downloader.py 最后 8 行 worth-it 复评估`**。
- 三座大山现状：`app/services/add_to_downloader.py` `608` 行 / `app/services/import_to_library.py` `585` 行 / `app/services/search_media.py` `460` 行。
- 默认分支全量回归：`.venv/bin/python -m pytest -q` 为 `1724 passed, 0 skipped, 4 warnings`。

## Current health

- 仓库级 CI：`make quality` / `make verify-mainline` 绿灯。
- 导入链 focused：`48 passed, 100 deselected`；`tests/test_import_to_library.py` 为 `145 passed`。
- 真实 import smoke：`19091 Transmission` 已复验 `approval_pending -> pending_approval job -> import.approval_pending`。
- 默认分支当前没有新红灯，可继续围绕 downloader 剩余 `8` 行做 worth-it 复评估。

## Latest verification

- `make quality`：`24 passed`。
- import focused：`.venv/bin/python -m pytest -q tests/test_import_pending_write_through_state.py tests/test_import_to_library.py -k "import_by_task_ref or record_pending_approval or pending_state_unavailable or copy_fallback_pending"` 为 `48 passed, 100 deselected`。
- import 全量：`.venv/bin/python -m pytest -q tests/test_import_to_library.py` 为 `145 passed`。
- 真实 smoke：`19091 Transmission` + 临时 SQLite 复验导入申请待确认落盘链路。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1724 passed, 0 skipped, 4 warnings`。

## Current biggest risk

- 最大剩余结构债只剩 `app/services/add_to_downloader.py` `608` 行；是否继续拆最后 `8` 行，必须先证明不是纯 thin wrapper 搬家。
- `app/services/import_to_library.py` 已达 `≤ 600`；除非出现新的 focused gate 或新的失败边界，不再为了数字回头硬拆。
- shared runtime / channel 层已进入边际递减区；本轮不回到 `telegram_bot.py` / `private_chat_runtime.py`。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的"默认 3 轮施工"执行。
```
