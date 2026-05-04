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

#### Bilingual subtitle presentation contract

- Plain translated subtitles remain the compatibility path and must still be emitted.
- In addition to the plain path, the subtitle pipeline may emit a bilingual ASS/SSA sidecar artifact for media players that support styled subtitles.
- The bilingual artifact should render:
  - Chinese on the top line
  - English on the bottom line in smaller text
  - `LXGW WenKai` / `LxgwWenKai` as the preferred Chinese font family name
- If bilingual sidecar generation fails, the plain subtitle output must still succeed and remain the authoritative fallback.

### 4. Validation & Error Matrix

- Missing subtitle translation API key -> fail translation step with existing user-facing error; do not block metadata scraping.
- Missing / unreadable metadata sidecar -> subtitle translation continues with empty `trusted_name_map`.
- Missing `tmdb.media_type` or missing credits lookup function -> metadata sidecar may omit `subtitle_translation`; subtitle translation continues without trusted map.
- TMDB credits lookup HTTP / parse failure -> log operational warning, omit `subtitle_translation`, continue import flow.
- Non-string or empty `trusted_name_map` entries in metadata -> ignore invalid entries, do not fail subtitle translation.
- Model output line-count mismatch or invalid JSON -> fail subtitle translation for that import step, preserving existing fail-soft import behavior.
- Bilingual ASS/SSA sidecar generation failure -> log a warning and keep the plain translation output; do not fail the import-time subtitle step.

## Scenario: AI cast localization supplement

### 1. Scope / Trigger

- Trigger: TMDB zh-CN credits are sufficient for most metadata truth, but some cast rows still need a helper-only Chinese name / role supplement.
- This is a cross-layer contract because `metadata_scraper -> cast_truth -> NFO / metadata.json` must agree on which fields may be localized and which fields must remain canonical.
- This task settled on **AI cast localization** as the default补充方向 instead of external web helpers, because external Chinese sources showed anti-bot / challenge instability and are not suitable for the default media mainline.

### 2. Signatures

- `app.services.cast_localization.CastLocalizationService.localize(...)`
- `app.services.cast_localization.AICastLocalizationService.localize(...)`
- `app.services.metadata_scraper.MetadataScraperService._localize_cast_truth(...)`
- `app.services.metadata_scraper.MetadataScraperService._enrich_cast_truth_with_domestic_helper(...)`

### 3. Contracts

#### Cast truth contract

- TMDB remains the only main source.
- AI may only supplement:
  - `name`
  - `character`
- AI must not modify:
  - `id`
  - `original_name`
  - `original_character`
  - `order`
  - `profile_image_url`
- AI localization should be conservative:
  - actor names should stay original if confidence is low
  - character names may be translated more freely
  - if the model is unsure, it should prefer empty string or original text over a fabricated common translation

#### Confidence policy

- Actor names are stricter than character names.
- If the model is not confident in an actor name, it should leave the field empty or preserve the original value.
- Character names may be translated more freely, but still must not invent new identities or roles.

#### Fail-soft policy

- Missing API key, disabled service, bad JSON, timeout, or any helper error must soft-fail.
- Soft-fail means:
  - metadata scraping still succeeds
  - NFO still writes TMDB truth
  - AI output is treated as optional enrichment only
- The AI localization seam should reuse existing subtitle/OpenAI-compatible runtime settings where possible, so the project does not grow a second LLM configuration path just for cast text.

### 4. Validation & Error Matrix

- Missing AI API key -> no-op
- Bad AI JSON -> log operational warning + return TMDB-only cast truth
- AI returns non-CJK localized text for an attempted localization -> keep original value
- AI returns localized text for only some cast rows -> merge only the matched rows

### 5. Tests Required

- `tests/test_cast_localization.py`
  - service disabled returns empty
  - prompt only requests unlocalized rows
  - parser keeps id alignment
- `tests/test_metadata_scraper.py`
  - TMDB-only path unchanged when AI disabled
  - AI enrichment updates only `name` / `character`
  - AI errors soft-fail
- `tests/test_main.py`
  - runtime wiring only injects AI cast localization when subtitle/OpenAI-compatible config is available

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
  - plain translation still succeeds when bilingual sidecar write fails
  - bilingual ASS sidecar is generated for both SRT and ASS inputs

- `tests/test_main.py`
  - startup wiring still constructs subtitle translation path successfully after credits lookup plumbing

## Scenario: Subtitle provider smoke verification

### 1. Scope / Trigger

- Trigger: operators need a stable way to verify a newly switched subtitle provider / model before trusting import-time subtitle translation again.
- This is an operator-facing contract spanning `Makefile`, env loading, provider `/models` compatibility checks, and the minimum translation chain.

### 2. Signatures

- `make verify-subtitle-provider-smoke`
- `python -m app.maintenance.verify_subtitle_provider_smoke`

### 3. Contracts

#### Config contract

- The smoke tool reads only subtitle-provider-related env:
  - `SUBTITLE_TRANSLATION_API_KEY`
  - `SUBTITLE_TRANSLATION_BASE_URL`
  - `SUBTITLE_TRANSLATION_MODEL`
  - `SUBTITLE_TRANSLATION_TIMEOUT_SECONDS`
  - `OUTBOUND_PROXY_URL`
- It must not require unrelated Telegram / downloader runtime config just to run the provider smoke.

#### `/models` contract

- If provider `/models` is reachable and lists the configured model, smoke prints `/models: ok`.
- If `/models` is unreachable, unsupported, or unparseable, smoke prints `/models: warning` and still proceeds to the translation smoke.
- If `/models` succeeds but does not contain the configured model id, smoke fails immediately.

#### Translation smoke contract

- Smoke uses a tiny built-in subtitle sample, not a real library file.
- The smoke passes only when translation returns:
  - the same number of lines as the source sample
  - all non-empty translated lines
- Runtime errors from the translation chain must fail the smoke with a clear `translation: fail - ...` line.

### 4. Tests Required

- `tests/test_verify_subtitle_provider_smoke.py`
  - subtitle-only env loading works
  - `/models` success path passes
  - `/models` warning path still reaches translation smoke
  - missing configured model fails
  - blank translated line fails
  - runtime error from translation chain fails

- `tests/test_makefile.py`
  - `verify-subtitle-provider-smoke` stays listed in `help`
  - the target sources `$(ENV_FILE)` before invoking the module entrypoint

## Scenario: Bilingual subtitle presentation

### 1. Scope / Trigger

- Trigger: import-time subtitles should keep the existing plain translation path, but also expose a styled bilingual artifact for media players that support ASS/SSA.
- Why code-spec depth is required: the subtitle translation pipeline, subtitle file naming, and media-server consumption must agree on plain vs styled outputs.

### 2. Contracts

- Plain translated subtitle output must continue to exist for backward compatibility.
- Bilingual styled subtitle output should be emitted as an additional ASS/SSA artifact when possible.
- Styled bilingual subtitles should use:
  - Chinese on the top line
  - English on the bottom line in smaller text
  - `LXGW WenKai` / `LxgwWenKai` as the preferred Chinese font
- If a player cannot use styled output, the plain translation path remains the fallback.

### 3. Validation & Error Matrix

- Styled bilingual output write failure -> log operational warning and keep the plain translation output.
- Missing font availability on the host does not block file generation; the font name is a rendering preference, not a runtime dependency.

### 4. Tests Required

- `tests/test_subtitle_translator.py`
  - plain translation still exists
  - bilingual ASS sidecar is generated for SRT input
  - bilingual ASS sidecar is generated for ASS input
  - sidecar content includes `LXGW WenKai` and the dual-line Chinese/English payload

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
