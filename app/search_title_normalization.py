from __future__ import annotations

import re
import unicodedata

_SEARCH_TITLE_NOISE_VARIANTS: tuple[str, ...] = (
    r"imax(?:\s+enhanced)?",
    r"(?:the\s+)?extended(?:\s+(?:edition|cut))?",
    r"(?:the\s+)?special(?:\s+extended)?\s+edition",
    r"(?:the\s+)?ultimate\s+edition",
    r"(?:the\s+)?final\s+cut",
    r"(?:the\s+)?director(?:'?s)?\s+cut",
    r"remaster(?:ed)?",
    r"theatrical(?:\s+(?:cut|version))?",
    r"uncut",
    r"unrated",
    r"(?:the\s+)?anniversary\s+edition",
    r"(?:the\s+)?collector(?:'?s)?\s+edition",
)
BT_RESULT_PROVIDER_TAGS = frozenset(
    {
        "amzn",
        "dsnp",
        "nf",
        "atvp",
        "hmax",
        "itunes",
    }
)
BT_RESULT_TITLE_NOISE_TOKENS = frozenset(
    {
        "2160p",
        "4k",
        "1080p",
        "720p",
        "480p",
        "web",
        "dl",
        "webdl",
        "webrip",
        "bluray",
        "blu",
        "ray",
        "bdrip",
        "hdr",
        "dv",
        "hevc",
        "x264",
        "x265",
        "h264",
        "h265",
        "ddp",
        "aac",
        "dts",
        "hd",
        "atmos",
        "truehd",
        "uhd",
        "10bit",
        "8bit",
        "remux",
        "ma",
        "2audios",
        "csweb",
        "frds",
        "hdsweb",
        "diy",
        "hhweb",
        "eur",
    }
) | BT_RESULT_PROVIDER_TAGS


def _union_pattern(variants: tuple[str, ...]) -> str:
    return rf"(?:{'|'.join(variants)})"


SEARCH_TITLE_NOISE_PATTERN = _union_pattern(_SEARCH_TITLE_NOISE_VARIANTS)
_SEARCH_TITLE_NOISE_SEQUENCE_PATTERN = rf"{SEARCH_TITLE_NOISE_PATTERN}(?:\s+{SEARCH_TITLE_NOISE_PATTERN})*"
_TRAILING_SEQUEL_DIGIT_WITH_YEAR_RE = re.compile(
    r"^(?P<title>.+?)(?P<separator>\s*)(?P<sequel>\d{1,2})(?:\s+|\s*[\[(]\s*)(?P<year>(?:19|20)\d{2})(?:\s*[\])])?$"
)
_TRAILING_SEQUEL_TOKEN_WITH_YEAR_RE = re.compile(
    r"^(?P<title>.+?)(?P<separator>\s*)(?P<sequel>(?:\d{1,2}|ii|iii|iv|v|vi|vii|viii|ix|x|第\s*[一二三四五六七八九十两\d]+\s*部))(?:\s+|\s*[\[(]\s*)(?P<year>(?:19|20)\d{2})(?:\s*[\])])?$",
    re.IGNORECASE,
)
_SEQUEL_VALUE_PATTERN = r"(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|ii|iii|iv|v|vi|vii|viii|ix|x|第\s*[一二三四五六七八九十两\d]+\s*部)"
_SEQUEL_PHRASE_PATTERN = rf"(?:(?:part|chapter)\s+{_SEQUEL_VALUE_PATTERN}|{_SEQUEL_VALUE_PATTERN})"
_SEQUEL_SUFFIX_RE = re.compile(rf"^(?:{_SEQUEL_PHRASE_PATTERN}|\d{{4}})$", re.IGNORECASE)
_TRAILING_SEQUEL_TOKEN_WITH_NOISE_AND_YEAR_RE = re.compile(
    rf"^(?P<title>.+?)(?P<separator>\s*)(?P<sequel>{_SEQUEL_PHRASE_PATTERN})(?:\s+(?P<noise>{_SEARCH_TITLE_NOISE_SEQUENCE_PATTERN}))?(?:\s+|\s*[\[(]\s*)(?P<year>(?:19|20)\d{{2}})(?:\s*[\])])?$",
    re.IGNORECASE,
)
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
_PART_DIGIT_PATTERN = re.compile(
    r"\bpart\s+(?P<value>(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|ii|iii|iv|v|vi|vii|viii|ix|x))\b",
    re.IGNORECASE,
)
_CHAPTER_TOKEN_PATTERN = re.compile(
    r"\bchapter\s+(?P<value>(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|ii|iii|iv|v|vi|vii|viii|ix|x))\b",
    re.IGNORECASE,
)
_TRAILING_ORDINAL_WORD_PATTERN = re.compile(r"\b(?P<value>(?:one|two|three|four|five|six|seven|eight|nine|ten))\b$", re.IGNORECASE)
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
_TRAILING_QUERY_NOISE_RE = re.compile(rf"(?:\s+{SEARCH_TITLE_NOISE_PATTERN})+$", re.IGNORECASE)


