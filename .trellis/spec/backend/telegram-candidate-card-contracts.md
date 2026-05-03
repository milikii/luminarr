# Telegram Candidate Confirmation Contracts

> Executable contracts for Telegram media-candidate confirmation delivery.

## Scenario: Telegram Candidate Confirmation Delivery

### 1. Scope / Trigger

- Trigger: Telegram candidate confirmation was upgraded from per-candidate poster cards into a single aggregate HTML message flow.
- Why code-spec depth is required: this crosses service selection flow, TMDB/fanart enrichment, Telegram formatter/runtime chunking, and channel-specific fallback behavior.

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

#### Telegram aggregate-confirmation contract

- Telegram media candidate confirmation must render as one aggregate HTML message whenever it fits within Telegram's 4096-character limit.
- When the aggregate text exceeds 4096 characters, runtime must continue in ordered follow-up text messages; splitting is a transport fallback, not a return to poster-card mode.
- The first line must follow the operator-facing pattern `【查询词】共找到 N 条相关信息，请选择操作`.
- Every candidate title must be a clickable TMDB detail link.
- The first candidate must expose a poster preview link when poster/fanart data is available.
- Candidate selection remains candidate-first and text-index driven; this contract does not redesign PT resource cards or resource-search ordering.

#### Poster-source contract

- Poster resolution priority for Telegram candidate confirmation preview is:
  1. TMDB poster
  2. fanart poster
- `fanart` enrichment applies only to Telegram candidate-confirmation rendering and must not alter non-Telegram channel output contracts.
- Empty `channel=""` still counts as the default Telegram candidate-confirmation path for poster enrichment.
- If no poster/fanart URL is available, candidate confirmation must stay text-first; the missing preview link must not block candidate display.

#### Transport contract

- Telegram candidate confirmation prefers `send_message(parse_mode="HTML")`, not `send_photo`.
- Runtime must preserve HTML formatting when sending aggregate candidate messages.
- Runtime must split oversized aggregate confirmation text without reordering candidates or dropping the final action lines.

### 4. Validation & Error Matrix

- Fanart HTTP / auth / proxy failure -> log operational failure, keep candidate visible, omit preview link if no TMDB poster exists.
- TMDB poster missing and no fanart poster -> keep aggregate confirmation text intact without a preview link.
- Aggregate candidate text exceeds Telegram 4096-char limit -> split into ordered continuation messages and keep the final action lines in the last chunk.
- Non-Telegram channel rendering -> must keep previous candidate confirmation layout and must not receive Telegram-only fanart/placeholder behavior.

### 5. Good / Base / Bad Cases

- Good: Telegram ambiguous title query returns one aggregate HTML message with clickable TMDB titles, the first candidate exposes a poster preview link, and selecting a candidate then moves into resource search.
- Base: TMDB poster is missing, fanart returns a poster, and Telegram aggregate confirmation uses the fanart URL as the first preview link without changing non-Telegram output.
- Base: TMDB and fanart both miss, runtime still sends the aggregate candidate text and preserves candidate selection.
- Bad: Telegram falls back to one poster card per candidate again.
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
  - assert candidate confirmation text becomes one aggregate HTML message with clickable TMDB titles
  - assert only the first candidate exposes a poster preview link
  - assert oversized aggregate confirmation text is split into continuation messages under 4096 characters
- `tests/test_telegram_delivery_runtime.py`
  - assert standard Telegram text/media delivery behavior remains valid after the aggregate-confirmation change
- `make verify-stage1-telegram-delivery`
  - must stay green after Telegram aggregate-confirmation changes

### 7. Wrong vs Correct

#### Wrong

- Use TMDB poster for the first candidate and leave the rest as separate poster cards.
- Treat `channel=""` as “not Telegram”, causing default Telegram candidate confirmations to skip fanart fallback.
- Move resource search into the aggregate rendering path because Telegram now shows richer candidate confirmations.

#### Correct

- Keep one aggregate candidate-confirmation flow for Telegram, with clickable TMDB titles and a best-effort first-candidate poster preview link.
- Apply fanart enrichment to the Telegram candidate-confirmation path, including the default empty-channel path.
- Preserve the business order: candidate lock first, resource search second.
