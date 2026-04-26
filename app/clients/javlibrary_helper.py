from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import quote_plus, urljoin, urlparse

import httpx

from app.services.adult_content import extract_exact_adult_content_match

_TAG_PATTERN = re.compile(r"<[^>]+>")
_TITLE_PATTERN = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
_DETAIL_TITLE_PATTERN = re.compile(
    r"""id=["']video_title["'][^>]*>.*?<a[^>]*>(?P<title>.*?)</a>""",
    re.IGNORECASE | re.DOTALL,
)
_DETAIL_ID_PATTERN = re.compile(
    r"""id=["']video_id["'][^>]*>.*?<td[^>]*class=["']text["'][^>]*>(?P<id>.*?)</td>""",
    re.IGNORECASE | re.DOTALL,
)
_DETAIL_LINK_PATTERN = re.compile(
    r"""<a[^>]+href=["'](?P<href>[^"']*\?v=[^"']+)["'][^>]*(?:title=["'](?P<title>[^"']+)["'])?[^>]*>(?P<text>.*?)</a>""",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class JavLibraryReadOnlyMatch:
    normalized_content_id: str
    display_id: str
    archive_category: str
    title: str
    detail_url: str
    source_site: str = "javlibrary"


class JavLibraryReadOnlyHelperClient:
    def __init__(
        self,
        timeout_seconds: float = 10.0,
        proxy_url: str = "",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._proxy_url = proxy_url.strip()

    async def lookup(self, lookup_text: str) -> JavLibraryReadOnlyMatch | None:
        expected_display_id = _normalize_expected_display_id(lookup_text)
        if not expected_display_id:
            return None

        search_url = _build_search_url(expected_display_id)
        response = await self._get(search_url)
        detail_url = _resolve_detail_url(response=response, expected_display_id=expected_display_id)
        detail_html = response.text
        if detail_url and _normalize_url(str(response.url)) != _normalize_url(detail_url):
            detail_response = await self._get(detail_url)
            detail_html = detail_response.text
            detail_url = str(detail_response.url)
        if not detail_url:
            detail_url = str(response.url)

        return _extract_read_only_match(
            html=detail_html,
            expected_display_id=expected_display_id,
            detail_url=detail_url,
        )

    async def _get(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
            proxy=self._proxy_url or None,
        ) as client:
            response = await client.get(url)
        response.raise_for_status()
        return response


def _build_search_url(display_id: str) -> str:
    encoded_query = quote_plus(display_id)
    return f"https://www.javlibrary.com/tw/vl_searchbyid.php?keyword={encoded_query}"


def _normalize_expected_display_id(lookup_text: str) -> str:
    content_match = extract_exact_adult_content_match(lookup_text, source_site="javlibrary")
    if content_match is None or content_match.archive_category != "censored":
        return ""
    return content_match.display_id.strip().upper()


def _resolve_detail_url(*, response: httpx.Response, expected_display_id: str) -> str:
    response_url = str(response.url)
    parsed_response_url = urlparse(response_url)
    if parsed_response_url.query and "v=" in parsed_response_url.query.lower():
        return response_url

    for matched in _DETAIL_LINK_PATTERN.finditer(response.text):
        title = _clean_html_text(str(matched.group("title") or "")) or _clean_html_text(str(matched.group("text") or ""))
        if not _looks_like_expected_display_id(title, expected_display_id=expected_display_id):
            continue
        href = str(matched.group("href") or "").strip()
        if href:
            return urljoin(response_url, unescape(href))
    return ""


def _extract_read_only_match(
    *,
    html: str,
    expected_display_id: str,
    detail_url: str,
) -> JavLibraryReadOnlyMatch | None:
    detail_id = _extract_detail_id(html) or expected_display_id
    title = _extract_detail_title(html) or detail_id
    content_match = extract_exact_adult_content_match(f"{detail_id} {title}", source_site="javlibrary")
    if content_match is None or content_match.archive_category != "censored":
        return None
    return JavLibraryReadOnlyMatch(
        normalized_content_id=content_match.normalized_content_id,
        display_id=content_match.display_id,
        archive_category=content_match.archive_category,
        title=title,
        detail_url=detail_url.strip(),
    )


def _extract_detail_title(html: str) -> str:
    matched = _DETAIL_TITLE_PATTERN.search(html)
    if matched is not None:
        title = _clean_html_text(str(matched.group("title") or ""))
        if title:
            return title

    matched = _TITLE_PATTERN.search(html)
    if matched is None:
        return ""
    title = _clean_html_text(str(matched.group("title") or ""))
    if not title:
        return ""
    if " - " in title:
        title = title.split(" - ", 1)[0].strip()
    if title.lower().startswith("javlibrary"):
        _, _, trailing = title.partition(" ")
        if trailing.strip():
            title = trailing.strip()
    return title


def _extract_detail_id(html: str) -> str:
    matched = _DETAIL_ID_PATTERN.search(html)
    if matched is None:
        return ""
    detail_id = _clean_html_text(str(matched.group("id") or ""))
    content_match = extract_exact_adult_content_match(detail_id, source_site="javlibrary")
    if content_match is None:
        return ""
    return content_match.display_id


def _looks_like_expected_display_id(text: str, *, expected_display_id: str) -> bool:
    if not text:
        return False
    content_match = extract_exact_adult_content_match(text, source_site="javlibrary")
    if content_match is not None:
        return content_match.display_id == expected_display_id
    return expected_display_id.lower() in text.strip().lower()


def _clean_html_text(value: str) -> str:
    without_tags = _TAG_PATTERN.sub(" ", value)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def _normalize_url(value: str) -> str:
    return value.strip().rstrip("/")
