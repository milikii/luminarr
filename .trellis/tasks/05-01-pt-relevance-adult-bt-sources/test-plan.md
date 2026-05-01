# Test Plan — PT relevance-first and adult BT source completion

## Scope

This plan covers:

1. PT relevance-first search over `movie / tv / anime`
2. PT candidate-first interaction before resource search
3. TMDB-enriched Telegram result cards
4. adult BT provider completion
5. adult metadata/helper source expansion + Telegram card readability

## Test Diagram

| Flow | Expected behavior | Test type |
|---|---|---|
| PT strong-title query | returns primary candidate + fallback candidates | unit + Telegram formatter |
| PT ambiguous query | returns 3-5 relevance-ranked candidates, not immediate year clarification | unit |
| PT mixed movie/tv/anime query | candidate list spans multiple media types | unit |
| PT candidate-first interaction | first round returns media candidate confirmation only; resource search starts after selection | unit + runtime |
| PT TMDB-enriched card | includes poster, title, year, type, short support text | unit + Telegram formatter |
| PT strong-title query | first round returns exact/near-exact media candidate confirmation, not resource mix | unit + runtime |
| PT still-empty query | returns explicit no-result path | unit |
| adult BT configured provider hit | returns BT resources with adult card | unit + integration-ish service test |
| adult BT metadata-only source hit but no provider hit | returns explicit resource-empty path, not false success | unit |
| adult helper fallback | primary helper fail -> backup helper | unit |
| adult provider empty config | curated fallback or explicit config behavior stays deterministic | unit |
| adult Telegram card | poster-first, Chinese labels, grouped metadata/resource sections | formatter + real smoke |
| adult metadata localization | title/series/actors use trusted Chinese aliases and retain original Japanese title | unit + Telegram formatter |
| unknown adult actor alias | no blind translation; original actor name is marked as unconfirmed | unit |
| Telegram real smoke | `丧尸`, `你的名字`, `成人搜 SSIS-483` render readable result cards | real smoke |

## Required Test Updates

### PT

- `tests/test_search_media.py`
  - title-only query no longer defaults to year clarification
  - mixed `movie / tv / anime` candidates are relevance-ranked
  - strong-title query returns primary candidate
  - first-round PT result does not mix in BT resource results
  - strong-title Japanese anime movie query such as `你的名字` prefers the exact TMDB movie identity
- `tests/test_telegram_reply_formatter.py`
  - PT Telegram card shows poster, type, year, alias/support text
  - adult Telegram card is poster-first and Chinese-readable
  - adult Telegram card uses Chinese main title/actor when localization has trusted aliases and keeps the Japanese title as subtitle
- `tests/test_adult_metadata_localization.py`
  - trusted localized title/series/actor aliases are emitted with original fields retained
  - unknown Japanese actor names are marked `中文名未确认` instead of being machine-translated
- `tests/test_private_chat_search_runtime.py`
  - runtime returns card-style results for ambiguous title-only search
  - runtime does not dispatch resource search before media candidate confirmation

### adult BT

- `tests/test_search_media.py`
  - adult provider hit returns resource results
  - helper-only hit does not masquerade as BT resource success
  - empty `BT_WEB_SOURCES` fallback behavior is deterministic
- `tests/test_bt_sources.py`
  - provider/helper role mapping for newly implemented sources
- `tests/test_main.py`
  - startup wiring builds expected adult provider/helper composition
- `tests/test_telegram_reply_formatter.py`
  - adult Telegram card still preserves poster, metadata source role, and copyable magnet

## Real Smoke

### Telegram

1. `丧尸`
2. `你的名字`
3. `Dune`
4. `成人搜 SSIS-483`

### Expected operator checks

- PT query does not immediately ask for year
- candidate cards are readable enough to identify the work
- strong-title query like `你的名字` first confirms the anime movie itself, not a bundle of expanded resource names
- adult BT returns actual resource candidates when upstream sites have them
- adult metadata sources enrich the card rather than replacing the resource result
- adult BT card shows poster first and key metadata fields in Chinese-friendly grouping
