# subtitle translation proxy toggle

## Goal

Keep the existing repo-local ffmpeg extraction fix and add a dedicated boolean switch for subtitle translation proxy usage so subtitle translation does not automatically inherit `OUTBOUND_PROXY_URL`.

## What I already know

* The user wants a minimal change scoped to subtitle translation proxy wiring.
* Existing uncommitted repo-local ffmpeg extraction fix lives in `app/services/subtitle_translation_support.py` and related subtitle tests.
* Current wiring passes `settings.outbound_proxy_url` into `SubtitleTranslatorService` from `app/main.py`.
* Other outbound chains such as TMDB, Fanart, BT web sources, and adult metadata must stay unchanged.

## Assumptions (temporary)

* The new env flag should be named `SUBTITLE_TRANSLATION_USE_PROXY`.
* Missing or false-like values should resolve to `False`.
* When the flag is `True`, subtitle translation should reuse `settings.outbound_proxy_url` exactly as-is.

## Open Questions

* None. The user already specified expected behavior and preferred touchpoints.

## Requirements

* Preserve the current repo-local ffmpeg extraction fix if it is still uncommitted.
* Add `SUBTITLE_TRANSLATION_USE_PROXY` parsing to `app/config.py`.
* Default behavior: subtitle translation does not use `OUTBOUND_PROXY_URL`.
* When `SUBTITLE_TRANSLATION_USE_PROXY=true`, `SubtitleTranslatorService` receives `settings.outbound_proxy_url`.
* No other runtime path may change proxy behavior.

## Acceptance Criteria

* [ ] `load_settings()` returns `subtitle_translation_use_proxy=False` when the env var is unset.
* [ ] `load_settings()` returns `subtitle_translation_use_proxy=True` when the env var is set to `true`.
* [ ] `SubtitleTranslatorService` receives empty `proxy_url` when the flag is false or missing.
* [ ] `SubtitleTranslatorService` receives `settings.outbound_proxy_url` when the flag is true.
* [ ] Existing repo-local ffmpeg extraction path remains covered by tests.

## Definition of Done (team quality bar)

* Tests added or updated for config, startup wiring, and subtitle translator behavior
* Relevant pytest target passes
* No unrelated proxy consumers change behavior

## Out of Scope (explicit)

* Changing TMDB, Fanart, BT web source, Telegram, or adult metadata proxy behavior
* Refactoring unrelated config parsing or service wiring

## Technical Notes

* Relevant code paths: `app/config.py`, `app/main.py`, `app/services/subtitle_translator.py`
* Relevant tests: `tests/test_config.py`, `tests/test_main.py`, `tests/test_subtitle_translator.py`
* Relevant spec files: `.trellis/spec/backend/subtitle-translation-contracts.md`, `.trellis/spec/backend/quality-guidelines.md`
