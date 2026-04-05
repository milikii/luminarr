# Luminarr AGENTS.md (v27)

This file is the repository contract for AI coding agents.

## 1. Communication rules

- Use plain Chinese when explaining architecture or changes.
- No black-box jargon. Explain who sends what data to whom.
- Before modifying a file, explain its role in 1-2 plain Chinese sentences.
- Never fail silently. On operational failure, print explicit colored Chinese logs with a clear fix hint.

## 2. Environment

- Host OS: Windows
- Dev shell: WSL Ubuntu
- Interaction mode: Codex CLI in pure terminal
- Repo path: inside WSL filesystem

## 3. Local integration test stack

Use the WSL Docker test stack for real downloader/import/refresh verification when the task depends on:
- hardlink execution
- Transmission RPC dispatch
- Emby refresh API behavior

Services:
- Transmission: `http://127.0.0.1:19091`
- Emby: `http://127.0.0.1:18096`

Read `docs/TEST_ENV.md` before touching these paths.

## 4. CLI rules

- No heredoc or multiline commands in user-facing instructions.
- Use single-line commands.
- Put temporary validation scripts only in `tmp_tests/`.
- If a task needs manual verification, provide a one-line command.
- Wrap executable commands in standard ` ```bash ` blocks.

## 5. Document priority

When docs disagree, follow:
1. `docs/DECISIONS.md`
2. `docs/NEXT_STEP.md`
3. `docs/STATUS.md`
4. `README.md`
5. `AGENTS.md`

`docs/HISTORY.md` is background only. Do not use it as the source of current execution truth.

## 6. Project scope

Current mainline profile:
- Telegram + Feishu（当前为最小私聊文本基线）
- TMDB
- Prowlarr（current main source） + minimal BT WebSource（BT-only）
- Transmission + qBittorrent
- Emby
- SQLite
- Docker Compose
- single instance / single process / single host
- movie-first workflow

Core responsibilities:
- `search_media`
- `add_to_downloader`
- `get_download_status`
- `import_to_library`
- `refresh_media_server`
- `manage_watchlist`

Do not expand into:
- generic AI assistant behavior
- generic agent platform features
- generic plugin / skill / MCP platformization
- Jellyfin / Plex mainline support in the current step
- auto-download watchlist in the current mainline

Roadmap items that stay out of scope until `docs/NEXT_STEP.md` promotes them:
- WeCom / personal WeChat adapters
- downloader/library asset cleanup automation

## 7. Current priority

The current next smallest path is:

- **WeCom private-chat identity projection + text event adapter baseline**

Keep these landed baselines stable while doing it:
- execution hygiene (`telegram_updates`, `jobs`, confirm wake rebuild)
- shared private-chat text runtime + Feishu 最小 webhook 请求入口 / 文本回消息 / 签名校验
- downloader/import approval boundaries
- copy fallback approval
- completion-monitor + post-download auto import
- metadata scraping + subtitle auto-translation
- PT / BT split + BT follow-up chain
- downloader role binding + qBittorrent protocol
- BT subscription scheduler tick
- pure BT single-item ranking baseline
- BT external web-source baseline
- BT WebSource richer metadata extraction baseline
- BT-only read-only helper baseline

## 8. Runtime rules

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
- `confirm` must rebuild execution context from persisted truth.
- Do not reuse old free-form conversation transcript as execution memory.

### BT boundary
- direct `magnet:?` requests currently ask which downstream path to use (`media-import` vs `pure-bt`), but they still stay inside the BT envelope.
- pure BT path currently has a minimum single-item ranking baseline, and may later add LLM-assisted preference after deterministic pre-filtering.
- BT 当前已可接 deterministic external website sources, but PT main path must stay unchanged.
- BT may later add a BT-only read-only helper.
- That helper may not write workflow truth, mutate approvals/jobs, dispatch downloads, or trigger import side effects.
- Scheduler ticks and automatic recovery must not depend on that helper.

## 9. Engineering conventions

- Python 3.12 style.
- Prefer small explicit functions.
- Prefer deterministic text protocols over fancy UI.
- Keep diffs narrow.
- Do not refactor unrelated modules.
- Update docs whenever behavior or rules change.

## 10. High-risk paths

Do not casually modify these without updating docs and calling out the risk:
- persistence schema / migrations
- approval protocol
- lease/version protocol
- recovery scripts
- docker-compose deployment files
- restore / backup scripts
- secrets or token wiring

## 11. Definition of done

A task is done only when:
1. code or docs are complete
2. if verification is needed, a `tmp_tests/` script is created
3. manual verification succeeds
4. relevant docs are updated
5. temporary validation scripts are deleted
6. no obvious regression remains
7. document priority is still internally consistent
