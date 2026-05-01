from __future__ import annotations

from dataclasses import dataclass

from app.search_title_normalization import compact_match_key, normalize_match_key

PRIMARY_FRANCHISE_INTENT_BOOST = 2


@dataclass(frozen=True, slots=True)
class _FranchiseIntentRule:
    query_alias_keys: tuple[str, ...]
    primary_candidate_keys: tuple[str, ...]
    family_candidate_keys: tuple[str, ...]


_FRANCHISE_INTENT_RULES: tuple[_FranchiseIntentRule, ...] = (
    _FranchiseIntentRule(
        query_alias_keys=(
            "魔戒",
            "指环王",
            "lordoftherings",
            "thelordoftherings",
        ),
        primary_candidate_keys=(
            "指环王护戒使者",
            "指环王双塔奇兵",
            "指环王王者无敌",
            "thelordoftheringsthefellowshipofthering",
            "thelordoftheringsthetwotowers",
            "thelordoftheringsthereturnoftheking",
        ),
        family_candidate_keys=(
            "指环王",
            "lordoftherings",
            "thelordoftherings",
        ),
    ),
)


def resolve_franchise_intent_boost(
    query_title: str,
    candidate_title: str,
    candidate_original_title: str,
) -> int:
    """Return an intent boost when the query clearly asks for a known franchise family."""

    rule = _resolve_franchise_intent_rule(query_title)
    if rule is None:
        return 0

    candidate_keys = tuple(
        key
        for key in (
            _compact_query_key(candidate_title),
            _compact_query_key(candidate_original_title),
        )
        if key
    )
    if not candidate_keys:
        return 0

    if _candidate_matches_intent(candidate_keys, rule.primary_candidate_keys):
        return PRIMARY_FRANCHISE_INTENT_BOOST
    if _candidate_matches_intent(candidate_keys, rule.family_candidate_keys):
        return 1
    return 0


def has_explicit_franchise_intent(query_title: str) -> bool:
    """Return whether the query explicitly matches a curated high-value franchise alias."""

    return _resolve_franchise_intent_rule(query_title) is not None


def _candidate_matches_intent(candidate_keys: tuple[str, ...], expected_keys: tuple[str, ...]) -> bool:
    for candidate_key in candidate_keys:
        if any(expected_key in candidate_key for expected_key in expected_keys):
            return True
    return False


def _compact_query_key(value: str) -> str:
    normalized_value = normalize_match_key(value)
    if not normalized_value:
        return ""
    return compact_match_key(normalized_value)


def _resolve_franchise_intent_rule(query_title: str) -> _FranchiseIntentRule | None:
    query_key = _compact_query_key(query_title)
    if not query_key:
        return None

    for rule in _FRANCHISE_INTENT_RULES:
        if query_key in rule.query_alias_keys:
            return rule
    return None
