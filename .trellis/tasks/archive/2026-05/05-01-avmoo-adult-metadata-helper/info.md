# Implementation context

## Decision

Start with static HTTP scraping for Avmoo. The live pages currently include the metadata in returned HTML, so a headless browser would add operational cost without solving a present blocker.

## MVP

1. Add `AvmooReadOnlyHelperClient`.
2. Compose Avmoo primary + JavLibrary backup behind the existing `adult_read_only_lookup_func` wiring.
3. Preserve existing candidate decoration and Telegram formatting.
4. Add focused tests for Avmoo parsing and fallback order.

## Non-goals

- No browser automation.
- No new dependency.
- No DB cache.
- No change to adult-only search boundaries.

## Known live fixture

`SSIS-483` currently resolves through Avmoo static HTML:

- Search page contains `a.movie-box href="//avmoo.shop/cn/movie/4221ec1035fdf66f"`.
- Search result poster is `https://jp.netcdn.space/digital/video/ssis00483/ssis00483ps.jpg`.
- Detail page poster is `https://jp.netcdn.space/digital/video/ssis00483/ssis00483pl.jpg`.
- Detail page fields include `发行时间`, `长度`, `导演`, `制作商`, `发行商`, `系列`, `类别`, and `演员`.

## Risk

Avmoo HTML is not a formal API. Parser should fail closed: return `None` or omit missing optional fields while keeping BT candidates visible.
