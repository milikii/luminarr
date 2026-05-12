# Telegram Candidate Confirmation Contracts

> Executable contracts for Telegram media-candidate confirmation delivery.

## Scenario: Telegram Candidate Confirmation Delivery

### 1. Scope / Trigger

- Trigger: Telegram candidate confirmation must keep the poster-card delivery path instead of collapsing into a first-candidate-only preview plus aggregate HTML text.
- Why code-spec depth is required: this crosses service selection flow, TMDB/fanart enrichment, Telegram formatter/runtime delivery, and channel-specific fallback behavior.

### 2. Signatures

- `app.services.search_media.SearchMediaService.search_and_format(query: str, *, chat_id: int, channel: str = "") -> str`
- `app.services.search_media.SearchMediaService._resolve_confirmation_candidates_for_channel(*, tmdb_candidates: Sequence[TmdbMovie], channel: str | None) -> tuple[TmdbMovie, ...]`
- `app.bot.telegram_reply_formatter.format_telegram_reply(text: str) -> str`
- `app.bot.telegram_update_runtime.build_telegram_reply_func(...) -> Callable[[str], Awaitable[object]]`
- `app.bot.telegram_delivery_runtime.build_telegram_send_media_func(application: Application)`

### 3. Contracts

#### Business-order contract

- Media lookup flow remains:
  1. resolve media candidates
  2. user locks one candidate
  3. only then search resource candidates
- Candidate confirmation must not trigger resource search side effects.
- Resource search remains in the selected-media path, not in Telegram card rendering.

#### Telegram candidate-card contract

- Telegram media candidate confirmation must format into:
  1. header text `【候选作品】 <query>`
  2. candidate count line `候选作品（N 条）`
  3. one candidate block per TMDB candidate
  4. final action lines under `下一步`
- Each candidate block must begin with `【序号】 <b>标题 (年份) | 类型</b>`.
- Candidate detail lines stay card-friendly:
  - `海报: <url>` when poster/fanart exists
  - `<i>原名</i>`
  - `📅 年份`
  - `🎞 类型`
  - `📝 简介`
  - `🌐 TMDB详情`
- Candidate selection remains candidate-first and text-index driven; this contract does not redesign PT resource cards or resource-search ordering.

#### Poster-source contract

- Poster resolution priority for Telegram candidate confirmation cards is:
  1. TMDB poster
  2. fanart poster
- `fanart` enrichment applies only to Telegram candidate-confirmation rendering and must not alter non-Telegram channel output contracts.
- Empty `channel=""` still counts as the default Telegram candidate-confirmation path for poster enrichment.
- If no poster/fanart URL is available, Telegram runtime may generate a placeholder image card; if placeholder generation or media send also fails, that candidate must fall back into text without blocking the rest of the list.

#### Transport contract

- Telegram candidate confirmation prefers per-candidate media delivery:
  1. for each candidate block, send `send_photo` / equivalent Telegram photo reply when media or placeholder media is available
  2. attach a single-candidate inline button `确认作品 N`
  3. after media sends finish, send one final text message containing the header, any candidate blocks that failed media delivery, and the final action lines
- If poster download, placeholder generation, or Telegram photo send fails for one candidate, runtime must fall back only that candidate block into text; it must not collapse the whole confirmation into a first-candidate aggregate message.
- Runtime must preserve HTML formatting in candidate captions and any text fallback blocks.

### 4. Validation & Error Matrix

- Fanart HTTP / auth / proxy failure -> log operational failure, keep candidate visible, use TMDB poster when available, otherwise continue toward placeholder/text fallback.
- TMDB poster missing and no fanart poster -> candidate still remains visible; Telegram may use a placeholder media card or text fallback for that candidate.
- One candidate media send fails but others succeed -> successful cards stay as media, failed candidate reappears in the follow-up text, final action lines stay present.
- Non-Telegram channel rendering -> must keep previous candidate confirmation layout and must not receive Telegram-only fanart/placeholder behavior.

