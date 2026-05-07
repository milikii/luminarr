# Scope Split

## Decision

This feature is intentionally split into two phases.

### Phase A — current task

Only improve the Telegram download-success message presentation:

- better hierarchy
- copy-friendly task id / hash
- cleaner Telegram-specific text card
- downloader identity visible
- a reserved progress section that clearly says live sync comes later

### Phase B — later task

Telegram live progress sync on the same message:

- message id capture
- task_hash -> message tracking truth
- edit_message_text path
- throttling / dedupe / final-state transition

## Why the split exists

Phase A is mostly presentation-layer work.

Phase B is not presentation-only:

- it crosses Telegram transport
- status polling
- download monitor truth
- message lifecycle
- retry / dedupe policy

So Phase B is a distinct system feature, not a small follow-up to a text template.

## Out-of-scope reminder

This task must not:

- add Telegram message editing
- store task/message mapping truth
- change downloader or import workflow semantics
- expand to Feishu / personal WeChat / WeCom
- fake real-time progress values in Phase A
