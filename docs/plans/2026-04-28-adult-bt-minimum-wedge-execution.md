# Adult BT Minimum Wedge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a user-visible adult BT minimum wedge by fixing the docs gate first, then improving adult query entry/results, adult pending download replies, and adult-focused verification without changing SQLite schema or PT/movie-first semantics.

**Architecture:** Reuse the existing adult BT backbone instead of building a new workflow: `BT 成人链` routing, `adult_content_registry`, `AddToDownloaderService`, `PostDownloadAutoImportService`, and `AdultArchiveService`. Keep all changes inside the current BT-only path and docs/verification surfaces, so the diff is bounded and the result is demonstrable in 3-6 days.

**Tech Stack:** Python 3.12, SQLite, python-telegram-bot, httpx, pytest, Makefile, existing BT WebSource adapters, existing adult archive pipeline.

---

## Context Lock

This plan is derived from:

- [2026-04-28-adult-bt-minimum-wedge.md](/home/alex/projects/luminarr/docs/plans/2026-04-28-adult-bt-minimum-wedge.md)

Assumptions for execution:

- Work from a dedicated branch or worktree, not directly on `main`
- Keep the current [AGENTS.md](/home/alex/projects/luminarr/AGENTS.md) changes; do not revert them
- Do not reopen the `services`-wide helper merge campaign during this plan

## What Already Exists

- BT chain routing already supports `观影 PT 链 / BT 成人链 / 纯 BT 下载链`
- Adult content truth already exists in `adult_content_registry`
- Adult download pending / dispatch already records adult content metadata
- Adult archive and retention cleanup already exist in `AdultArchiveService`
- Adult read-only search, helper lookup, and history annotations already exist

## NOT In Scope

- No SQLite schema changes
- No `ExecutionGate` redesign
- No PT mainline changes
- No movie-first import pipeline changes
- No Web UI / desktop client
- No adult BT image cards in this wedge
- No batch page-range crawler / site DSL / generalized BT platformization
- No multi-channel richer reply rollout beyond text improvements
- No additional `services` structural cleanup unless strictly required to ship this wedge

## Dependency Map

```text
Task 1: docs gate recovery
    |
    v
Task 2: adult query entry + read-only reply polish
    |
    v
Task 3: adult pending reply + history carry-through
    |
    v
Task 4: adult-focused verification target + operator docs
```

Implementation should stay sequential. All tasks touch shared docs or the same adult BT flow and are not worth parallelizing in the same workspace.

---

### Task 1: Restore Docs Gate Budget

**Files:**
- Move: `docs/DEPLOY_CHECKLIST.md` -> `archive/docs/DEPLOY_CHECKLIST.md`
- Move: `docs/BT_SCORING_RULES.md` -> `archive/docs/BT_SCORING_RULES.md`
- Modify: `docs/GETTING_STARTED.md`
- Test: `tests/test_cleanup_docs_consistency.py`

