from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


ADULT_ARCHIVE_CATEGORIES = (
    "fc2",
    "censored",
    "uncensored",
    "chinese_original",
    "western",
    "other_adult",
)

_FC2_PATTERNS = (
    re.compile(r"\bfc2[-_\s]*ppv[-_\s]*(?P<serial>\d{4,10})\b", re.IGNORECASE),
    re.compile(r"\bfc2[-_\s]*(?P<serial>\d{4,10})\b", re.IGNORECASE),
)
_UNCENSORED_PATTERNS = (
    re.compile(r"\b(?P<prefix>carib(?:beancom)?)[-_\s]?(?P<serial>\d{6}[-_]\d{2,4})\b", re.IGNORECASE),
    re.compile(r"\b(?P<prefix>1pon(?:do)?)[-_\s]?(?P<serial>\d{6}[-_]\d{2,4})\b", re.IGNORECASE),
    re.compile(r"\b(?P<prefix>10mu(?:sume)?)[-_\s]?(?P<serial>\d{6}[-_]\d{2,4})\b", re.IGNORECASE),
    re.compile(r"\b(?P<prefix>paco(?:pacomama)?)[-_\s]?(?P<serial>\d{6}[-_]\d{2,4})\b", re.IGNORECASE),
    re.compile(r"\b(?P<prefix>heyzo)[-_\s]?(?P<serial>\d{3,6})\b", re.IGNORECASE),
    re.compile(r"\b(?P<prefix>tokyohot)[-_\s]?(?P<serial>[a-z]{1,4}\d{3,6})\b", re.IGNORECASE),
)
_CENSORED_PATTERN = re.compile(r"\b(?P<prefix>[a-z]{2,10})[-_\s]?(?P<serial>\d{2,6})\b", re.IGNORECASE)
_CHINESE_ORIGINAL_PATTERN = re.compile(
    r"\b(?P<prefix>md|madou|91cm|91mf|xk|swag)[-_\s]?(?P<serial>\d{2,8})\b",
    re.IGNORECASE,
)
_CHINESE_ORIGINAL_KEYWORDS = ("国产", "麻豆", "天美", "果冻", "91", "兔子先生")
_WESTERN_KEYWORDS = ("欧美", "western", "brazzers", "naughtyamerica", "teamskeet", "realitykings")
_UNCENSORED_KEYWORDS = ("无码", "uncensored", "caribbeancom", "caribbean", "1pondo", "10musume", "pacopacomama", "heyzo", "tokyohot")
_FC2_KEYWORDS = ("fc2", "ppv")
_CENSORED_KEYWORDS = ("有码", "jav", "javbus", "javlibrary")
_NOISE_PATTERN = re.compile(r"[^0-9a-z]+", re.IGNORECASE)
_UNCENSORED_PREFIX_ALIASES = {
    "carib": "carib",
    "caribbeancom": "carib",
    "1pon": "1pon",
    "1pondo": "1pon",
    "10mu": "10mu",
    "10musume": "10mu",
    "paco": "paco",
    "pacopacomama": "paco",
}
_SEPARATOR_TRANSLATION = str.maketrans(
    {
        "—": "-",
        "–": "-",
        "−": "-",
        "ー": "-",
        "＿": "_",
    }
)


@dataclass(frozen=True, slots=True)
class AdultContentMatch:
    normalized_content_id: str
    archive_category: str
    source_kind: str
    display_id: str


def extract_adult_content_match(text: str, *, source_site: str = "") -> AdultContentMatch | None:
    cleaned_text = _normalize_match_text(text)
    if not cleaned_text:
        return None

    fc2_match = _match_fc2(cleaned_text)
    if fc2_match is not None:
        return fc2_match

    uncensored_match = _match_uncensored(cleaned_text)
    if uncensored_match is not None:
        return uncensored_match

    chinese_original_match = _match_chinese_original(cleaned_text)
    if chinese_original_match is not None:
        return chinese_original_match

    censored_match = _match_censored(cleaned_text)
    if censored_match is not None:
        return censored_match

    fallback_category = guess_adult_archive_category(cleaned_text, source_site=source_site)
    if fallback_category == "other_adult":
        return None
    fallback_id = build_fallback_content_id(cleaned_text, category=fallback_category)
    return AdultContentMatch(
        normalized_content_id=fallback_id,
        archive_category=fallback_category,
        source_kind=fallback_category,
        display_id=fallback_id,
    )


