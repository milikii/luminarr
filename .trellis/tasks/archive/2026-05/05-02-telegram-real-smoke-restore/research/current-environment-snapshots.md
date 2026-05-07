# Current Environment Snapshots

Research dates: 2026-05-02, 2026-05-07

## Goal

Capture the concrete environment blockers before attempting a fresh real Telegram smoke.

## Findings

- Active task created and set to `05-02-telegram-real-smoke-restore`.
- Current working tree was clean before this task, aside from this new task directory.
- No local `python -m app.main` process is currently running.
- `api.telegram.org` remains unreachable from the current shell path during this pass.
- The configured outbound proxy endpoint at `192.168.2.110:7890` is also unreachable from the current shell path.
- Local runtime prerequisites still exist:
  - `.env` exists
  - `.venv` exists
  - `make` exists
  - Telegram token / outbound proxy are configured in `.env`

## Implication

The first blocker for a new real Telegram smoke is environment reachability, not application code. Until either direct access to `api.telegram.org` or the configured outbound proxy path is restored, starting `app.main` is unlikely to produce a fresh successful Telegram ingress trace.

## Next debugging slice

1. Confirm whether general outbound network works at all from this shell.
2. Confirm whether DNS resolution for `api.telegram.org` works.
3. If direct access still fails, fix or replace `OUTBOUND_PROXY_URL`.
4. Only after network is healthy, start local `app.main` and send a real Telegram message.

## Recheck (2026-05-07)

- `getent ahosts api.telegram.org` now resolves both IPv4 and IPv6 addresses, so DNS is no longer the primary blocker.
- Host-network verification still fails on direct Telegram access:
  - `curl -sS -m 10 -o /dev/null -w 'http=%{http_code}' https://api.telegram.org` timed out and returned `http=000`.
- `.env` still contains the `OUTBOUND_PROXY_URL` key, but the current value is empty in this shell path.
- `timeout 25 .venv/bin/python -m app.main` can now start the local runtime far enough to bring up:
  - WeCom webhook
  - Feishu long connection
  - personal WeChat private-chat polling
- During that short run, existing downloader follow-up records still log route-miss noise for historical tasks, but that is separate from the Telegram ingress blocker.

## Updated implication

The primary blocker has narrowed from "network and process are both down" to "the local app can run, but the host still lacks a working outbound path to `api.telegram.org`." A fresh real Telegram smoke still cannot be completed until direct Telegram access or a replacement proxy path is restored.

## Updated next debugging slice

1. Restore a working outbound path to `api.telegram.org` (direct reachability or a valid `OUTBOUND_PROXY_URL`).
2. Keep local `app.main` running after network recovery instead of using a short timeout probe.
3. Send a real Telegram message to the bot and capture the fresh ingress/runtime evidence.

## Recheck (2026-05-07, proxy follow-up)

- The replacement proxy `http://192.168.2.220:7890` is reachable from the host path.
- Telegram Bot API is also reachable through that proxy, but `getMe` currently returns:
  - `{"ok":false,"error_code":404,"description":"Not Found"}`
- Shell inspection shows the immediate reason:
  - `TELEGRAM_BOT_TOKEN` currently expands to an empty value in `.env`
  - token shape probe: `token_len=0`, `has_colon=no`
- A short `OUTBOUND_PROXY_URL=http://192.168.2.220:7890 timeout 25 .venv/bin/python -m app.main` run still starts non-Telegram hosts only; no Telegram host startup evidence appears in the logs during this pass.

## Updated implication (proxy follow-up)

The outbound proxy blocker is now resolved, but the real Telegram smoke remains blocked by configuration truth: the current `.env` does not provide a usable `TELEGRAM_BOT_TOKEN`, so the Telegram host cannot be restored even with a working proxy.

## Updated next debugging slice (proxy follow-up)

1. Restore a non-empty valid `TELEGRAM_BOT_TOKEN` in `.env`.
2. Re-run `getMe` through `http://192.168.2.220:7890` and confirm a `200` response.
3. Start `app.main` with that proxy and capture fresh Telegram ingress evidence.

## Correction (2026-05-07, quoting fix)

- The previous "empty token" conclusion was caused by a shell quoting mistake in the probe command, not by `.env`.
- Corrected probes now confirm:
  - `.env` contains `TELEGRAM_BOT_TOKEN` with non-zero length and the expected `bot_id:secret` shape.
  - Sourcing `.env` in-shell preserves that token correctly.
  - Current `.env` also already provides a non-empty `OUTBOUND_PROXY_URL` (`http://192.168.2.106:10808`).
  - An alternate operator-provided proxy override `http://192.168.2.220:7890` is reachable.
  - `getMe` through that proxy returns HTTP `200` with `ok=true`.
- The environment is no longer blocked on proxy/token reachability. The remaining step is to keep `app.main` running and capture a fresh real Telegram inbound message.

## Real inbound evidence (2026-05-07)

