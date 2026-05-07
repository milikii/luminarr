# Current Timeout Truth

Research date: 2026-05-07

## Goal

Capture the current repository truth for Telegram/PT search timeout behavior before implementation.

## Findings

- The current PT search flow eventually reaches `app/services/search_request_context.py::_search_candidates_with_logging()`.
- `_search_candidates_with_logging()` currently wraps `_search_first_non_empty()` and catches:
  - `httpx.HTTPError`
  - `json.JSONDecodeError`
- On those exceptions, it emits an operational log titled `搜索源查询失败`, then re-raises.
- Because it re-raises immediately, a failure on an early ordered query prevents the rest of `ordered_queries` from being attempted.
- The current log fix hint already treats this as an abnormal source failure rather than a normal empty-result case:
  - `检查 Prowlarr/BT 来源、代理和网络连通性；当前搜索未拿到结果，且这不是正常的“无候选”状态。`
- Existing tests already distinguish helper fail-soft behavior from hard failure elsewhere in the repo:
  - `tests/test_search_media.py::test_search_bt_read_only_and_format_keeps_results_when_javlibrary_lookup_fails`

## Implication

The most likely minimal recovery cut is inside ordered-query search itself: continue trying later queries when an earlier query fails abnormally, but preserve explicit source-failure semantics when all queries fail.