def guess_adult_archive_category(text: str, *, source_site: str = "") -> str:
    normalized_text = _normalize_compact_text(text)
    normalized_site = _normalize_compact_text(source_site)
    if any(keyword in normalized_text for keyword in _FC2_KEYWORDS):
        return "fc2"
    if any(keyword in normalized_text for keyword in _UNCENSORED_KEYWORDS):
        return "uncensored"
    if any(keyword in normalized_text for keyword in _CHINESE_ORIGINAL_KEYWORDS):
        return "chinese_original"
    if any(keyword in normalized_text for keyword in _WESTERN_KEYWORDS):
        return "western"
    if normalized_site in {"javbus", "javlibrary"}:
        return "censored"
    if normalized_site in {"tokyotosho", "sukebei"}:
        return "other_adult"
    if any(keyword in normalized_text for keyword in _CENSORED_KEYWORDS):
        return "censored"
    return "other_adult"


def build_fallback_content_id(text: str, *, category: str) -> str:
    normalized_text = _normalize_compact_text(text)
    compact = _NOISE_PATTERN.sub("", normalized_text)
    if not compact:
        compact = "unknown"
    return f"{category}:{compact[:64]}"


def _match_fc2(text: str) -> AdultContentMatch | None:
    for pattern in _FC2_PATTERNS:
        matched = pattern.search(text)
        if matched is None:
            continue
        serial = str(matched.group("serial") or "").strip()
        if not serial:
            continue
        display_id = f"FC2-{serial}"
        return AdultContentMatch(
            normalized_content_id=f"fc2:{serial}",
            archive_category="fc2",
            source_kind="fc2",
            display_id=display_id,
        )
    return None


def _match_uncensored(text: str) -> AdultContentMatch | None:
    for pattern in _UNCENSORED_PATTERNS:
        matched = pattern.search(text)
        if matched is None:
            continue
        prefix = _canonicalize_uncensored_prefix(str(matched.group("prefix") or ""))
        serial = _normalize_uncensored_serial(str(matched.group("serial") or ""))
        if not prefix or not serial:
            continue
        display_id = f"{prefix.upper()}-{serial}"
        return AdultContentMatch(
            normalized_content_id=f"{prefix}:{serial}",
            archive_category="uncensored",
            source_kind="uncensored",
            display_id=display_id,
        )
    return None


def _match_chinese_original(text: str) -> AdultContentMatch | None:
    matched = _CHINESE_ORIGINAL_PATTERN.search(text)
    if matched is not None:
        prefix = _normalize_compact_text(str(matched.group("prefix") or ""))
        serial = str(matched.group("serial") or "").strip()
        if prefix and serial:
            display_id = f"{prefix.upper()}-{serial}"
            return AdultContentMatch(
                normalized_content_id=f"cn:{prefix}-{serial}",
                archive_category="chinese_original",
                source_kind="chinese_original",
                display_id=display_id,
            )
    normalized_text = _normalize_compact_text(text)
    if any(keyword in normalized_text for keyword in _CHINESE_ORIGINAL_KEYWORDS):
        fallback_id = build_fallback_content_id(text, category="chinese_original")
        return AdultContentMatch(
            normalized_content_id=fallback_id,
            archive_category="chinese_original",
            source_kind="chinese_original",
            display_id=fallback_id,
        )
    return None


def _match_censored(text: str) -> AdultContentMatch | None:
    matched = _CENSORED_PATTERN.search(text)
    if matched is None:
        return None
    prefix = _normalize_compact_text(str(matched.group("prefix") or ""))
    serial = str(matched.group("serial") or "").strip()
    if not prefix or not serial:
        return None
    if prefix in {"fc2", "carib", "caribbeancom", "1pon", "1pondo", "10mu", "10musume", "paco", "pacopacomama", "heyzo", "tokyohot"}:
        return None
    if prefix in {"s", "e", "ep", "vol"}:
        return None
    display_id = f"{prefix.upper()}-{serial}"
    return AdultContentMatch(
        normalized_content_id=f"censored:{prefix}-{serial}",
        archive_category="censored",
        source_kind="censored",
        display_id=display_id,
    )


def _normalize_compact_text(value: str) -> str:
    normalized = _normalize_match_text(value)
    return re.sub(r"\s+", "", normalized).lower()


def _normalize_uncensored_serial(value: str) -> str:
    cleaned = _normalize_match_text(value).replace("_", "-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned.strip("-")


def _normalize_match_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return normalized.translate(_SEPARATOR_TRANSLATION).strip()


def _canonicalize_uncensored_prefix(value: str) -> str:
    prefix = _normalize_compact_text(value)
    return _UNCENSORED_PREFIX_ALIASES.get(prefix, prefix)
