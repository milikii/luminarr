# Luminarr AGENTS.md (v33)

This file is the repository contract for AI coding agents.

## 1. Communication rules

- Use plain Chinese when explaining architecture or changes.
- No black-box jargon. Explain who sends what data to whom.
- Before modifying a file, explain its role in 1-2 plain Chinese sentences.
- Never fail silently. On operational failure, print explicit colored Chinese logs with a clear fix hint.
- Default user-facing progress reports should be brief and non-technical.
- Per iteration, report only: current task, verification result, changed files, docs updated or not, commit hash / blocker.
- Give detailed logs or deep technical explanation only when failure happens or the user explicitly asks.

## 2. Read Order

### Cold start

在**同一会话的第 1 轮**、第一次真正动代码前，按这个顺序读：

1. `docs/INDEX.md`
2. `docs/ARCHITECTURE.md`
3. `docs/NEXT_STEP.md`
4. `docs/DECISIONS.md`
5. `docs/STATUS.md`
6. `docs/TEST_ENV.md`（only when the task depends on real downloader/import/refresh verification）

### Same-session follow-up rounds

同一会话里的**后续轮次**不要机械重读全文。默认只读：

1. `AGENTS.md`
2. `docs/NEXT_STEP.md` 当前主线相关段落
3. `docs/STATUS.md` 当前快照
4. 与本轮任务直接相关的代码、测试、最近提交

只有在确实需要时才按需读取：

- `docs/DECISIONS.md` 相关边界段落
- `docs/PERSISTENCE_CLOSURE_LOG.md` 当前主线详细闭环
- `docs/CLEANUP_VERIFICATION_WINDOW.md` cleanup 已完成窗口证据
- `docs/TEST_ENV.md` 真实 downloader / import / refresh 联调规则

## 3. Environment

- Host OS: Windows
- Dev shell: WSL Ubuntu
- Interaction mode: Codex CLI in pure terminal
- Repo path: inside WSL filesystem

## 4. Local integration test stack

Use the WSL Docker test stack for real downloader/import/refresh verification when the task depends on:
- hardlink execution
- Transmission RPC dispatch
- Emby refresh API behavior

Services:
- Transmission: `http://127.0.0.1:19091`
- Emby: `http://127.0.0.1:18096`

Read `docs/TEST_ENV.md` before touching these paths.

## 5. CLI rules

- No heredoc or multiline commands in user-facing instructions.
- Use single-line commands.
- Put temporary validation scripts only in `tmp_tests/`.
- If a task needs manual verification, provide a one-line command.
- Wrap executable commands in standard ` ```bash ` blocks.

## 6. Document priority

When docs disagree, follow:
1. `docs/DECISIONS.md`
2. `docs/NEXT_STEP.md`
3. `docs/STATUS.md`
4. `README.md`
5. `AGENTS.md`

`docs/HISTORY.md` is background only. Do not use it as the source of current execution truth.

## 7. Project scope

Current mainline profile:
- Telegram + personal WeChat + Feishu + WeCom（当前为最小私聊文本基线）
- TMDB
- Prowlarr（current main source） + minimal BT WebSource（BT-only）
- Transmission + qBittorrent
- Emby / Jellyfin / Plex（按配置选择 refresh provider）
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
- `manage_bt_subscription`

Do not expand into:
- generic AI assistant behavior
- generic agent platform features
- generic plugin / skill / MCP platformization
- Jellyfin / Plex full media-management parity or auto-detection in the current step
- auto-download watchlist in the current mainline

Roadmap items that stay out of scope until `docs/NEXT_STEP.md` promotes them:
- downloader/library asset cleanup automation

## 8. Current priority

当前进行中的 promoted 主线是 **BT 更多 allowlist 页面类型再评估**。2026-04-19 本会话已确认：更早一条 **BT 用户页 / 编号范围页能力** 主线满足退出条件并保持完成态；本批次随后补齐了首页翻页页 `https://nyaa.si/?p=2` 与排序列表页 `https://nyaa.si/?s=seeders&o=desc`，当前更保守的下一步只剩“是否还值得继续扩更多 allowlist 页面类型”的再评估。上一条 **Plex 真实 refresh smoke 值得性重评估** 主线也已满足退出条件，本机 `http://127.0.0.1:32400/identity` 返回 `000`，当前批次暂不继续追 Plex 实例；再上一条 **Jellyfin / Plex 真实联调重评估** 主线保持完成态，provider 缺配置时的静默关闭 refresh 已收口；更早一条 **Jellyfin 单 provider 真实 refresh smoke** 也已通过真实失败探针收口，失败点可直接定位到 `provider + target + request_url`。当前主线蓝图继续看 `docs/BT_PAGE_RANGE_PLAN.md`；刚完成的 Plex 评估蓝图继续看 `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md`；再上一条 Jellyfin smoke 蓝图继续看 `docs/JELLYFIN_REAL_VERIFICATION_PLAN.md`；更早一条 **BT 批量任务显式批量确认** 蓝图继续看 `docs/BT_BATCH_PLAN.md`；更早的 PT live seeding 蓝图入口继续看 `docs/PT_LIVE_SEEDING_PLAN.md`；`.ass` 详细闭环入口继续看 `docs/SERIES_ANIME_NAMING_LOG.md` 2.3；已完成闭环入口继续看 `docs/JELLYFIN_PLEX_PLAN.md`、`docs/BT_SCORING_LOG.md`、`docs/QUICK_START_PLAN.md`、`docs/DEPLOY_CHECKLIST.md`、`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md` 与 `docs/CLEANUP_VERIFICATION_WINDOW.md`。

