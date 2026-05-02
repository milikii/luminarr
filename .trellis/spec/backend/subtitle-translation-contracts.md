# Subtitle Translation Contracts

## Scenario: Import-time subtitle translation quality

### 1. Scope / Trigger

- Trigger: subtitle translation now depends on metadata scraping output and TMDB-linked person-name guidance.
- This is a cross-layer contract because `metadata_scraper -> .metadata.json -> subtitle_translator` must agree on field names, fallback behavior, and failure mode.

### 2. Signatures

- Metadata sidecar writer:
  - `app.services.metadata_scraper.MetadataScraperService.scrape_for_import(...)`
- Subtitle translation entry:
  - `app.services.subtitle_translator.SubtitleTranslatorService.translate_for_import(...)`
- TMDB credits lookup:
  - `app.clients.tmdb.TmdbClient.get_movie_credits(tmdb_id, *, language="zh-CN")`
  - `app.clients.tmdb.TmdbClient.get_tv_credits(tmdb_id, *, language="zh-CN")`

### 3. Contracts

#### Metadata sidecar fields

Import-time metadata sidecar may include:

```json
{
  "tmdb": {
    "id": "157336",
    "title": "星际穿越",
    "original_title": "Interstellar",
    "year": "2014",
    "media_type": "movie"
  },
  "subtitle_translation": {
    "trusted_name_map": {
      "Matthew McConaughey": "马修·麦康纳",
      "Cooper": "库珀"
    },
    "source_priority": [
      "tmdb_zh_cn_credits",
      "original_name_fallback"
    ]
  }
}
```

#### Translation request payload

Subtitle chat-completion payload must include:

- `movie_title`
- `source_lines`
- `trusted_name_map`
- `rules.target_language`
- `rules.style`
- `rules.dialogue_tone`
- `rules.proper_noun_policy`
- `rules.return_json_only`
- `rules.json_schema`

#### Trusted-name policy

- `trusted_name_map` is a title-linked bilingual map built from confirmed media identity.
- If a trusted mapping exists, subtitle translation must use that Chinese name consistently.
- If no trusted mapping exists for a likely film/TV person name, translation should preserve the original name instead of inventing a transliteration.

### 4. Validation & Error Matrix

- Missing subtitle translation API key -> fail translation step with existing user-facing error; do not block metadata scraping.
- Missing / unreadable metadata sidecar -> subtitle translation continues with empty `trusted_name_map`.
- Missing `tmdb.media_type` or missing credits lookup function -> metadata sidecar may omit `subtitle_translation`; subtitle translation continues without trusted map.
- TMDB credits lookup HTTP / parse failure -> log operational warning, omit `subtitle_translation`, continue import flow.
- Non-string or empty `trusted_name_map` entries in metadata -> ignore invalid entries, do not fail subtitle translation.
- Model output line-count mismatch or invalid JSON -> fail subtitle translation for that import step, preserving existing fail-soft import behavior.

### 5. Good / Base / Bad Cases

- Good:
  - Metadata sidecar has `tmdb.id + media_type`.
  - TMDB zh-CN credits produce a non-empty `trusted_name_map`.
  - Translation payload contains the trusted map and produces subtitle-style Chinese.

- Base:
  - Metadata sidecar has title only, no usable `trusted_name_map`.
  - Translation still runs line-by-line with strengthened prompt, but unresolved names stay in original form.

- Bad:
  - Translation fabricates a Chinese person name with no trusted mapping.
  - Metadata scraping failure blocks the whole import just because credits lookup failed.
  - Subtitle translator assumes any metadata JSON is valid and crashes on malformed payloads.

### 6. Tests Required

- `tests/test_tmdb_client.py`
  - credits endpoint path / params are correct
  - localized cast/crew rows parse into credit objects

- `tests/test_metadata_scraper.py`
  - metadata sidecar writes `tmdb.media_type`
  - metadata sidecar writes `subtitle_translation.trusted_name_map` when credits are available
  - missing guidance path stays fail-soft

- `tests/test_subtitle_translator.py`
  - trusted name map from metadata is injected into subtitle translation payload
  - prompt/rules include subtitle-style tone + trusted-name policy
  - existing unsupported-format / bad-JSON / bad-encoding cases still behave correctly

- `tests/test_main.py`
  - startup wiring still constructs subtitle translation path successfully after credits lookup plumbing

### 7. Wrong vs Correct

#### Wrong

- Read TMDB title from metadata, then let the model freely guess all person names from subtitle context.
- Do synchronous network lookups inside every subtitle chunk translation call.
- Fail the whole import because online person-name guidance lookup was unavailable.

#### Correct

- Build trusted person-name guidance once from confirmed media identity during metadata scraping.
- Persist the result into metadata sidecar.
- Let subtitle translation read local guidance and use it as a hard constraint.
- If guidance is unavailable, fall back to original names, not machine-guessed Chinese names.
