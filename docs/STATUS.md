# Current status (v543)

## Current mainline
- **质量硬化** 已收工；当前主线是 `services` 层数据结构降本。
- 最近已合并：`add_pending_persistence.py`、`add_request_facade.py`、`add_confirm_preparation.py`、`add_confirm_availability_state.py`、`add_confirm_approval_state.py`、`add_confirm_context_state.py`、`add_confirm_finalization_state.py`、`add_confirm_job_state.py`、`add_cancel_state.py`、`search_candidate_state.py`。
- 本轮继续把 `search_ambiguity_helper.py` 合并回 `app/services/search_media.py`，删掉单消费者薄壳，focused tests `54 passed, 134 deselected`。
- 本轮继续把 `search_clarification_state.py` 合并回 `app/services/search_media.py`，删掉单消费者状态壳，focused tests `62 passed, 123 deselected`。
- 本轮继续把 `search_media_bt_ordering.py` 合并回 `app/services/search_media.py`，删掉单消费者排序壳，focused tests `55 passed, 134 deselected`。
- 本轮继续把 `bt_read_only_helper_selection.py` 合并回 `app/services/bt_read_only_display.py`，删掉单消费者 helper 选择壳，focused tests `10 passed`。
- 本轮继续把 `adult_bt_selector.py` 合并回 `app/services/bt_read_only_display.py`，删掉单消费者成人排序壳，focused tests `18 passed`。
- 本轮继续把 `status_delivery.py` 合并回 `app/services/get_download_status.py`，删掉单消费者状态渲染壳，focused tests `25 passed, 24 deselected`。
- 本轮继续把 `status_follow_up.py` 合并回 `app/services/get_download_status.py`，删掉单消费者状态 follow-up 壳，focused tests `25 passed, 24 deselected`。
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
- 本轮 focused tests：`tests/test_search_media.py -k "clarification or search_and_format"` 通过（`62 passed, 123 deselected`）。
- 本轮 focused tests：`tests/test_search_media.py tests/test_search_media_bt_ordering.py -k "bt_ordering or fallback or search_and_format"` 通过（`55 passed, 134 deselected`）。
- 本轮 focused tests：`tests/test_bt_read_only_display.py tests/test_bt_read_only_helper_selection.py` 通过（`10 passed`）。
- 本轮 focused tests：`tests/test_adult_content.py tests/test_bt_read_only_display.py` 通过（`18 passed`）。
- 本轮 focused tests：`tests/test_get_download_status.py -k "parse_status_query or get_status_text_success or personal_wechat_channel or render_status_reply or download_monitor or completion_event or auto_import_terminal or skip_event"` 通过（`25 passed, 24 deselected`）。
- 本轮 focused tests：`tests/test_get_download_status.py -k "parse_status_query or get_status_text_success or personal_wechat_channel or render_status_reply or download_monitor or completion_event or auto_import_terminal or skip_event"` 通过（`25 passed, 24 deselected`）。

## Current biggest risk
- 当前风险不是业务回归，而是 services 层仍有剩余重复结构；下一轮仍需维持“小 diff + focused tests + 文档同步”的节奏，避免重新把 STATUS/NEXT_STEP 写回历史流水账。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线仍是 services 层数据结构降本。优先找剩余单消费者状态壳、重复 parse/display helper 或稳定数据结构收口点；不要重建已删的小文件，不改协议或 SQLite 真相边界。
```
