# Quality Guidelines

> Code quality standards for backend development.

## Scenario: Stage 1 Verification Entry Point

### 1. Scope / Trigger

- Trigger: T19 introduced a single Stage 1 verification entry point and synced operator-facing docs to that truth.
- Why code-spec depth is required: this is a new command-level contract spanning `Makefile`, docs gates, and release-time verification behavior.

### 2. Signatures

- `make verify-stage1`
- `make verify-stage1-duplicate-memory`
- `make verify-stage1-telegram-delivery`
- `make verify-stage1-bt-source-roles`

### 3. Contracts

#### Command contract

- `verify-stage1` must remain a pure aggregator target that runs exactly:
  - `verify-stage1-duplicate-memory`
  - `verify-stage1-telegram-delivery`
  - `verify-stage1-bt-source-roles`
- `verify-stage1` is the operator-facing single truth for Stage 1 (`T16` / `T17` / `T18`) focused regression coverage.

#### Documentation contract

- `docs/GETTING_STARTED.md`, `docs/STATUS.md`, `docs/NEXT_STEP.md`, and `docs/OPERATOR_RUNBOOK.md` must all reference `make verify-stage1` consistently.
- `docs/STATUS.md` remains a short snapshot, not a command transcript or long checklist.

#### Evidence contract

- If a fresh real Telegram smoke cannot be produced because runtime/network prerequisites are unavailable, operator docs may record:
  - current environment snapshots
  - existing real trace evidence still available in repo logs
- This fallback must be labeled as equivalent evidence, not as a new real Telegram smoke.

### 4. Validation & Error Matrix

- New Stage 1 regression added but not wired into `verify-stage1` -> docs/tests drift; fix the Makefile target group.
- Docs claim Stage 1 complete but omit `make verify-stage1` -> docs gate failure.
- Docs present equivalent evidence as real smoke -> contract violation; rewrite wording to distinguish them.
- `verify-stage1` becomes a giant flat command list instead of grouped targets -> maintainability regression; restore grouped targets.

### 5. Good/Base/Bad Cases

- Good: operator runs `make verify-stage1` and gets grouped coverage for duplicate memory, Telegram-first delivery, and BT source roles.
- Base: real Telegram smoke unavailable, but docs explicitly record `telegram bot api unreachable`, `no luminarr process running`, and point to retained trace evidence.
- Bad: docs still point operators at an old Stage 1 task name or a scattered set of manual pytest invocations.

### 6. Tests Required

- `tests/test_makefile.py`
  - assert `verify-stage1` points to the three subgroup targets
  - assert each subgroup target points to the intended focused regressions
- `tests/test_cleanup_docs_consistency.py`
  - assert all operator-facing docs mention `make verify-stage1`
  - assert finish-phase wording and Stage 1 completion wording stay aligned

### 7. Wrong vs Correct

#### Wrong

- Add a new focused regression for Stage 1 but only mention it in `docs/GETTING_STARTED.md`.
- Tell operators “Telegram smoke completed” when the only fresh evidence is environment snapshots plus an older trace.

#### Correct

- Wire the regression into the appropriate `verify-stage1-*` target and keep docs pointing at `make verify-stage1`.
- Describe unavailable fresh smoke as equivalent evidence and state the missing runtime/network prerequisites explicitly.
