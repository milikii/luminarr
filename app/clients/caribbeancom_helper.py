from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin

import httpx

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.services.adult_content import extract_exact_adult_content_match

_TAG_PATTERN = re.compile(r"<[^>]+>")
_TITLE_PATTERN = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
_H1_PATTERN = re.compile(r"<h1[^>]*>(?P<title>.*?)</h1>", re.IGNORECASE | re.DOTALL)
_OG_IMAGE_PATTERN = re.compile(
    r"""<meta\b[^>]*\bproperty=["']og:image["'][^>]*\bcontent=["'](?P<url>[^"']+)["']""",
    re.IGNORECASE | re.DOTALL,
)


class CaribbeancomReadOnlyHelperClient:
    """Read exact Caribbeancom metadata from direct movie pages."""

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        proxy_url: str = "",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._proxy_url = proxy_url.strip()

    async def lookup(self, lookup_text: str) -> JavLibraryReadOnlyMatch | None:
        content_match = extract_exact_adult_content_match(lookup_text, source_site="caribbeancom")
        if content_match is None or content_match.normalized_content_id.split(":", 1)[0] != "carib":
            return None

        serial = content_match.normalized_content_id.split(":", 1)[1]
        detail_url = f"https://www.caribbeancom.com/moviepages/{serial}/index.html"
        response = await self._get(detail_url)
        title = _extract_title(response.text) or content_match.display_id
        confirmed_match = extract_exact_adult_content_match(f"{content_match.display_id} {title}", source_site="caribbeancom")
        if confirmed_match is None or confirmed_match.normalized_content_id != content_match.normalized_content_id:
            return None
        return JavLibraryReadOnlyMatch(
            normalized_content_id=confirmed_match.normalized_content_id,
            display_id=confirmed_match.display_id,
            archive_category=confirmed_match.archive_category,
            title=title,
            detail_url=str(response.url).strip(),
            source_site="caribbeancom",
            poster_url=_extract_poster_url(response.text, detail_url=str(response.url)),
            release_date=_extract_release_date(response.text),
            runtime=_extract_runtime(response.text),
            duration=_extract_runtime(response.text),
            actors=_extract_actors(response.text),
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


def _extract_title(html: str) -> str:
    matched = _H1_PATTERN.search(html) or _TITLE_PATTERN.search(html)
    if matched is None:
        return ""
    title = _clean_html_text(str(matched.group("title") or ""))
    if " - " in title:
        title = title.split(" - ", 1)[0].strip()
    return title


def _extract_poster_url(html: str, *, detail_url: str) -> str:
    matched = _OG_IMAGE_PATTERN.search(html)
    if matched is None:
        return ""
    poster_url = str(matched.group("url") or "").strip()
    if not poster_url:
        return ""
    return urljoin(detail_url, unescape(poster_url))


def _extract_release_date(html: str) -> str:
    for pattern in (
        r"""class=["'][^"']*release-date[^"']*["'][^>]*>(?P<value>.*?)</[^>]+>""",
        r"""(?:Release Date|配信日|発売日)\s*[:：]?\s*</[^>]+>\s*<[^>]+>(?P<value>.*?)</[^>]+>""",
    ):
        matched = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if matched is not None:
            return _clean_html_text(str(matched.group("value") or ""))
    return ""


def _extract_runtime(html: str) -> str:
    for pattern in (
        r"""class=["'][^"']*(?:movie-info|runtime|duration)[^"']*["'][^>]*>(?P<value>[^<]*\d+\s*(?:min|minutes|分|分鐘)[^<]*)</[^>]+>""",
        r"""(?:Runtime|収録時間|再生時間)\s*[:：]?\s*</[^>]+>\s*<[^>]+>(?P<value>.*?)</[^>]+>""",
    ):
        matched = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if matched is not None:
            return _clean_html_text(str(matched.group("value") or ""))
    return ""


def _extract_actors(html: str) -> tuple[str, ...]:
    values = tuple(
        _clean_html_text(value)
        for value in re.findall(
            r"""<a\b[^>]*href=["'][^"']*/actress/[^"']*["'][^>]*>(?P<value>.*?)</a>""",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )
    return tuple(dict.fromkeys(value for value in values if value))


def _clean_html_text(value: str) -> str:
    without_tags = _TAG_PATTERN.sub(" ", value)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()
