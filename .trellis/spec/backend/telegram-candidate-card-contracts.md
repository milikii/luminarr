# Telegram Candidate Card Contracts

> Executable contracts for Telegram media-candidate confirmation cards.

## Scenario: Telegram Candidate Confirmation Cards

### 1. Scope / Trigger

- Trigger: Telegram candidate confirmation was upgraded from mixed text follow-up into per-candidate poster cards with candidate-specific selection buttons.
- Why code-spec depth is required: this crosses service selection flow, TMDB/fanart image enrichment, Telegram runtime media sending, and channel-specific fallback behavior.

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

- Every Telegram media candidate must render as its own poster card.
- Each candidate card must expose candidate-specific selection interaction, currently via callback data carrying the candidate index.
- Candidate captions use Telegram HTML formatting for visual hierarchy.
- Candidate cards may be sent as multiple Telegram messages; the invariant is one card per candidate, not a single aggregate message.

#### Poster-source contract

- Poster resolution priority for Telegram candidate confirmation is:
  1. TMDB poster
  2. fanart poster
  3. generated placeholder poster
- `fanart` enrichment applies only to Telegram candidate-confirmation rendering and must not alter non-Telegram channel output contracts.
- Empty `channel=""` still counts as the default Telegram candidate-confirmation path for poster enrichment.

#### Placeholder contract

- If TMDB and fanart both lack a poster, the candidate must still be shown.
- Placeholder output must remain image-based so the candidate is still a poster card rather than a text-only fallback.
- Placeholder generation may use Pillow, which is already a project dependency.
- CJK-capable fonts must be preferred over Latin-only defaults so Chinese/Japanese/Korean candidate titles remain legible.

#### Transport contract

- Telegram media sending must support `reply_markup` on candidate-card media sends.
- If candidate media sending fails, runtime must fall back to text without changing candidate-selection semantics.

### 4. Validation & Error Matrix

- Fanart HTTP / auth / proxy failure -> log operational failure, keep candidate visible, fall back to placeholder if no TMDB poster exists.
- TMDB poster missing and no fanart poster -> generate placeholder and keep candidate card flow intact.
- Placeholder generation failure -> log operational failure, fall back to text candidate block.
- Telegram `send_photo` / media send failure -> log operational failure, fall back to text candidate block.
- Non-Telegram channel rendering -> must keep previous candidate confirmation layout and must not receive Telegram-only fanart/placeholder behavior.

### 5. Good / Base / Bad Cases

- Good: Telegram ambiguous title query returns multiple candidate photo cards, each with its own select button, and selecting a candidate then moves into resource search.
- Base: TMDB poster is missing, fanart returns a poster, and Telegram candidate card uses the fanart image without changing non-Telegram output.
- Base: TMDB and fanart both miss, runtime sends a generated placeholder poster card and preserves candidate selection.
- Bad: first candidate gets a poster while the remaining candidates degrade into text-only names/buttons.
- Bad: fanart enrichment starts running for WeChat / Feishu / WeCom candidate rendering.
- Bad: resource search executes before candidate selection is confirmed.

### 6. Tests Required

- `tests/test_search_media.py`
  - assert Telegram candidate-confirmation path does not trigger resource search
  - assert missing TMDB poster can use fanart poster
  - assert default empty `channel` still gets Telegram fanart enrichment
  - assert non-Telegram candidate confirmation layout stays unchanged
- `tests/test_telegram_reply_formatter.py`
  - assert candidate confirmation text becomes HTML candidate-card captions
  - assert candidate placeholder path still yields per-candidate card behavior
  - assert candidate selection buttons remain candidate-specific
- `tests/test_telegram_delivery_runtime.py`
  - assert media sending can forward `reply_markup`
  - assert inline keyboard behavior remains valid for candidate-card media sends
- `make verify-stage1-telegram-delivery`
  - must stay green after Telegram candidate-card changes

### 7. Wrong vs Correct

#### Wrong

- Use TMDB poster for the first candidate and leave the rest as plain text rows.
- Treat `channel=""` as “not Telegram”, causing default Telegram candidate confirmations to skip fanart fallback.
- Move resource search into the candidate-card rendering path because Telegram now shows richer candidate cards.

#### Correct

- Keep one visual poster card per Telegram candidate, regardless of whether the image comes from TMDB, fanart, or placeholder generation.
- Apply fanart enrichment to the Telegram candidate-confirmation path, including the default empty-channel path.
- Preserve the business order: candidate lock first, resource search second.
