# Luminarr AGENTS.md (v15)

This file is the operating contract for AI coding agents working in this repository.

## Document priority

When files disagree, follow this order:

1. `docs/DECISIONS.md`
2. `docs/NEXT_STEP.md`
3. `docs/STATUS.md`
4. `README.md`
5. `AGENTS.md`

Do not invent a third interpretation. If two files conflict, update the lower-priority file.

## Project goal

Luminarr is a narrow vertical media automation harness for 2–4 self-hosted users.

Current fixed runtime profile:
- Telegram private chat only
- TMDB only
- Prowlarr only
- Transmission only
- Emby only
- SQLite only
- Docker Compose only
- single instance / single process / single host
- movie-first workflow

Core responsibilities:
- `search_media`
- `add_to_downloader`
- `get_download_status`
- `import_to_library`
- `refresh_media_server`
- `manage_watchlist` (reserved, not current priority)

## Scope discipline

Do not expand into:
- generic AI assistant behavior
- office automation
- generic agent platform features
- plugin marketplace / MCP platformization
- qBittorrent / Jellyfin / Sonarr / Radarr in the current mainline
- auto-download watchlist in the current mainline

## Current priority

The next development priority is **execution hygiene**, not watchlist:
1. durable Telegram message/callback de-dup
2. durable execution ownership (`jobs.version`, `lease_owner`, `lease_until`)
3. approval-wake context rebuild
4. low-cost frustration/reset short-circuit
5. only after the above, consider watchlist baseline

## Runtime rules

### Model usage
- Parser-first, LLM-fallback.
- Never use the model for idempotency checks.
- Never use the model for lease ownership.
- Never use the model for execution-result truth.
- Never use the model for approval re-validation.
- Background recovery and scheduler ticks must not depend on LLM calls.

### Concurrency
- Read-only tools may be marked concurrency-safe.
- Stateful tools must remain serialized through workflow ownership.
- Same-job side effects must never run concurrently.
- If no lease is held, the side-effect path must exit.

### Approval wake
When a suspended task is resumed by `confirm`, rebuild execution context from persisted truth:
- `system_base`
- `project_rules`
- current `job_context`
- minimal `approval_context`
Do not reuse the old free-form conversation transcript as execution memory.

### Ambiguous search
For highly ambiguous title resolution, an isolated read-only exploration helper is allowed.
It may:
- query TMDB / Prowlarr
- help generate clarification text
It may not:
- mutate main workflow state
- write side-effect approvals
- dispatch downloads
Only the final confirmed structured result may be written back to the main workflow.

### Frustration detector
Use low-cost parser rules for phrases such as:
- 不对
- 停
- 重来
- 换一个
- 算了
- 取消
When triggered in clarification / selection / pending-approval stages, prefer deterministic reset/cancel flows over more LLM turns.

## Engineering conventions

- Python 3.12 style.
- Prefer small explicit functions.
- Prefer minimal dependencies.
- Prefer deterministic text protocols over fancy UI.
- Add tests for every non-trivial change.
- Keep diffs narrow.
- Do not refactor unrelated modules.
- Update docs whenever behavior or rules change.

## High-risk paths

Do not casually modify these without updating docs and calling out the risk:
- persistence schema / migrations
- approval protocol
- lease/version protocol
- recovery scripts
- docker-compose deployment files
- restore / backup scripts
- secrets or token wiring

## Definition of done

A task is done only when:
1. code is complete
2. tests pass
3. manual verification steps are written
4. relevant docs are updated
5. no obvious regression remains
6. document priority is still internally consistent

## Useful commands

- run app: `python -m app.main`
- run tests: `pytest -q`
- format: `python -m black .`
- lint: `python -m ruff check .`
