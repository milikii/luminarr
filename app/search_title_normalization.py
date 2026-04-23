from __future__ import annotations

import re
import unicodedata

_SEQUEL_ALIAS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bpart\s+one\b", re.IGNORECASE), "1"),
    (re.compile(r"\bpart\s+two\b", re.IGNORECASE), "2"),
    (re.compile(r"\bpart\s+three\b", re.IGNORECASE), "3"),
    (re.compile(r"\bpart\s+four\b", re.IGNORECASE), "4"),
    (re.compile(r"\bpart\s+five\b", re.IGNORECASE), "5"),
    (re.compile(r"\bpart\s+six\b", re.IGNORECASE), "6"),
    (re.compile(r"\bpart\s+seven\b", re.IGNORECASE), "7"),
    (re.compile(r"\bpart\s+eight\b", re.IGNORECASE), "8"),
    (re.compile(r"\bpart\s+nine\b", re.IGNORECASE), "9"),
    (re.compile(r"\bpart\s+ten\b", re.IGNORECASE), "10"),
    (re.compile(r"\bviii\b", re.IGNORECASE), "8"),
    (re.compile(r"\bvii\b", re.IGNORECASE), "7"),
    (re.compile(r"\bvi\b", re.IGNORECASE), "6"),
    (re.compile(r"\biv\b", re.IGNORECASE), "4"),
    (re.compile(r"\biii\b", re.IGNORECASE), "3"),
    (re.compile(r"\bii\b", re.IGNORECASE), "2"),
    (re.compile(r"\bix\b", re.IGNORECASE), "9"),
    (re.compile(r"\bx\b", re.IGNORECASE), "10"),
)
_PART_DIGIT_PATTERN = re.compile(r"\bpart\s+(?P<value>(?:\d{1,2}|ii|iii|iv|v|vi|vii|viii|ix|x))\b", re.IGNORECASE)
_CHAPTER_TOKEN_PATTERN = re.compile(
    r"\bchapter\s+(?P<value>(?:\d{1,2}|ii|iii|iv|v|vi|vii|viii|ix|x))\b",
    re.IGNORECASE,
)
_CHINESE_PART_PATTERN = re.compile(r"第\s*(?P<value>[一二三四五六七八九十两\d]+)\s*部", re.IGNORECASE)
_CHINESE_NUMERAL_MAP = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def normalize_match_key(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", value).strip().lower()
    if not cleaned:
        return ""
    cleaned = re.sub(r"[._:：\-]+", " ", cleaned)
    cleaned = _normalize_sequel_aliases(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def compact_match_key(value: str) -> str:
    return value.replace(" ", "")


def _normalize_sequel_aliases(value: str) -> str:
    normalized = value
    normalized = _CHINESE_PART_PATTERN.sub(lambda match: str(_parse_chinese_part_number(match.group("value"))), normalized)
    normalized = _PART_DIGIT_PATTERN.sub(lambda match: str(_parse_ordinal_token(match.group("value"))), normalized)
    normalized = _CHAPTER_TOKEN_PATTERN.sub(lambda match: str(_parse_ordinal_token(match.group("value"))), normalized)
    for pattern, replacement in _SEQUEL_ALIAS_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _parse_chinese_part_number(value: str) -> int:
    cleaned = value.strip()
    if not cleaned:
        return 0
    if cleaned.isdigit():
        return int(cleaned)
    if cleaned == "十":
        return 10
    if cleaned.startswith("十") and len(cleaned) == 2:
        return 10 + _CHINESE_NUMERAL_MAP.get(cleaned[1], 0)
    if cleaned.endswith("十") and len(cleaned) == 2:
        return _CHINESE_NUMERAL_MAP.get(cleaned[0], 0) * 10
    if "十" in cleaned and len(cleaned) == 3:
        tens, _, ones = cleaned.partition("十")
        return _CHINESE_NUMERAL_MAP.get(tens, 0) * 10 + _CHINESE_NUMERAL_MAP.get(ones, 0)
    return _CHINESE_NUMERAL_MAP.get(cleaned, 0)


def _parse_ordinal_token(value: str) -> int:
    cleaned = value.strip().lower()
    if not cleaned:
        return 0
    if cleaned.isdigit():
        return int(cleaned)
    roman_map = {
        "ii": 2,
        "iii": 3,
        "iv": 4,
        "v": 5,
        "vi": 6,
        "vii": 7,
        "viii": 8,
        "ix": 9,
        "x": 10,
    }
    return roman_map.get(cleaned, 0)