**诊断分流递减自检**：若本轮候选闭环的代码变更 < 20 行、只是对同一个 repo 方法再拆一条 `if/elif/log` 诊断分支，且上一轮也是同类微闭环，则视为收益递减；本轮完成并提交后**直接停止**，把"当前主线可宣告完成"汇报给用户，不要自动进入下一轮再拆一条分流。

## 9. Runtime rules

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

## 10. Engineering conventions

- Python 3.12 style.
- Prefer small explicit functions.
- Prefer deterministic text protocols over fancy UI.
- Keep diffs narrow.
- Do not refactor unrelated modules.
- Update docs whenever behavior or rules change.
- **瘦身 commit 必须顺手清掉对应被拆文件的 pyflakes 未用 import**；不单独开 commit、不单独开主线。具体纪律见 `docs/SLIMMING_RULES.md`。

## 11. Task protocol

- Identify the smallest reasonable closed loop from `docs/NEXT_STEP.md` and current codebase state.
- Work on one small task at a time; do not bundle unrelated cleanup or refactors.
- Prefer reusing existing tests and scripts; only create `tmp_tests/` files when necessary.
- Run verification yourself; do not stop at “here is the command”.
- After implementation, review the diff for scope creep, debug leftovers, and temporary files.
- If behavior, rules, or entrypoints changed, update the relevant docs in the same turn.
- **诊断分流递减停机规则**：本轮代码变更 `< 20 行` 且只是为同一个 repo 方法追加 `if/elif/log` 诊断分支时，视为收益递减。本轮完成并提交后**直接停止**并请用户确认是否宣告当前主线完成、切换到 `After this step` 第 1 项；不要自动连续第 2/3 轮再拆一条分流。
- 同一会话默认最多连续推进 10 轮；到第 10 轮结束后，下一次继续施工时应新开会话，不要把第 11 轮继续叠在旧线程里。
- 长会话重开时，优先用“最新 commit hash + 1 段当前快照 + 1 段当前主线详细闭环”做交接，不要把整段历史对话当执行上下文。

## 12. High-risk paths

Do not casually modify these without updating docs and calling out the risk:
- persistence schema / migrations
- approval protocol
- lease/version protocol
- recovery scripts
- docker-compose deployment files
- restore / backup scripts
- secrets or token wiring

## 13. Definition of done

A task is done only when:
1. code or docs are complete
2. if verification is needed, a `tmp_tests/` script is created
3. manual verification succeeds
4. relevant docs are updated
5. temporary validation scripts are deleted
6. no obvious regression remains
7. document priority is still internally consistent
