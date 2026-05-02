# TMDB Candidate Ranking Contracts

> Executable contracts for TMDB media-candidate ranking, with explicit franchise protection.

## Scenario: Protected Franchise Candidate Ranking

### 1. Scope / Trigger

- Trigger: short-title TMDB candidate ranking needed an explicit protected-franchise path so `超人` no longer surfaced unrelated `contains` matches like `女超人` / `一拳超人`.
- Why code-spec depth is required: the change crosses TMDB payload parsing, franchise-intent detection, candidate confirmation ranking, and persisted candidate-selection UX.

### 2. Signatures

- `app.clients.tmdb.TmdbMovie`
- `app.clients.tmdb.TmdbClient.search_media_candidates(title: str, year: str = "", *, limit: int = 5) -> list[TmdbMovie]`
- `app.clients.tmdb._rank_tmdb_candidates(candidates: list[TmdbMovie], *, title: str, year: str, limit: int) -> list[TmdbMovie]`
- `app.services.search_request_context._select_confirmation_tmdb_candidates(*, parsed_query: ParsedMovieQuery, tmdb_candidates: Sequence[TmdbMovie]) -> tuple[TmdbMovie, ...]`
- `app.search_franchise_intent.resolve_franchise_intent_boost(query_title: str, candidate_title: str, candidate_original_title: str) -> int`
- `app.search_franchise_intent.has_explicit_franchise_intent(query_title: str) -> bool`
- `app.search_franchise_intent.franchise_family_metric_sort_key(*, popularity: float, vote_average: float, vote_count: int) -> tuple[float, float, int]`

### 3. Contracts

#### TMDB payload contract

- `TmdbMovie` carries:
  - `popularity`
  - `vote_average`
  - `vote_count`
- Both movie and TV parsing paths must populate `vote_average` when TMDB provides it.

#### Protected-franchise contract

- Explicit protected-franchise handling only applies when `has_explicit_franchise_intent(query_title)` is true.
- Current curated protected franchises include:
  - `魔戒` / `指环王` / `Lord of the Rings`
  - `超人` / `Superman`
- Candidate-family matching for protected franchises must be stricter than generic substring matching:
  - allowed: exact match
  - allowed: startswith family match
  - not allowed: arbitrary contains match

This means:
- `超人` / `超人2` / `超人前传` / `超人归来` may stay in-family
- `女超人` / `一拳超人` must not be pulled in by protected-family matching

#### Same-family ordering contract

- For title-only protected-franchise queries, same-family ordering must use explicit TMDB metrics:
  1. `popularity`
  2. `vote_average`
  3. `vote_count`
- Sort direction is descending.

#### Year-aware protected-franchise contract

- If the user query includes an explicit year, protected-family ordering must preserve `year_match` before metric ordering.
- Ordering becomes:
  1. `year_match`
  2. `popularity`
  3. `vote_average`
  4. `vote_count`

This prevents a more popular wrong-year family member from outranking the intended year-qualified result.

#### Confirmation-path consistency contract

- Candidate-confirmation ranking in `search_request_context` must mirror protected-franchise ranking semantics used in TMDB candidate ranking.
- Telegram / default candidate-confirmation UX must not reintroduce old family-order drift after TMDB ranking has already been cleaned up.

### 4. Validation & Error Matrix

- Protected-franchise query with no curated rule -> fall back to generic ranking logic.
- Protected-franchise query with explicit year -> wrong-year but more popular family candidate must not outrank the matching-year candidate.
- Protected-franchise query without year -> unrelated contains candidates must not appear via family protection.
- Missing `vote_average` in TMDB payload -> treat as `0.0`, keep ordering stable.
- Generic short CJK query without protected intent -> preserve existing broad-query logic unless explicit tests say otherwise.

### 5. Good / Base / Bad Cases

- Good: query `超人` returns `超人`, `超人前传`, `超人归来` while excluding `女超人` and `一拳超人`.
- Good: query `超人 2001` keeps the `2001` family member ahead of a more popular `2025` family member.
- Base: query `传奇` still allows broader same-token candidates per existing short-query spread logic.
- Base: query `丧尸` keeps existing candidate-spread behavior unless a protected rule is added later.
- Bad: using `contains` to treat `女超人` as a protected-family match for `超人`.
- Bad: letting title-only TMDB API return order implicitly define protected-family ordering.

### 6. Tests Required

- `tests/test_tmdb_client.py`
  - assert `vote_average` is parsed for both movie and TV detail lookups
  - assert protected-franchise title-only query excludes unrelated contains matches
  - assert protected-franchise same-family ordering uses TMDB metrics
  - assert explicit-year protected-franchise query preserves `year_match`
- `tests/test_search_media.py`
  - assert confirmation path mirrors protected-franchise ranking
  - assert title-only `超人` candidate confirmation excludes `女超人` / `一拳超人`
  - assert explicit-year `超人 2001` confirmation keeps the matching-year family candidate ahead
- Existing covered regressions for `传奇`, `丧尸`, `Dune 2021`, and `魔戒` must remain green.

### 7. Wrong vs Correct

#### Wrong

- Treat every candidate containing `超人` as part of the Superman family.
- Use `popularity` alone and let `超人 2025` outrank `超人前传 2001` even when the user asked for `超人 2001`.
- Parse `vote_count` and `popularity` but ignore `vote_average`, then claim ordering is “按 TMDB 热度和评分”.

#### Correct

- Limit protected-family matching to exact/startswith family members.
- For `超人 2001`, rank matching-year family entries first, then apply TMDB metric ordering.
- Parse and use `popularity -> vote_average -> vote_count` explicitly for title-only protected-family ordering.