- [x] **Step 1: Run the failing docs gate first**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py -k "active_docs_root_stays_small_and_current"
```

Expected: FAIL because `docs/*.md` count is `17` and the gate requires `<= 15`.

- [x] **Step 2: Move the two non-core active docs out of the root docs directory**

Run:

```bash
git mv docs/DEPLOY_CHECKLIST.md archive/docs/DEPLOY_CHECKLIST.md
git mv docs/BT_SCORING_RULES.md archive/docs/BT_SCORING_RULES.md
```

Why these two:

- `DEPLOY_CHECKLIST.md` is useful, but it is an operator convenience sheet, not current execution truth
- `BT_SCORING_RULES.md` is a tuning explainer, not a top-level project entrypoint

- [x] **Step 3: Update the remaining user-facing reference to the deploy checklist**

Replace the current line in [docs/GETTING_STARTED.md](/home/alex/projects/luminarr/docs/GETTING_STARTED.md) that says:

```markdown
如果你只想走最短路径，不要在这里重复抄配置清单，直接看 `docs/DEPLOY_CHECKLIST.md` 的 `Phase 0-3`，再按 `.env.example` 分组填值。
```

with:

```markdown
如果你只想走最短路径，不要在这里重复抄配置清单，直接按 `.env.example` 的分组填写最小必填项；旧的部署速查表已经归档到 `archive/docs/DEPLOY_CHECKLIST.md`。
```

- [x] **Step 4: Re-run the docs gate**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py
```

Expected: PASS.

- [x] **Step 5: Re-run the repository quality gate**

Run:

```bash
make quality
```

Expected: PASS.

- [x] **Step 6: Commit the docs-gate recovery**

```bash
git add archive/docs/DEPLOY_CHECKLIST.md archive/docs/BT_SCORING_RULES.md docs/GETTING_STARTED.md
git commit -m "docs: restore active docs gate budget"
```

---

### Task 2: Add an Explicit Adult Query Entry and Improve Read-Only Replies

**Files:**
- Modify: `app/bot/query_text_runtime.py`
- Modify: `app/services/search_reply_formatter.py`
- Test: `tests/test_query_text_runtime.py`
- Test: `tests/test_search_media.py`

- [x] **Step 1: Add a failing parser test for the new adult query alias**

Add this assertion to [tests/test_query_text_runtime.py](/home/alex/projects/luminarr/tests/test_query_text_runtime.py):

```python
assert extract_bt_read_only_query("成人搜 SSIS-123") == "SSIS-123"
```

Run:

```bash
.venv/bin/python -m pytest -q tests/test_query_text_runtime.py -k extract_bt_read_only_query
```

Expected: FAIL because `成人搜` is not currently recognized.

- [x] **Step 2: Implement the explicit adult read-only alias**

Update [app/bot/query_text_runtime.py](/home/alex/projects/luminarr/app/bot/query_text_runtime.py):

```python
BT_READ_ONLY_PREFIXES = ("bt搜 ", "bt search ", "成人搜 ")
```

Do not remove existing `bt搜` behavior.

- [x] **Step 3: Add a failing formatter test for helper detail URL visibility**

In [tests/test_search_media.py](/home/alex/projects/luminarr/tests/test_search_media.py), extend the existing helper-summary scenario so the rendered text must include:

```python
assert "只读详情: https://www.javlibrary.com/tw/?v=javli0001" in text
```

Run:

```bash
.venv/bin/python -m pytest -q tests/test_search_media.py -k "javlibrary_helper_summary or helper_for_history_lookup"
```

Expected: FAIL because the detail URL is currently stored but not shown to the user.

- [x] **Step 4: Surface helper detail URLs and a clearer adult-only notice**

Update [app/services/search_reply_formatter.py](/home/alex/projects/luminarr/app/services/search_reply_formatter.py):

1. Add a small formatter helper:

```python
def format_read_only_adult_detail_url(item: Mapping[str, Any]) -> str:
    return safe_text(item.get("read_only_adult_detail_url"), default="")
```

2. In both `format_bt_read_only_reply()` and `format_bt_batch_preview_reply()`, append:

```python
detail_url = format_read_only_adult_detail_url(item)
if detail_url:
    lines.append(f"   只读详情: {detail_url}")
```

3. Replace `BT_READ_ONLY_NOTICE_TEXT` with:

```python
BT_READ_ONLY_NOTICE_TEXT = (
    "只读说明：当前结果仅供手动 BT 探索和站点规则排查参考，不会创建审批或下载任务。\n"
    "如需走成人下载链，请直接发送磁力并选择 BT 成人链。"
)
```

- [x] **Step 5: Run the focused read-only tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_query_text_runtime.py tests/test_search_media.py -k "成人搜 or bt_read_only or javlibrary"
```

Expected: PASS.

- [x] **Step 6: Commit the adult query/reply improvements**

```bash
git add app/bot/query_text_runtime.py app/services/search_reply_formatter.py tests/test_query_text_runtime.py tests/test_search_media.py
git commit -m "feat: add explicit adult search alias and richer read-only reply"
```

---

### Task 3: Carry Adult History into Pending Download Replies

**Files:**
- Modify: `app/services/add_pending_context.py`
- Modify: `app/services/add_to_downloader.py`
- Test: `tests/test_add_pending_context.py`
- Test: `tests/test_add_to_downloader.py`

- [x] **Step 1: Add a failing builder test for adult history lookup**

Add a new test to [tests/test_add_pending_context.py](/home/alex/projects/luminarr/tests/test_add_pending_context.py) that:

1. Creates a temporary SQLite database
2. Writes an `archived_present` row for `censored:ssis-123`
3. Builds a pending context from a direct magnet source titled `SSIS-123`
4. Asserts:

```python
assert result.pending_add is not None
assert result.pending_add.adult_history_text.startswith("历史: 该番号已归档保留：")
```

Run:

```bash
.venv/bin/python -m pytest -q tests/test_add_pending_context.py -k adult_history
```

Expected: FAIL because `build_from_source()` does not currently populate `adult_history_text`.

- [x] **Step 2: Extend `AddPendingContextBuilder` with optional registry-backed history lookup**

Update [app/services/add_pending_context.py](/home/alex/projects/luminarr/app/services/add_pending_context.py):

1. Extend the constructor:

```python
class AddPendingContextBuilder:
    def __init__(
        self,
        search_service: SearchMediaService,
        adult_content_registry_repo: AdultContentRegistryRepo | None = None,
    ) -> None:
        self._search_service = search_service
        self._adult_content_registry_repo = adult_content_registry_repo
```

2. Add a helper that loads an existing adult history string:

```python
def _resolve_adult_history_text(self, *, content_id: str) -> str:
    ...
```

Use:

- `AdultContentRegistryRepo.get_by_content_id()`
- `build_adult_history_text()` from `app.services.bt_read_only_display`
- fail-open logging only; never break pending creation because of a history lookup problem

3. Call that helper from:

- `build_from_selection()` when `adult_history_text` is empty but `adult_content_id` exists
- `build_from_source()` when an exact adult ID is found

- [x] **Step 3: Pass the registry repo into the pending context builder**

Update [app/services/add_to_downloader.py](/home/alex/projects/luminarr/app/services/add_to_downloader.py):

```python
self._pending_context_builder = AddPendingContextBuilder(
    search_service,
    adult_content_registry_repo=adult_content_registry_repo,
)
```

- [x] **Step 4: Add a failing reply-level test, then make it pass**

Add a new test to [tests/test_add_to_downloader.py](/home/alex/projects/luminarr/tests/test_add_to_downloader.py) that constructs a service with an existing adult registry record and asserts the pending reply now includes:

```python
"历史: 该番号已归档保留："
```

Run:

```bash
.venv/bin/python -m pytest -q tests/test_add_pending_context.py tests/test_add_to_downloader.py -k "adult_history or adult_pending"
```

Expected before the implementation is complete: FAIL.  
Expected after the implementation: PASS.

- [x] **Step 5: Run the focused pending/download tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_add_pending_context.py tests/test_add_to_downloader.py tests/test_private_chat_runtime.py -k "adult or BT 成人链"
```

Expected: PASS.

- [x] **Step 6: Commit the adult pending-history carry-through**

```bash
git add app/services/add_pending_context.py app/services/add_to_downloader.py tests/test_add_pending_context.py tests/test_add_to_downloader.py
git commit -m "feat: surface adult history in pending download replies"
```

---

### Task 4: Add an Adult-BT Focused Verification Entry Point

**Files:**
- Modify: `Makefile`
- Modify: `tests/test_makefile.py`
- Modify: `docs/GETTING_STARTED.md`

- [x] **Step 1: Add a dedicated Makefile target for this wedge**

Update [Makefile](/home/alex/projects/luminarr/Makefile) with a new target and help entry:

```makefile
.PHONY: verify-adult-bt-wedge
```

Add to `help` output:

```makefile
verify-adult-bt-wedge
```

Add the target:

```makefile
verify-adult-bt-wedge:
	$(PYTHON) -m pytest -q tests/test_query_text_runtime.py tests/test_bt_read_only_display.py tests/test_search_media.py
	$(PYTHON) -m pytest -q tests/test_add_pending_context.py tests/test_add_to_downloader.py tests/test_private_chat_runtime.py
	$(PYTHON) -m pytest -q tests/test_adult_archive_service.py tests/test_get_download_status.py
```

Use full test files instead of fragile `-k` filters for this target.

- [x] **Step 2: Update the Makefile tests**

Add assertions to [tests/test_makefile.py](/home/alex/projects/luminarr/tests/test_makefile.py) for:

1. `verify-adult-bt-wedge` appearing in help text
2. The target recipe matching the three exact commands above

Run:

```bash
.venv/bin/python -m pytest -q tests/test_makefile.py -k adult_bt_wedge
```

Expected: FAIL before the target/test exists, then PASS after implementation.

- [x] **Step 3: Add one operator-facing adult BT verification section**

Append a short section to [docs/GETTING_STARTED.md](/home/alex/projects/luminarr/docs/GETTING_STARTED.md):

```markdown
## 成人 BT focused 验证

先跑：

`make verify-adult-bt-wedge`

最小人工路径：

1. 发送 `成人搜 SSIS-123`
2. 确认结果里能看到番号、来源、历史状态
3. 发送磁力并选择 `BT 成人链`
4. 确认待下载回复里能看到番号、分类、历史状态
```

Do not add a long tutorial here. Keep it short and operator-oriented.

- [x] **Step 4: Run the focused verification target and full quality gate**

Run:

```bash
make verify-adult-bt-wedge
make quality
make verify-mainline
```

Expected: PASS.

- [x] **Step 5: Commit the adult-BT verification entry point**

```bash
git add Makefile tests/test_makefile.py docs/GETTING_STARTED.md
git commit -m "chore: add adult BT focused verification target"
```

---

## Final Verification

- [x] Run the full wedge verification:

```bash
make verify-adult-bt-wedge
```

- [x] Run repository gates:

```bash
make quality
make verify-mainline
```

- [x] Confirm the docs gate is still green:

```bash
.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py
```

- [x] Confirm the active docs root count is now within budget:

```bash
python3 - <<'PY'
from pathlib import Path
active_docs = sorted(
    path.name
    for path in Path("docs").glob("*.md")
    if path.name not in {"BLOCKERS.md", "PROGRESS.md"}
)
print(len(active_docs))
PY
```

Expected: `15`

当前状态：Final Verification 已通过；Telegram 人工 smoke 正在当前会话进行中。

---

## Manual Smoke Checklist

```text
1. 发送 `成人搜 SSIS-123`
2. 结果里看到：
   - 番号
   - 来源入口
   - 历史状态
   - 只读详情 URL（当 helper 命中时）
3. 发送 magnet:? 链接
4. 回复 `BT 成人链`
5. 待确认回复里看到：
   - 番号
   - 分类
   - 历史状态（若 registry 已有记录）
6. `confirm <task_ref>`
7. 下载完成后通过状态跟进进入归档
8. retention 到期后清理下载器任务与源资源
```

## Execution Handoff

This plan is already the execution plan. Do **not** spend another round re-planning it.

Recommended next step for Superpowers:

1. Use `superpowers:executing-plans`
2. Start with Task 1 immediately
3. Do not widen scope
4. Do not reopen the `services`-wide cleanup campaign
