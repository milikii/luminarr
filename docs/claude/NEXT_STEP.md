# Next step (v18)

Prerequisite completed:
- `search_media` + index-based select works
- `add_to_downloader` works for Transmission
- `get_download_status` works
- `import_to_library` hardlink flow works
- `import done -> refresh_media_server (Emby only)` is landed
- candidate mapping persistence is landed (SQLite)
- minimal import -> refresh `job_event` persistence is landed
- explicit import approval interaction is landed:
  - `import <id/hash>` enters pending and does not execute side effect
  - `confirm <id/hash>` executes import + refresh
  - duplicate/stale confirm is deterministically rejected
- minimal lease/version replay guard for import confirm is landed
- durable `telegram_updates` truth source is landed for Telegram message de-dup
- minimal `jobs.version + lease_owner + lease_until` truth source is landed for import wake/replay + downloader approval wake/replay ownership
- `confirm <id/hash>` now rebuilds execution context from persisted job + approval truth
- parser-level frustration/reset short-circuit is landed for selection reset + pending downloader/import cancel
- explicit pre-dispatch approval for `add_to_downloader` is now landed:
  - numeric select enters pending approval before Transmission side effects
  - `confirm <id/hash>` deterministically routes to downloader or import approval wake
  - downloader duplicate/stale confirm is deterministically rejected
  - pending downloader approval survives restart via persisted `job + approval_record` truth
- smallest persisted manual watchlist baseline is now landed:
  - `watchlist_item` SQLite persistence
  - deterministic `watchlist` / `想看` add/list/remove/clear command path
  - no auto-download side effects
- smallest approval expiry / timeout policy baseline is now landed:
  - pending downloader/import approval persists timeout truth (`approval_record.expires_at`)
  - `confirm <id/hash>` deterministically rejects expired pending approvals
  - expired pending approvals converge to cancelled truth (`approval_record + jobs`)
- smallest reactive recovery baseline for LLM physical failures is now landed:
  - deterministic physical failure detection (`413`, truncated-style errors)
  - same-turn one-time compact-and-retry
  - final user-safe fallback text instead of surfacing raw physical backend error
- smallest clarification-stage frustration/reset coverage baseline is now landed:
  - no-result clarification pending truth is tracked per chat in-process
  - frustration phrases (`不对/停/重来/换一个/算了/取消`) deterministically short-circuit clarification reset
  - existing pending downloader/import cancel routing remains stable
- smallest read-only concurrency-safe execution policy baseline is now landed:
  - explicit runtime policy marks read-only actions as `concurrency_safe`
  - read-only actions run without side-effect serialization lock
  - side-effect actions remain serialized through the execution gate
  - existing Telegram command behavior and success/failure text bodies remain unchanged
- smallest isolated read-only exploration baseline for ambiguous title resolution is now landed:
  - highly ambiguous no-year queries return deterministic clarification text with read-only options
  - clarification-path does not persist candidate mapping and does not trigger downloader/import side effects
  - numeric select is blocked while clarification is pending

## Goal

Land the smallest **restart-durable clarification pending truth baseline**.

## Scope

Only do:
- keep current search order, poster-card reply, and candidate mapping behavior unchanged
- keep current Telegram command words for `search/select/status/import/confirm/watchlist` unchanged
- keep the landed downloader/import approval flows, `telegram_updates` de-dup, `jobs` ownership, confirm wake rebuild, reset/cancel behavior, and manual watchlist behavior unchanged
- keep the landed clarification-stage frustration/reset behavior unchanged
- keep the landed physical-failure reactive recovery behavior stable
- keep the landed read-only concurrency-safe execution policy behavior stable
- keep the landed ambiguous read-only exploration behavior unchanged
- persist minimal clarification-pending truth so it can survive process restart
- restore/clear clarification-pending truth deterministically with existing reset/cancel routing
- add focused tests/manual verification for clarification durability and no-regression

## Explicit constraints

- do not add new downloader/media server support
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming
- do not introduce Telegram inline keyboard as a requirement for this step
- do not remove existing `import <id/hash>` / `confirm <id/hash>` / `watchlist ...` command paths
- do not change current downloader/import success/failure text bodies
- do not regress the landed execution-hygiene baseline
- do not add global scheduler or multi-process orchestration in this step
- do not broaden into generic multi-agent platform work
- do not broaden clarification persistence into a generic workflow-state platform

## Suggested implementation shape

1. add a smallest persisted clarification truth shape (chat-scoped, no extra side-effect protocols)
2. wire search/no-result clarification set + clear to persisted truth with in-memory fast path preserved
3. keep numeric-select blocking and frustration reset behavior deterministic after restart
4. keep side-effect serialization, lease/approval protocol, physical-failure behavior unchanged
5. add focused tests and manual verification steps

## Done when

- existing downloader/import approval flows do not regress
- existing Telegram command behavior does not regress
- current search/select/add/status/import/confirm/watchlist/refresh chain remains stable
- clarification pending state survives restart with deterministic reset behavior
- ambiguous-query exploration path remains read-only isolated and cannot trigger side effects

## After this step

完成 clarification durability 后，按以下顺序推进（每次只做一个小目标）：

**近期控制层收尾：**
- copy fallback approval（跨文件系统 import 场景）
- scheduler 最小基线（pending task 重试 + 追更轮询前置）

**阶段 B 入口（D-037，优先级最高的下一大步）：**
- 下载完成自动触发入库（移除手动 import confirm）
- 文件规范化重命名（D-042）
- TMDB + Fanart.tv 刮削（D-042）
- 字幕自动翻译（D-041）

以上阶段 B 完成后，再依次推进：阶段 C（追更 D-038 + qBittorrent D-039）→ 阶段 D（渠道扩展 D-040）→ 阶段 E（运维自动化 D-043）。

详见 `README.md` 路线图。

## Integration test reminder

涉及 `import_to_library`、`refresh_media_server`、`add_to_downloader` 端到端的任务，必须用 WSL Docker 本地测试栈验证，不得用 mock。见 `docs/TEST_ENV.md`。

```bash
curl -s http://localhost:9091/transmission/rpc | grep -q "X-Transmission-Session-Id" && echo "TR up" || echo "TR down"
curl -s http://localhost:8096/System/Info/Public | grep -q "ServerName" && echo "Emby up" || echo "Emby down"
```
