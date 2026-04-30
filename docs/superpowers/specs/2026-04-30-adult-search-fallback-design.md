# Adult Search Fallback Design

## Goal

When `成人搜 <query>` hits the current BT read-only route and that route cannot produce useful resource results, do not stop at the read-only empty-state message. Stay inside the adult-only BT search boundary and continue to return actionable resource-style output when configured adult-only sources can provide it.

## Confirmed Boundaries

- `成人搜` must remain adult-only.
- It may search:
  - configured adult BT web sources
  - configured adult-oriented Prowlarr indexers
- It must not fall back to the PT mainline search path.
- It must not silently expand into unconfigured adult sources.

## Proposed Behavior

1. `成人搜 <query>` keeps using the current adult-only source set.
2. If the current read-only response path would otherwise stop at `BT 只读探索未找到候选：{query}`, the service should attempt an adult-only resource fallback using the same configured source set.
3. If fallback finds configured adult-only resource candidates, return those candidates in a user-actionable result form instead of the read-only empty-state text.
4. If the configured adult-only source set truly returns zero candidates, return an explicit adult-source-empty result, not a generic BT read-only empty-state.

## Implementation Direction

- Keep the change inside `SearchMediaService` plus the existing formatter/state helpers.
- Prefer reusing current candidate persistence / reply formatting utilities over creating a second adult-search protocol.
- Do not change normal non-adult search behavior.
- Do not broaden source discovery or source configuration rules in this task.

## Acceptance Criteria

- `成人搜` no longer stops at the generic BT read-only empty-state when adult-only fallback can still return configured-source candidates.
- The fallback remains adult-only and never enters PT search.
- When configured adult-only sources are truly empty, the reply explicitly says the current adult source set has no results.
- Tests cover:
  - no-result read-only path with adult fallback candidates
  - no-result path with truly empty configured adult sources
  - guardrail that fallback does not switch to PT search
