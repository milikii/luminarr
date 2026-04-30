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
_DETAIL_POSTER_PATTERN = re.compile(
    r"""id=["']video_jacket_img["'][^>]*src=["'](?P<src>[^"']+)["']""",
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
    poster_url: str = ""
    release_date: str = ""
    runtime: str = ""
    duration: str = ""
    maker: str = ""
    studio: str = ""
    label: str = ""
    series: str = ""
    director: str = ""
    genres: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()


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
        poster_url=_extract_detail_poster_url(html, detail_url=detail_url),
        release_date=_extract_detail_field(html, "video_date", "发行日期", "發行日期", "発売日"),
        runtime=_extract_detail_field(html, "video_length", "长度", "長度", "収録時間"),
        duration=_extract_detail_field(html, "video_length", "长度", "長度", "収録時間"),
        maker=_extract_detail_field(html, "video_maker", "制作商", "製作商", "メーカー"),
        studio=_extract_detail_field(html, "video_maker", "制作商", "製作商", "メーカー"),
        label=_extract_detail_field(html, "video_label", "厂牌", "レーベル"),
        series=_extract_detail_field(html, "video_series", "系列", "シリーズ"),
        director=_extract_detail_field(html, "video_director", "导演", "導演", "監督"),
        genres=_extract_detail_genres(html),
        actors=_extract_detail_actors(html),
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


def _extract_detail_poster_url(html: str, *, detail_url: str) -> str:
    matched = _DETAIL_POSTER_PATTERN.search(html)
    if matched is None:
        return ""
    poster_url = str(matched.group("src") or "").strip()
    if not poster_url:
        return ""
    return urljoin(detail_url, unescape(poster_url))


def _extract_detail_field(html: str, element_id: str, *label_aliases: str) -> str:
    pattern = re.compile(
        rf"""id=["']{re.escape(element_id)}["'][^>]*>(?P<html>.*?)</div>""",
        re.IGNORECASE | re.DOTALL,
    )
    matched = pattern.search(html)
    if matched is not None:
        return _strip_detail_field_label(_clean_html_text(str(matched.group("html") or "")))

    for label in label_aliases:
        labeled_value = _extract_sibling_text_after_label(html, label)
        if labeled_value:
            return labeled_value
    return ""


def _extract_sibling_text_after_label(html: str, label: str) -> str:
    pattern = re.compile(
        rf""">(?:\s*){re.escape(label)}\s*[:：]?(?:\s*)</[^>]+>\s*<[^>]*class=["']text["'][^>]*>(?P<html>.*?)</[^>]+>""",
        re.IGNORECASE | re.DOTALL,
    )
    matched = pattern.search(html)
    if matched is None:
        return ""
    return _clean_html_text(str(matched.group("html") or ""))


def _extract_detail_actors(html: str) -> tuple[str, ...]:
    actor_values = _extract_detail_link_values(html, "video_cast")
    if actor_values:
        return actor_values
    star_values = tuple(_clean_html_text(value) for value in re.findall(r"""class=["']star["'][^>]*>.*?<a[^>]*>(.*?)</a>""", html, flags=re.IGNORECASE | re.DOTALL))
    star_values = tuple(value for value in star_values if value)
    if star_values:
        return star_values
    actor_text = _extract_detail_field(html, "video_cast", "演员", "演員", "女優")
    if not actor_text:
        return ()
    parts = [part.strip() for part in re.split(r"[,，/]+", actor_text) if part.strip()]
    return tuple(parts or (actor_text,))


def _extract_detail_genres(html: str) -> tuple[str, ...]:
    genre_values = _extract_detail_link_values(html, "video_genres")
    if genre_values:
        return genre_values
    genre_text = _extract_detail_field(html, "video_genres", "类别", "類別", "ジャンル")
    if not genre_text:
        return ()
    return tuple(part.strip() for part in re.split(r"[,，/ ]+", genre_text) if part.strip())


def _extract_detail_link_values(html: str, element_id: str) -> tuple[str, ...]:
    container_pattern = re.compile(
        rf"""id=["']{re.escape(element_id)}["'][^>]*>(?P<html>.*?)</div>""",
        re.IGNORECASE | re.DOTALL,
    )
    matched = container_pattern.search(html)
    if matched is None:
        return ()
    values = tuple(
        _clean_html_text(value)
        for value in re.findall(r"<a\b[^>]*>(?P<text>.*?)</a>", str(matched.group("html") or ""), flags=re.IGNORECASE | re.DOTALL)
    )
    return tuple(value for value in values if value)


def _strip_detail_field_label(text: str) -> str:
    return re.sub(
        r"^(?:发行日期|發行日期|発売日|长度|長度|収録時間|制作商|製作商|メーカー|厂牌|レーベル|系列|シリーズ|导演|導演|監督|演员|演員|女優)\s*[:：]?\s*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    ).strip()


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
