# Person Name Sources Research

## Scope

Research date: 2026-05-02

Question: for subtitle translation quality, if movie / TV person names must use commonly used Chinese names from online sources, which sources are practical and safe to automate in this repo?

## Sources Checked

### TMDB official API

Sources:

* https://developer.themoviedb.org/reference/movie-credits
* https://developer.themoviedb.org/reference/tv-series-credits
* https://developer.themoviedb.org/docs/faq

What matters:

* TMDB has official credits endpoints for both movies and TV:
  - `/3/movie/{movie_id}/credits`
  - `/3/tv/{series_id}/credits`
* Both endpoints support a `language` query parameter.
* TMDB's developer FAQ states the API is free for non-commercial use with attribution, and is intended for programmatic use of movie / TV / actor data.

Implication for this repo:

* Best first online source, because the repo already has TMDB identity and API key flow.
* Lowest implementation cost: we already write `tmdb.id/title/original_title/year` into `.metadata.json`.
* Likely easiest path for title-linked cast/crew lookup.

Risk / limitation:

* Chinese localized person names may be incomplete or inconsistent across entries.
* Current local `TmdbClient` does not yet expose credits/person lookups, so code changes are required.

### Wikidata / Wikimedia official APIs

Sources:

* https://www.wikidata.org/wiki/Wikidata:REST_API/en
* https://www.wikidata.org/wiki/Help:Linked_Data_Interface
* https://www.mediawiki.org/wiki/API:Query

What matters:

* Wikidata exposes stable REST and Action APIs.
* Linked entity data is available via `Special:EntityData/<QID>.json`.
* Structured Wikidata data is CC0.
* MediaWiki APIs expose page terms / extracts / sitelinks and are suitable for structured retrieval.

Implication for this repo:

* Best fallback / cross-check source after TMDB.
* Good fit when we already know a concrete person entity or can resolve from a title-linked identity.
* Licensing / automation posture is much cleaner than HTML scraping sites.

Risk / limitation:

* Requires an entity-resolution step.
* Title-linked cast/crew matching is still easier than arbitrary subtitle-line name recognition.

### Douban

Sources checked:

* https://www.douban.com/
* official-domain search for current developer docs / public API pages did not surface a current structured API reference during this research pass

What matters:

* Douban clearly has widely used Chinese display names in practice.
* However, in this research pass I did not find a current official public developer API reference on official domains.

Implication for this repo:

* Douban is a potentially valuable display-reference source, but not a good first automation target for MVP.

Risk / limitation:

* Current official automation surface is unclear from this pass.
* Likely requires HTML scraping and anti-bot / maintenance handling.
* Higher legal / operational risk than TMDB + Wikidata.

## Recommended Source Priority

For MVP:

1. TMDB zh-CN credits as first online source
2. Wikidata / Wikimedia structured lookup as fallback or cross-check
3. If both lack a trusted Chinese name, keep original name; do not machine-translate or phonetic-guess

Do **not** make Douban scraping the primary automated source in the first implementation slice.

## Recommended Trigger Scope

Only resolve names for people tied to a known media identity:

* subtitle translation already has `.metadata.json`
* `.metadata.json` already stores `tmdb.id/title/original_title/year`

Therefore the practical MVP is:

* use media identity to fetch cast/crew names
* build a small trusted bilingual name map for that title
* use the map to protect or substitute names during subtitle translation

Avoid this in MVP:

* full subtitle-line NER for arbitrary names
* open-ended internet search per line

## Recommendation

Use `TMDB credits -> Wikidata fallback -> original name fallback` as the subtitle-person-name pipeline. Treat Douban as a later enhancement only if the user explicitly wants scraping trade-offs.