- With `app.main` running and the proxy override active, `logs/trace.log` recorded fresh same-session Telegram ingress:
  - `2026-05-07T14:38:55+08:00` inbound `ping`
  - `2026-05-07T14:38:57+08:00` reply `候选作品：ping ✓`
  - `2026-05-07T14:38:57+08:00` inbound `start`
  - `2026-05-07T14:39:14+08:00` reply `候选作品：start ✓`
- This confirms the current session has restored:
  - Telegram inbound delivery
  - Telegram reply delivery
  - trace persistence for operator-facing evidence

## Updated implication (real inbound evidence)

The environment restoration part of this task is now complete. The remaining evidence gap is narrower: we still need a fresh same-session PT post-selection flow if we want to re-prove the downloader/import half of the Telegram chain, but basic real Telegram ingress is no longer the blocker.

## Real PT post-selection evidence (2026-05-07)

- `logs/trace.log` now records a fresh same-session PT chain:
  - `2026-05-07T15:35:02+08:00` inbound `功夫熊猫`
  - `2026-05-07T15:35:09+08:00` reply `候选作品：功夫熊猫 ✓`
  - `2026-05-07T15:35:15+08:00` inbound `1`
  - `2026-05-07T15:35:21+08:00` reply `【PT资源卡】 a6a75e1b`
  - `2026-05-07T15:35:26+08:00` workflow `approval_pending` for `task_ref=pt-a6a75e1b-15`
  - `2026-05-07T15:35:27+08:00` workflow `confirm_dispatch` + `confirm_finalize` succeeded
  - `2026-05-07T15:40:21+08:00` inbound `status 46b9071551bb3eb905623b8851151d11f4734751`
  - `2026-05-07T15:40:22+08:00` reply `下载状态 ✓`
- Database truth (`job_event`) confirms new same-session backend events for the same hash:
  - `2026-05-07 07:35:27` `downloader.succeeded`
  - `2026-05-07 07:35:32` `downloader.completed_observed`
- `download_monitor` currently shows the same hash at `task_id=20`, `status_code=6`, `percent_done=1.0`, `is_complete=1`.

## Updated implication (PT post-selection evidence)

This task now has current-session real evidence for:
- Telegram inbound
- candidate resolution
- PT resource card delivery
- downloader dispatch
- user-visible completed status reply

What is still missing is a fresh same-session import/post-processing tail. The selected title reused an already-known hash (`46b907...`), and no new `import.*`, `metadata.*`, `subtitle.*`, or `refresh.*` events were created after the new `2026-05-07 15:35` dispatch.

## Fresh-hash PT evidence (2026-05-07)

- A second same-session PT chain now proves the "new hash" path rather than a reused historical one:
  - `2026-05-07T15:54:22+08:00` inbound `超人`
  - `2026-05-07T15:54:28+08:00` reply `候选作品：超人 ✓`
  - `2026-05-07T15:54:47+08:00` inbound `3`
  - `2026-05-07T15:54:56+08:00` reply `【PT资源卡】 3d9006a4`
  - `2026-05-07T15:56:09+08:00` inbound `14`
  - `2026-05-07T15:56:12+08:00` workflow `confirm_dispatch` + `confirm_finalize` succeeded
  - `2026-05-07T15:56:14+08:00` reply `已添加下载：Superman 2025 BluRay 1080p x265 10bit DDP7.1 MNHD-FRDS`
  - `2026-05-07T15:57:58+08:00` inbound `status 52bde7a5544843b7088c9181d7452a34efd4c07c`
  - `2026-05-07T15:57:58+08:00` reply `下载状态 ⏳`
- Database truth confirms this hash is new in the current session:
  - `job_event`: `media.identity.confirmed`, `downloader.succeeded`
  - `download_monitor`: `task_id=21`, `status_code=4`, `percent_done≈0.00447`, `is_complete=0`

## Updated implication (fresh-hash PT evidence)

The task now has same-session real evidence for both:
- a reused-hash path that reached `下载状态 ✓`
- a fresh-hash path that reached `已添加下载` and `下载状态 ⏳`

The remaining evidence gap is now very specific: wait for the fresh hash `52bde7...` to complete and then capture whether the same session produces new `import.*`, `metadata.*`, `subtitle.*`, and `refresh.*` events.

## Restart verification (2026-05-07)

- Before restart, fresh hash `52bde7...` had:
  - `percent_done≈0.03381`
  - `telegram_progress_last_synced_at=2026-05-07 08:26:18`
  - Telegram progress text showing `下载进度：3%`
- After restarting `app.main` with the fix applied, the same persisted card resumed syncing:
  - `telegram_progress_last_synced_at=2026-05-07 08:27:57`
  - then advanced again to `2026-05-07 08:28:10`
  - `percent_done` increased to `≈0.03586`
  - persisted Telegram progress text updated to `下载进度：4%`, with changed speed / ETA text

## Updated implication (restart verification)

This confirms the restart regression is fixed for live-progress cards: an unfinished Telegram download card now resumes progress synchronization after `app.main` restarts instead of freezing at the pre-restart state.
