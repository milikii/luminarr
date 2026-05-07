# Phase B Boundary

## Scope

This task is Phase B only:

- Telegram-only live progress sync
- edit the original download-success message in place
- use real progress / speed / ETA

## Required new capability

Phase B is allowed to add:

- Telegram message id tracking
- minimal persistent mapping between task identity and Telegram message identity
- edit-message transport capability
- throttling / dedupe for progress refresh

## Out of scope

This task must not:

- redesign downloader/import workflow semantics
- expand to Feishu / personal WeChat / WeCom
- build a generic cross-channel live progress platform
- fake progress values

## Quality bar

The implementation must preserve:

- Telegram-first current behavior
- existing auto-confirm / auto-import truth
- no regression in PT resource card callback path