### 5. Good / Base / Bad Cases

- Good: Telegram ambiguous title query returns one poster card per candidate, each card keeps the same candidate number used for later selection, and the final text only carries the header/action summary.
- Base: TMDB poster is missing, fanart returns a poster, and Telegram still sends that candidate as a media card without changing non-Telegram output.
- Base: TMDB and fanart both miss, runtime sends a placeholder card or candidate text fallback while preserving candidate selection.
- Bad: Telegram collapses candidate confirmation into “first candidate poster + aggregate text”.
- Bad: fanart enrichment starts running for WeChat / Feishu / WeCom candidate rendering.
- Bad: resource search executes before candidate selection is confirmed.

### 6. Tests Required

- `tests/test_search_media.py`
  - assert Telegram candidate-confirmation path does not trigger resource search
  - assert default Telegram candidate confirmation can keep more than the old top-5 display cap when relevant candidates are available
  - assert missing TMDB poster can use fanart poster
  - assert default empty `channel` still gets Telegram fanart enrichment
  - assert non-Telegram candidate confirmation layout stays unchanged
- `tests/test_telegram_reply_formatter.py`
  - assert candidate confirmation text formats into `【候选作品】` header plus per-candidate card blocks
  - assert Telegram replies send one poster card per candidate when posters exist
  - assert posterless candidates still get placeholder media or text fallback without changing numbering
  - assert failed candidate media sends reappear in the final text fallback while successful cards stay as media
- `tests/test_telegram_delivery_runtime.py`
  - assert standard Telegram text/media delivery behavior remains valid after candidate-card delivery changes
- `make verify-stage1-telegram-delivery`
  - must stay green after Telegram candidate-card changes

### 7. Wrong vs Correct

#### Wrong

- Collapse candidate confirmation into one preferred-poster card plus aggregate confirmation text.
- Treat `channel=""` as “not Telegram”, causing default Telegram candidate confirmations to skip fanart fallback.
- Move resource search into the rendering path because Telegram now shows richer candidate confirmations.

#### Correct

- Keep one candidate-card flow for Telegram, with one poster/placeholder card per candidate plus a final text message for header, failed blocks, and actions.
- Apply fanart enrichment to the Telegram candidate-confirmation path, including the default empty-channel path.
- Preserve the business order: candidate lock first, resource search second.

## Scenario: Telegram PT Resource Card Delivery

### 1. Scope / Trigger

- Trigger: Telegram PT resource delivery changed from a single poster-caption card with a tiny top-N resource slice into a two-message flow.
- Why code-spec depth is required: this crosses BT result ordering, per-site selection, Telegram media/text transport limits, candidate persistence, and callback-number consistency.

### 2. Signatures

- `app.services.search_media.SearchMediaService.search_resources_for_selected_media(chat_id: int, selection_text: str, *, channel: str | None = None) -> str`
- `app.services.telegram_pt_resource_cards.prepare_telegram_pt_resource_items(*, title: str, year: str, resource_items: Sequence[Mapping[str, Any]], detail_char_limit: int = 4096, per_site_target: int = 6) -> tuple[dict[str, Any], ...]`
- `app.services.telegram_pt_resource_cards.format_telegram_pt_resource_card_caption(*, session: TelegramPtResourceCardSession) -> str`
- `app.services.telegram_pt_resource_cards.format_telegram_pt_resource_detail_message(*, session: TelegramPtResourceCardSession) -> str`
- `app.bot.telegram_update_runtime.build_telegram_reply_func(...) -> Callable[[str], Awaitable[object]]`

### 3. Contracts

#### Business-order contract

- Media lookup flow remains:
  1. user confirms one media candidate
  2. resource search runs for that locked media identity
  3. Telegram returns a PT resource card marker
  4. runtime delivers Telegram-specific PT card output
- PT resource rendering must not skip candidate locking or bypass pending-approval callback flow.

