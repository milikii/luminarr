# Current status (v543)

## Current mainline
- **质量硬化** 已收工；当前主线是 `services` 层数据结构降本。
- 最近已合并：`add_pending_persistence.py`、`add_request_facade.py`、`add_confirm_preparation.py`、`add_confirm_availability_state.py`、`add_confirm_approval_state.py`、`add_confirm_context_state.py`、`add_confirm_finalization_state.py`、`add_confirm_job_state.py`、`add_cancel_state.py`、`search_candidate_state.py`。
- 本轮继续把 `search_ambiguity_helper.py` 合并回 `app/services/search_media.py`，删掉单消费者薄壳，focused tests `54 passed, 134 deselected`。
- 当前主线没有改协议、SQLite schema、调度语义、下载/导入/刷新真相边界。
- `cleanup_*_support.py` 仍为 `0` 个；其余大 support 文件暂不机械强拆。
- `cleanup_*_support.py` 当前为 `0` 个。

## Current health
- 历史总 gate 基线：`make quality` -> `27 passed, 0 skipped`。
- 当前总 gate：`make quality` 通过。
- 当前主线验证：`make verify-mainline` 通过。
- 最近 focused tests：
  - `tests/test_add_to_downloader.py` 相关 7 组子集均通过。
  - `tests/test_search_media.py tests/test_search_media_batch_preview_support.py -k "batch_preview or persist_search_candidates or clear_cached_candidates or has_cached_candidates or load_persisted_candidate or search_and_format"` 通过（`124 passed, 64 deselected`）。

## Latest verification
- `make quality` 通过（`27 passed, 0 skipped`）。
- `make verify-mainline` 通过。
- 已通过的关键 focused tests 见上。
- 本轮 focused tests：`tests/test_search_media.py tests/test_search_ambiguity_helper.py -k "ambiguous or search_and_format"` 通过（`54 passed, 134 deselected`）。

## Current biggest risk
- 当前风险不是业务回归，而是 services 层仍有剩余重复结构；下一轮仍需维持“小 diff + focused tests + 文档同步”的节奏，避免重新把 STATUS/NEXT_STEP 写回历史流水账。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线仍是 services 层数据结构降本。优先找剩余单消费者状态壳、重复 parse/display helper 或稳定数据结构收口点；不要重建已删的小文件，不改协议或 SQLite 真相边界。
```