def normalize_spaces(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized.strip())


def normalize_match_key(value: str) -> str:
    cleaned = normalize_spaces(value).lower()
    if not cleaned:
        return ""
    cleaned = re.sub(r"[._:：\-]+", " ", cleaned)
    cleaned = strip_trailing_query_noise(cleaned)
    cleaned = _normalize_sequel_aliases(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def compact_match_key(value: str) -> str:
    return value.replace(" ", "")


def is_confident_title_match(query: str, candidate_title: str) -> bool:
    normalized_query = normalize_match_key(query)
    normalized_candidate = normalize_match_key(candidate_title)
    if not normalized_query or not normalized_candidate:
        return False
    if normalized_candidate == normalized_query:
        return True
    return compact_match_key(normalized_candidate) == compact_match_key(normalized_query) or is_subtitle_extension_match(
        query,
        candidate_title,
    )


def score_title_match(query: str, candidate_title: str) -> int:
    normalized_query = normalize_match_key(query)
    normalized_candidate = normalize_match_key(candidate_title)
    if not normalized_query or not normalized_candidate:
        return 0
    if normalized_candidate == normalized_query:
        return 4
    if is_subtitle_extension_match(query, candidate_title) or normalized_candidate.startswith(normalized_query):
        return 3
    if normalized_query in normalized_candidate:
        return 2
    return 1 if compact_match_key(normalized_candidate) == compact_match_key(normalized_query) else 0


def is_subtitle_extension_match(query: str, candidate_title: str) -> bool:
    normalized_query = normalize_match_key(query)
    normalized_candidate = normalize_match_key(candidate_title)
    if not normalized_query or not normalized_candidate:
        return False
    prefix = f"{normalized_query} "
    if not normalized_candidate.startswith(prefix):
        return False
    suffix = normalized_candidate[len(prefix) :].strip()
    if not suffix:
        return False
    suffix_tokens = suffix.split()
    if len(suffix_tokens) < 2 and not _has_subtitle_separator(candidate_title):
        return False
    return _SEQUEL_SUFFIX_RE.match(suffix) is None


def _has_subtitle_separator(value: str) -> bool:
    return bool(re.search(r"[:：\-]", value))


def finalize_parsed_query_title(
    *,
    cleaned_query: str,
    parsed_title: str,
    parsed_year: str,
) -> str:
    normalized_title = normalize_spaces(parsed_title)
    restored_digit_title = _restore_sequel_digit_title(
        cleaned_query=cleaned_query,
        parsed_title=normalized_title,
        parsed_year=parsed_year,
    )
    restored_noise_title = _restore_trailing_sequel_token_with_noise_title(
        cleaned_query=cleaned_query,
        parsed_title=restored_digit_title,
        parsed_year=parsed_year,
    )
    if restored_noise_title != restored_digit_title:
        return restored_noise_title
    return _restore_trailing_sequel_token_title(
        cleaned_query=cleaned_query,
        parsed_title=restored_digit_title,
        parsed_year=parsed_year,
    )


def strip_trailing_query_noise(value: str) -> str:
    cleaned_value = normalize_spaces(value)
    if not cleaned_value:
        return cleaned_value
    stripped_value = cleaned_value
    while True:
        next_value = normalize_spaces(_TRAILING_QUERY_NOISE_RE.sub("", stripped_value))
        if next_value == stripped_value:
            return stripped_value
        if not next_value or _is_trivial_title_after_noise_strip(next_value):
            return stripped_value
        stripped_value = next_value


def _normalize_sequel_aliases(value: str) -> str:
    normalized = value
    normalized = _CHINESE_PART_PATTERN.sub(lambda match: str(_parse_chinese_part_number(match.group("value"))), normalized)
    normalized = _PART_DIGIT_PATTERN.sub(lambda match: str(_parse_ordinal_token(match.group("value"))), normalized)
    normalized = _CHAPTER_TOKEN_PATTERN.sub(lambda match: str(_parse_ordinal_token(match.group("value"))), normalized)
    for pattern, replacement in _SEQUEL_ALIAS_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    normalized = _TRAILING_ORDINAL_WORD_PATTERN.sub(lambda match: str(_parse_ordinal_token(match.group("value"))), normalized)
    return normalized


def _restore_sequel_digit_title(
    *,
    cleaned_query: str,
    parsed_title: str,
    parsed_year: str,
) -> str:
    if not parsed_title or not parsed_year:
        return parsed_title
    match = _TRAILING_SEQUEL_DIGIT_WITH_YEAR_RE.match(cleaned_query)
    if match is None:
        return parsed_title
    if (match.group("year") or "").strip() != parsed_year:
        return parsed_title
    base_title = normalize_spaces(match.group("title") or "")
    if base_title != parsed_title:
        return parsed_title
    separator = _resolve_query_separator(match, base_title=base_title, sequel=(match.group("sequel") or "").strip())
    sequel = (match.group("sequel") or "").strip()
    return f"{parsed_title}{separator}{sequel}".strip()


def _restore_trailing_sequel_token_title(
    *,
    cleaned_query: str,
    parsed_title: str,
    parsed_year: str,
) -> str:
    match = _TRAILING_SEQUEL_TOKEN_WITH_YEAR_RE.match(cleaned_query)
    if match is None:
        return parsed_title
    if (match.group("year") or "").strip() != parsed_year:
        return parsed_title
    base_title = normalize_spaces(match.group("title") or "")
    sequel = normalize_spaces(match.group("sequel") or "")
    separator = _resolve_query_separator(match, base_title=base_title, sequel=sequel)
    candidate_title = f"{base_title}{separator}{sequel}".strip()
    if candidate_title == parsed_title:
        return parsed_title
    parsed_compact = compact_match_key(normalize_match_key(parsed_title))
    base_compact = compact_match_key(normalize_match_key(base_title))
    candidate_compact = compact_match_key(normalize_match_key(candidate_title))
    if parsed_compact == base_compact:
        return candidate_title
    if separator and parsed_compact == candidate_compact:
        return candidate_title
    return parsed_title


def _restore_trailing_sequel_token_with_noise_title(
    *,
    cleaned_query: str,
    parsed_title: str,
    parsed_year: str,
) -> str:
    match = _TRAILING_SEQUEL_TOKEN_WITH_NOISE_AND_YEAR_RE.match(cleaned_query)
    if match is None:
        return parsed_title
    if (match.group("year") or "").strip() != parsed_year:
        return parsed_title
    base_title = normalize_spaces(match.group("title") or "")
    sequel = normalize_spaces(match.group("sequel") or "")
    if not base_title or not sequel:
        return parsed_title
    separator = _resolve_query_separator(match, base_title=base_title, sequel=sequel)
    return f"{base_title}{separator}{sequel}".strip()


def _is_trivial_title_after_noise_strip(value: str) -> bool:
    tokens = [token for token in normalize_spaces(value).split(" ") if token]
    if not tokens:
        return True
    return len(tokens) == 1 and tokens[0].lower() in {"a", "an", "the"}


def _resolve_query_separator(match: re.Match[str], *, base_title: str, sequel: str) -> str:
    raw_separator = match.group("separator") or ""
    raw_title = match.group("title") or ""
    if (raw_separator or raw_title.endswith(" ")) and _should_preserve_query_separator(base_title, sequel):
        return " "
    return ""


def _should_preserve_query_separator(base_title: str, sequel: str) -> bool:
    _ = sequel
    return bool(re.search(r"[a-z0-9]", base_title, re.IGNORECASE))


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
    word_map = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    if cleaned in word_map:
        return word_map[cleaned]
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