#### Telegram PT resource delivery contract

- Telegram PT resource delivery is a two-message flow:
  1. first message: poster card or text fallback with inline buttons
  2. second message: expanded HTML detail text
- The first message caption must stay compact and must not attempt to dump the full resource list into a `sendPhoto` caption budget.
- The second message must use `sendMessage(parse_mode="HTML")` and stay within Telegram's `4096` character limit.
- The second message numbering must match the inline button numbering exactly.

#### Resource selection contract

- Telegram PT resource path must not reuse the generic `SearchMediaService limit=5` cap before Telegram-specific selection runs.
- Ordered PT resource queries may fail soft: if an earlier query times out or the source errors, runtime must continue trying later queries instead of aborting the whole locked-media search immediately.
- Telegram PT resource selection should:
  - group results by site
  - target up to `6` entries per site
  - prefer coverage across `2160p/4K`, `1440p/2K`, and `1080p` when present
- The selected Telegram PT resources become the persisted `candidate_mapping` truth for that chat, so callback buttons and later selection resolve against the same filtered list.

#### Transport/fallback contract

- If poster media is available and Telegram media send succeeds:
  - first message goes through `send_photo(..., caption=..., reply_markup=...)`
  - second message still sends the expanded detail text
- If poster send fails or no poster exists:
  - first message falls back to `send_message(..., reply_markup=...)`
  - second message still sends the expanded detail text
- Callback payload remains the existing short `ptr:<session>:s:<index>` contract; richer details must not be encoded into callback data.

### 4. Validation & Error Matrix

- Ordered BT results empty -> PT resource card path must not create a fake Telegram session; existing no-result behavior stays authoritative.
- Ordered PT query fails but a later query succeeds -> continue with the later results, emit operational failure logs, and include a partial-timeout hint in the Telegram PT detail message so operators know the resource set may be incomplete.
- All ordered PT queries fail abnormally -> preserve source-failure semantics; do not downgrade the outcome into a normal empty-result reply.
- Telegram PT detail expansion would exceed `4096` -> selector must stop before overflow and keep at least one valid item.
- Poster send fails -> log operational failure, fall back to text first message, still send second detail message.
- New Telegram selection list differs from raw BT ranking count -> persisted `candidate_mapping` and inline buttons must use the Telegram-filtered list, not the raw pre-filter list.

### 5. Good / Base / Bad Cases

- Good: one title returns multiple PT sites; first card stays compact, second message groups `PTP` / `HDB` / `BHD`, and buttons `1..N` match the detailed rows.
- Base: no poster is available; Telegram sends two text messages, with the first carrying buttons and the second carrying details.
- Base: only one site has results; second message still renders grouped details and callback numbering remains correct.
- Bad: first poster caption still only exposes the old top `3` items and hides the rest.
- Bad: second detail message shows items that do not have matching buttons.
- Bad: Telegram PT path is silently truncated by the generic service-level `limit=5` before site-aware selection happens.

### 6. Tests Required

- `tests/test_search_media.py`
  - assert Telegram PT resource path is not capped by the generic service limit before Telegram filtering
  - assert persisted candidate mapping reflects the Telegram-filtered resource set
  - assert ordered-query timeout recovery keeps later PT results and distinguishes partial failure from full source failure
- `tests/test_telegram_pt_resource_cards.py`
  - assert first PT card caption stays short
  - assert second PT detail message is sent
  - assert detail text stays under `4096`
  - assert button numbering matches detailed rows
  - assert partial-timeout hint appears in the Telegram PT detail message when session state carries partial source failure metadata
- `tests/test_telegram_runtime_adapter.py`
  - assert PT callback path still consumes the same candidate that the Telegram button index references
- `make verify-stage1-telegram-delivery`
  - must stay green after Telegram PT resource delivery changes

### 7. Wrong vs Correct

#### Wrong

