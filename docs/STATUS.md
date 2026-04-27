# Current status (v500)

## Current mainline
- **质量硬化** 继续保持完成态；当前最小闭环切到 **文档入口收口 / 当前真相对齐**，不改业务代码。
- 这轮先修文档漂移：README 不再写具体施工热点；`docs/STATUS.md` 只写短快照；`docs/NEXT_STEP.md` 只写当前唯一主线、边界和退出条件。
- 成人 BT 不是空白：当前已有 PT/BT 分流、BT 成人链问询、成人归档目录配置、`adult_content_registry`、归档保留期清理、只读补全和展示基础；但成人 BT 继续扩功能不是本轮主线。
- `cleanup_*_support.py` 当前为 `0` 个；cleanup 收口、workflow trace 收口、`_COMPAT_REEXPORTS` 清理、`config.py` 重复解析收口和 downloader route helper 收口继续保持完成态。

## Current health
- 默认分支最近业务回归保持绿灯；当前风险主要来自文档入口重复、过时主线残留和 docs gate 锁死易漂移事实。
- 先完成文档收口，再决定下一条业务主线；在文档真相未对齐前，不切成人 BT 新功能，也不继续扩大 downloader route 收口范围。

## Latest verification
- `tests/test_cleanup_docs_consistency.py`：`7 passed`
- `tests/test_config.py`：`39 passed, 0 skipped`
- `tests/test_config.py tests/test_downloader_route_lookup.py tests/test_main.py`：`71 passed, 4 warnings`
- `tests/test_downloader_route_lookup.py tests/test_main.py`：`34 passed, 4 warnings`
- `.venv/bin/python -m pytest tests/test_main.py tests/test_downloader_route_lookup.py`：`34 passed, 4 warnings`
- `tests/test_cleanup_downloaded_source.py tests/test_cleanup_cross_channel_smoke.py`：`425 passed, 4 warnings`
- `make quality`：通过（`26 passed`）
- `make verify-mainline`：通过

## Current biggest risk
- 若跳过文档收口直接继续成人 BT 或继续拆 helper，后续 agent 会同时被 README、STATUS、NEXT_STEP 里的旧主线牵引，增加误改范围。
- 当前成人 BT 后续仍可作为候选主线，但必须在文档入口稳定后再切，并先明确缺口与退出条件。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是文档入口收口 / 当前真相对齐。只改 README、docs/STATUS.md、docs/NEXT_STEP.md、docs/OPERATOR_RUNBOOK.md、docs/HUMAN_START_HERE.md、docs/INDEX.md 和 docs gate 相关测试；不改业务代码、不改协议、不改 SQLite 真相边界。先把“是否先做成人 BT”记录为后续候选，不在本轮开新功能。
```
