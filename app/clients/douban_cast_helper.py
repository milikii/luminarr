from __future__ import annotations

import re
from collections.abc import Mapping
from html import unescape
from urllib.parse import quote

import httpx

from app.services.domestic_cast_enrichment import DomesticCastMatch

_CAST_ROW_PATTERN = re.compile(
    r"""<li\b(?P<attrs>[^>]*)>(?P<html>.*?)</li>""",
    re.IGNORECASE | re.DOTALL,
)
_NAME_PATTERN = re.compile(
    r"""<a\b[^>]*title=["'](?P<title>[^"']+)["'][^>]*>(?P<text>.*?)</a>""",
    re.IGNORECASE | re.DOTALL,
)
_ROLE_PATTERN = re.compile(
    r"""<span\b[^>]*class=["'][^"']*role[^"']*["'][^>]*title=["'](?P<title>[^"']+)["'][^>]*>(?P<text>.*?)</span>""",
    re.IGNORECASE | re.DOTALL,
)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_ORIGINAL_NAME_ATTR_PATTERN = re.compile(r"""data-original-name=["'](?P<value>[^"']*)["']""", re.IGNORECASE)
_BROWSER_REQUEST_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
_BROWSER_REQUEST_ACCEPT_LANGUAGE = "zh-CN,zh;q=0.9,en;q=0.8"
_BROWSER_REQUEST_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)


class DoubanCastHelperClient:
    """Best-effort Douban lookup for localized cast names and role text."""

    def __init__(
        self,
        *,
        base_url: str = "https://movie.douban.com",
        timeout_seconds: float = 8.0,
        proxy_url: str = "",
    ) -> None:
        self._base_url = base_url.strip().rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._proxy_url = proxy_url.strip()
        self._request_headers = _build_browser_request_headers(self._base_url)

    async def lookup(self, title: str, original_title: str, year: str) -> tuple[DomesticCastMatch, ...]:
        """Resolve localized cast rows for the confirmed title/original-title pair."""

        for query in _iter_lookup_queries(title=title, original_title=original_title):
            suggestions = await self._get_json(_build_suggest_url(self._base_url, query))
            subject_id = _select_subject_id(suggestions, query=query, year=year)
            if not subject_id:
                continue
            html = await self._get_text(_build_subject_url(self._base_url, subject_id))
            matches = _parse_cast_rows(html)
            if matches:
                return matches
        return ()

    async def _get_json(self, url: str) -> list[Mapping[str, object]]:
        response = await self._get(url)
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("douban subject suggest payload must be a list")
        return [item for item in payload if isinstance(item, Mapping)]

    async def _get_text(self, url: str) -> str:
        response = await self._get(url)
        return response.text

    async def _get(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
            proxy=self._proxy_url or None,
            headers=self._request_headers,
        ) as client:
            response = await client.get(url)
        response.raise_for_status()
        return response


def _iter_lookup_queries(*, title: str, original_title: str) -> tuple[str, ...]:
    queries: list[str] = []
    seen_queries: set[str] = set()
    for raw_query in (title, original_title):
        cleaned_query = raw_query.strip()
        if not cleaned_query:
            continue
        normalized_query = cleaned_query.casefold()
        if normalized_query in seen_queries:
            continue
        seen_queries.add(normalized_query)
        queries.append(cleaned_query)
    return tuple(queries)


def _build_suggest_url(base_url: str, query: str) -> str:
    return f"{base_url}/j/subject_suggest?q={quote(query)}"


def _build_subject_url(base_url: str, subject_id: str) -> str:
    return f"{base_url}/subject/{subject_id}/?dt_dapp=1"


def _build_browser_request_headers(base_url: str) -> dict[str, str]:
    return {
        "User-Agent": _BROWSER_REQUEST_USER_AGENT,
        "Accept": _BROWSER_REQUEST_ACCEPT,
        "Accept-Language": _BROWSER_REQUEST_ACCEPT_LANGUAGE,
        "Referer": f"{base_url}/",
    }


def _select_subject_id(
    suggestions: list[Mapping[str, object]],
    *,
    query: str,
    year: str,
) -> str:
    normalized_query = _normalize_text(query)
    normalized_year = year.strip()
    for suggestion in suggestions:
        suggestion_year = str(suggestion.get("year", "")).strip()
        if normalized_year and suggestion_year and suggestion_year != normalized_year:
            continue
        candidate_titles = {
            _normalize_text(str(suggestion.get("title", ""))),
            _normalize_text(str(suggestion.get("sub_title", ""))),
            _normalize_text(str(suggestion.get("original_title", ""))),
            _normalize_text(str(suggestion.get("ori_title", ""))),
        }
        if normalized_query not in candidate_titles:
            continue
        subject_id = str(suggestion.get("id", "")).strip()
        if subject_id:
            return subject_id
    return ""


def _parse_cast_rows(html: str) -> tuple[DomesticCastMatch, ...]:
    matches: list[DomesticCastMatch] = []
    for order, matched in enumerate(_CAST_ROW_PATTERN.finditer(html)):
        attrs = str(matched.group("attrs") or "")
        if "celebrity" not in attrs.casefold():
            continue
        row_html = str(matched.group("html") or "")
        original_name_match = _ORIGINAL_NAME_ATTR_PATTERN.search(attrs)
        original_name = _clean_html_text(str(original_name_match.group("value") or "")) if original_name_match else ""
        name_matched = _NAME_PATTERN.search(row_html)
        role_matched = _ROLE_PATTERN.search(row_html)
        localized_name = ""
        if name_matched is not None:
            localized_name = _clean_html_text(str(name_matched.group("title") or "")) or _clean_html_text(
                str(name_matched.group("text") or "")
            )
        localized_character = ""
        if role_matched is not None:
            localized_character = _strip_role_prefix(
                _clean_html_text(str(role_matched.group("title") or ""))
                or _clean_html_text(str(role_matched.group("text") or ""))
            )
        if not localized_name and not localized_character:
            continue
        matches.append(
            DomesticCastMatch(
                order=order,
                original_name=original_name,
                localized_name=localized_name,
                localized_character=localized_character,
            )
        )
    return tuple(matches)


def _strip_role_prefix(value: str) -> str:
    cleaned_value = value.strip()
    if cleaned_value.startswith(("饰 ", "飾 ")):
        return cleaned_value[2:].strip()
    if cleaned_value.startswith(("饰", "飾")):
        return cleaned_value[1:].strip()
    return cleaned_value


def _clean_html_text(value: str) -> str:
    cleaned_value = unescape(_TAG_PATTERN.sub(" ", value))
    return " ".join(cleaned_value.split())


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()