- Cap PT resource items to the generic service `limit=5` before Telegram-specific grouping runs.
- Put all detailed resource lines back into the poster caption and hope `sendPhoto` accepts it.
- Show richer site-grouped details in message two while leaving inline buttons limited to a different top-3 subset.

#### Correct

- Run Telegram-specific PT resource selection after BT ordering, then persist that filtered set as the chat's resource truth.
- Keep the first Telegram PT card concise and move expanded grouped details into a second HTML text message.
- Ensure both callback buttons and expanded detail rows reference the same filtered, ordered item list.

## Scenario: Ordered Query Timeout Recovery for Search Replies

### 1. Scope / Trigger

- Trigger: ordered BT/PT search now recovers from per-query upstream timeout or decode failure instead of aborting the whole query chain on the first abnormal response.
- Why code-spec depth is required: this crosses ordered query execution, reply rendering, Telegram PT session persistence, and operator-facing abnormal-vs-empty-result semantics.

### 2. Signatures

- `app.services.search_request_context._search_candidates_with_logging(*, search_func: SearchFunc, ordered_queries: Sequence[str], user_query: str) -> _OrderedQuerySearchOutcome`
- `app.services.search_request_context.SearchRequestContext.search_warning_text: str`
- `app.services.search_media.SearchMediaService.search_and_format(query: str, chat_id: int | None = None, *, channel: str | None = None) -> str`
- `app.services.search_media.SearchMediaService.search_resources_for_selected_media(chat_id: int, selection_text: str, *, channel: str | None = None) -> str`
- `app.services.telegram_pt_resource_cards.TelegramPtResourceCardState.create_session(..., partial_failure_hint: str = "") -> TelegramPtResourceCardSession`
- `app.services.telegram_pt_resource_cards.format_telegram_pt_resource_detail_text(..., partial_failure_hint: str = "") -> str`

### 3. Contracts

#### Ordered-query recovery contract

- Ordered BT/PT queries must continue trying later `ordered_queries` entries after a per-query `httpx.HTTPError` or `json.JSONDecodeError`.
- The first later query that returns a non-empty candidate list becomes the resolved result set for ranking and rendering.
- Partial abnormal recovery must attach the stable warning text `提示：部分搜索源超时，结果可能不完整。` through `search_warning_text`.

#### Empty vs abnormal outcome contract

- All ordered queries empty with no abnormal exception -> treat as a normal no-result path.
- Any abnormal query failure followed by a later successful query -> return candidates plus the partial warning; do not escalate to a hard failure.
- All ordered queries abnormal with no successful result -> emit the abnormal-source log and re-raise the last captured exception; do not rewrite this into a no-result reply.

#### Reply transport contract

- Standard search replies must append `search_warning_text` after the normal result body when partial recovery happened.
- Telegram PT resource delivery must persist the same warning via `partial_failure_hint` in the card session and render it in the second detail message, not in callback payloads.
- Telegram PT button numbering, persisted candidate mapping, and site-grouped detail layout must stay unchanged when the warning is present.

#### Logging contract

- Any abnormal ordered-query failure must keep the operational log title `搜索源查询失败`.
- The log detail must retain:
  - original `query`
  - joined `ordered_queries`
  - `resolved_query` when recovery succeeded, otherwise `-`
  - per-query failure details
- Normal all-empty search results must not emit this abnormal-source log.

### 4. Validation & Error Matrix

- First query timeout / HTTP error, later query succeeds -> keep searching, return candidates, append warning, emit abnormal-source log with the successful `resolved_query`.
- All ordered queries timeout / HTTP error / decode failure -> emit abnormal-source log, then re-raise the last abnormal exception.
- All ordered queries empty -> return the existing no-result reply with no warning and no abnormal-source log.
- Telegram PT resource session created after partial recovery -> detail message includes the warning line while button indices and persisted candidates remain aligned.

### 5. Good / Base / Bad Cases

