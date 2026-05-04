# Subtitle Translation Chunk Tightening

## Goal

Reduce subtitle translation chunk size for long subtitle jobs so the new provider is less likely to stall on full-length translations, while keeping the existing subtitle translation behavior and retry flow intact.

## Background

- Current subtitle translation chunking uses `60` lines per request.
- A minimal no-proxy smoke request already returns `200 OK` on the new provider.
- A real long subtitle job for `爱的进行时` takes too long to return under the new provider.

## Scope

- Update only subtitle-translation-related files.
- Prioritize:
  - `app/services/subtitle_translation_support.py`
  - `tests/test_subtitle_translator.py`
- Tighten the chunk size to a more conservative value for long subtitle translation requests.
- Update focused tests that currently encode the old `60`-line chunk assumption.

## Non-Goals

- No business boundary changes.
- No proxy-chain changes.
- No provider/client API changes.
- No retry-strategy redesign beyond keeping the existing same-chunk retry and split fallback behavior working with the smaller chunk size.

## Acceptance Criteria

- Subtitle translation chunk size is reduced from `60` to `30`.
- Large subtitle chunking tests reflect the new request pattern.
- Existing line-count mismatch retry/split behavior still works under the smaller chunk size.
- Focused subtitle translation tests pass.
