# Current status (v387)

## Current mainline

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段切到 **services 层数据结构降本**，Done 定义锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 当前阶段第 1 条主线已完成：`docs/IMPORT_PIPELINE_REDESIGN.md` 已固化 `import_to_library.py` 的入口路径、`if/elif/except` 分支密度和候选 pipeline 草图。
- 当前唯一主线切到 **`app/services/import_to_library.py` 数据结构重设计 · 第 2 轮 · 抽离 post-import side-effect pipeline`**。
- 当前这轮只允许先抽 `metadata / subtitle / refresh` 后置链，不动 approval、`jobs`、lease/version、copy-fallback pending 真相边界。
- 默认分支已在本轮再次复验全量回归绿灯：`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。
- shared runtime / channel 解耦已累计完成 `57+` 条最小直连；刚完成的上一条主线是 `private_chat_runtime.py` execution gate preparation 收口。

## Current health

- 正式入口名：`make quality`、`make verify-mainline`。
- 仓库级 CI：GitHub Actions `Quality` workflow 在 `push` / `pull_request` / `workflow_dispatch` 上运行 `make quality` + `make verify-mainline`，最近一次推送绿灯。
- 仓库入口层：绿灯；操作者入口、AI runbook、当前快照和当前主线已拆层。
- 快速质量入口：绿灯；本次 `quality` 为 `24 passed`。
- 当前主线 focused 验证入口：绿灯；上一条闭环（private-chat BT follow-up）focused 为 `52 passed, 207 deselected`。
- 全量回归：绿灯；最近一次 `.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。

## Latest verification

- `quality`：`python3 -m compileall app tests` 通过，`tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py` 为 `24 passed`。
- redesign 基线验证：`make quality` 通过；`docs/IMPORT_PIPELINE_REDESIGN.md` 已落地，`docs/NEXT_STEP.md` / `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` 已同步当前主线。
- `verify-mainline` 已覆盖：多渠道 shared runtime / Telegram adapter focused、confirm / digit focused、以及上一条闭环 BT processing / classification focused。
- 上一条闭环 focused：`tests/test_private_chat_bt_processing_runtime.py tests/test_private_chat_bt_classification_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "processing_path or classification"` 为 `52 passed, 207 deselected`。
- 全量回归：`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。
- 当前真实端点探针：`19091 Transmission` 返回 `X-Transmission-Session-Id`，`18096 Emby` 返回 `ServerName`，`19092 BT Transmission` 与 `18098 qBittorrent` 当前返回 `000`。

## Current biggest risk

- shared runtime 层微切分已进入边际递减区：`app/bot/telegram_bot.py` 当前 `256` 行（纯 wrapper 已清空），`app/bot/private_chat_runtime.py` 当前 `468` 行（bootstrap / route block / follow-up / preparation 都已收口），继续在这一层拆分收益有限——这也是 **质量硬化** 阶段 D-039 收工的直接依据。
- 当前最大结构债转移到 services 层三座大山：`app/services/import_to_library.py` `2242` 行 / `app/services/add_to_downloader.py` `1669` 行 / `app/services/search_media.py` `1018` 行，合计 `4929` 行，占全仓 `25663` 行的 `19%`。
- 风险消除路径：当前先抽 `post_import_side_effects`，把 `metadata / subtitle / refresh` 从 `import_to_library.py` 主文件拿走；等这条后置链稳定后，再碰 approval / jobs 状态机。

## Recommended Next Operator Command

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的"默认 3 轮施工"执行。
```