- Good: `Dune 2021` times out, fallback `Dune` returns candidates, and the final reply keeps the results plus the partial-source warning.
- Base: original-title PT query times out, later English-title query resolves results, and the Telegram PT detail message shows the warning before grouped site sections.
- Bad: the first abnormal query aborts the remaining ordered queries.
- Bad: normal empty results are shown with the timeout warning or abnormal-source log.
- Bad: Telegram PT session keeps the recovered resource items but drops the warning before the detail message is sent.

### 6. Tests Required

- `tests/test_search_media.py`
  - `test_search_and_format_keeps_results_when_first_ordered_query_times_out`
  - `test_search_resources_for_selected_media_telegram_path_keeps_results_after_partial_timeout`
  - `test_search_resources_for_selected_media_raises_when_all_ordered_queries_fail`
  - `test_search_resources_for_selected_media_normal_empty_results_do_not_log_timeout`
- `tests/test_telegram_pt_resource_cards.py`
  - `test_build_telegram_reply_func_includes_partial_timeout_hint_in_detail_message`

### 7. Wrong vs Correct

#### Wrong

- Re-raise the first ordered-query timeout immediately and skip later fallback queries.
- Swallow all abnormal query failures and pretend the final result was a normal empty search.
- Append the partial warning to plain-text replies but drop it when building the Telegram PT resource-card session.

#### Correct

- Continue ordered-query execution after per-query abnormal failures and only stop early on the first non-empty result set.
- Keep three distinct outcomes: normal empty, partial abnormal recovery, and full abnormal failure.
- Carry the same partial warning text from ordered-query recovery into every user-visible reply surface that consumed the recovered result set.

## Scenario: Telegram Download Success Live Progress Sync

### 1. Scope / Trigger

- Trigger: Telegram download-success delivery was upgraded from a static success card into a same-message live progress sync flow with a character-based progress bar.
- Why code-spec depth is required: this crosses Telegram send/edit transport, download-monitor persistence, background polling cadence, and channel-specific rendering contracts.

### 2. Signatures

- `app.bot.telegram_delivery_runtime.build_telegram_edit_text_func(application: Application)`
- `app.bot.telegram_update_runtime.build_telegram_reply_func(...) -> Callable[[str], Awaitable[object]]`
- `app.services.get_download_status.GetDownloadStatusService.get_status_text(task_ref: str, *, chat_id: int | None = None, channel: str | None = None) -> str`
- `app.services.get_download_status.render_telegram_live_progress_reply(*, task_ref: str, task_status: TransmissionTaskStatus, auto_import_text: str | None) -> str`
- `app.bot.download_follow_up_runtime.poll_pending_download_completion_once(*, download_monitor_repo: DownloadMonitorRepo, status_service: GetDownloadStatusService, telegram_edit_message_func=None, min_telegram_progress_edit_interval_seconds: float = 300.0) -> None`
- `app.db.download_monitor_repo.DownloadMonitorRepo.bind_telegram_message(*, task_id: str, task_hash: str, message_id: int) -> None`
- `app.db.download_monitor_repo.DownloadMonitorRepo.record_telegram_progress_sync(*, task_id: str, task_hash: str, text: str) -> None`

### 3. Contracts

#### Telegram success-card binding contract

- Telegram add-success delivery must prefer the shared `send_text_func` path when `chat_id` is available, so the returned Telegram `message_id` can be captured.
- Runtime must parse the original add-success payload for `任务 ID` and `任务 Hash`, then bind the returned Telegram `message_id` onto the matching `download_monitor` row.
- The initial success card must tell the operator that the same message will continue to refresh with real progress, not that progress is placeholder-only.

#### Download-monitor persistence contract

- `download_monitor` now owns Telegram live-progress truth fields:
  - `telegram_message_id`
  - `telegram_progress_last_text`
  - `telegram_progress_last_synced_at`
- These fields must be migration-safe for existing SQLite databases by `ALTER TABLE` fallback in `app.db.sqlite`.
- Binding a Telegram message must reset the stored progress-sync text/timestamp so the first real background refresh is not deduped away.

#### Live-progress rendering contract

- `channel="telegram_live_progress"` is a Telegram-only rendering branch; non-Telegram channels must keep their existing status-delivery format.
- Telegram live-progress card must include, at minimum:
  - task id
  - task hash
  - status label
  - character-based progress bar
  - exact percentage
  - download speed
  - ETA
- The progress bar is presentation-only; real progress truth remains the downloader percentage stored on `TransmissionTaskStatus.percent_done`.
- The progress bar must be deterministic from the real percentage and must not invent intermediate progress.

#### Polling / dedupe contract

- Background completion polling must continue querying real downloader status for pending rows even when the resulting Telegram edit is deduped.
- Telegram message editing is allowed only when all three hold:
  - channel is Telegram
  - `chat_id > 0`
  - `telegram_message_id > 0`
- Runtime must skip Telegram edits when the newly rendered live-progress text is byte-for-byte identical to the last synced text.
- For in-progress downloads, runtime must also respect a minimum edit interval gate.
- For completed downloads, runtime must allow one final completion-state edit even when the normal interval gate would still block another in-progress refresh.

### 4. Validation & Error Matrix

- Success card sent through reply-only path with no shared sender -> keep existing Telegram reply behavior, but no same-message live sync binding occurs.
- `download_monitor` row missing when binding `message_id` -> log operational failure and keep the success card delivered; background live editing stays disabled for that task.
- Telegram `edit_message_text` fails -> log operational failure, keep polling, and do not overwrite last-synced progress truth.
- Progress-sync truth write fails after a successful Telegram edit -> log operational failure; the Telegram card may already be updated, but later dedupe cannot rely on SQLite state.
- Non-Telegram status query or passive `status xxx` query -> must not receive the Telegram live-progress card unless the explicit Telegram-only channel branch is requested.

### 5. Good / Base / Bad Cases

- Good: Telegram confirm-download sends one success card, binds its `message_id`, then background polling edits that same message into `下载进行中` with a visible progress bar and later into `下载完成`.
- Base: Telegram message is bound, but the next poll renders the same text as the previous one; runtime still queries real status, but skips a redundant edit.
- Base: Download completes between polling intervals; runtime emits one final completion-card edit even if the previous in-progress edit happened recently.
- Bad: Background polling stops calling downloader status because the Telegram text was deduped.
- Bad: Telegram live-progress formatting leaks into Feishu / personal WeChat / WeCom status rendering.
- Bad: Character progress bar drifts away from the true percentage or is updated from fake local counters.

### 6. Tests Required

- `tests/test_get_download_status.py`
  - assert Telegram live-progress branch renders the live-progress card
  - assert card includes the character progress bar, percentage, speed, and ETA
- `tests/test_telegram_reply_formatter.py`
  - assert Telegram add-success card wording reflects that same-message progress sync will continue
- `tests/test_telegram_delivery_runtime.py`
  - assert `build_telegram_edit_text_func` preserves HTML parse mode and inline button extraction for the edited progress card
- `tests/test_download_follow_up_runtime.py`
  - assert bound Telegram messages are edited in place
  - assert identical rendered progress text is deduped
  - assert one final completion edit is still allowed before the row leaves `list_pending_completion`
- `make verify-mainline`
  - must stay green after Telegram live-progress sync changes

### 7. Wrong vs Correct

#### Wrong

- Store only `task_hash -> message_id` in memory and lose the binding after process restart.
- Skip status polling entirely whenever the previously rendered Telegram text did not change.
- Render a pretty progress bar from guessed polling counts while the exact percentage says something else.

#### Correct

- Persist Telegram message binding and last-sync truth in `download_monitor`, so restart recovery and dedupe work off SQLite truth.
- Continue querying real downloader state on every polling cycle, then decide separately whether a Telegram edit is needed.
- Derive the character progress bar directly from the real downloader percentage and keep the exact percentage/speed/ETA visible alongside it.
