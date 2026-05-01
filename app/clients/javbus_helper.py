from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote_plus, urljoin, urlparse

import httpx

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.services.adult_content import extract_exact_adult_content_match

JavBusReadOnlyMatch = JavLibraryReadOnlyMatch

_TAG_PATTERN = re.compile(r"<[^>]+>")
_TITLE_PATTERN = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
_H3_PATTERN = re.compile(r"<h3[^>]*>(?P<title>.*?)</h3>", re.IGNORECASE | re.DOTALL)
_P_ROW_PATTERN = re.compile(r"<p\b(?P<attrs>[^>]*)>(?P<html>.*?)</p>", re.IGNORECASE | re.DOTALL)
_CLASS_ATTR_PATTERN = re.compile(r"""\bclass\s*=\s*["'](?P<classes>[^"']+)["']""", re.IGNORECASE)
_HEADER_LABEL_PATTERN = re.compile(
    r"""<span\b[^>]*\bclass=["'][^"']*\bheader\b[^"']*["'][^>]*>(?P<label>.*?)</span>""",
    re.IGNORECASE | re.DOTALL,
)
_IMAGE_PATTERN = re.compile(r"""<img\b[^>]*\bsrc=["'](?P<src>[^"']+)["']""", re.IGNORECASE | re.DOTALL)


class JavBusReadOnlyHelperClient:
    def __init__(
        self,
        timeout_seconds: float = 10.0,
        proxy_url: str = "",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._proxy_url = proxy_url.strip()

    async def lookup(self, lookup_text: str) -> JavBusReadOnlyMatch | None:
        expected_display_id = _normalize_expected_display_id(lookup_text)
        if not expected_display_id:
            return None

        search_url = _build_search_url(expected_display_id)
        response = await self._get(search_url)
        detail_url = _resolve_detail_url(response=response, expected_display_id=expected_display_id)
        if not detail_url:
            return None

        detail_html = response.text
        if _normalize_url(str(response.url)) != _normalize_url(detail_url):
            detail_response = await self._get(detail_url)
            detail_html = detail_response.text
            detail_url = str(detail_response.url)

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
    return f"https://www.javbus.com/search/{encoded_query}"


def _normalize_expected_display_id(lookup_text: str) -> str:
    content_match = extract_exact_adult_content_match(lookup_text, source_site="javbus")
    if content_match is None or content_match.archive_category != "censored":
        return ""
    return content_match.display_id.strip().upper()


def _resolve_detail_url(*, response: httpx.Response, expected_display_id: str) -> str:
    response_url = str(response.url)
    if _is_detail_url(response_url, expected_display_id=expected_display_id):
        return response_url

    for attrs, inner_html in _iter_anchor_blocks_with_class(response.text, "movie-box"):
        if not _looks_like_expected_display_id(_clean_html_text(inner_html), expected_display_id=expected_display_id):
            continue
        href = _extract_attr(attrs, "href")
        if href:
            return urljoin(response_url, unescape(href))
    return ""


def _extract_read_only_match(
    *,
    html: str,
    expected_display_id: str,
    detail_url: str,
) -> JavBusReadOnlyMatch | None:
    detail_id = _extract_detail_id(html) or expected_display_id
    title = _extract_detail_title(html) or detail_id
    content_match = extract_exact_adult_content_match(f"{detail_id} {title}", source_site="javbus")
    if (
        content_match is None
        or content_match.archive_category != "censored"
        or content_match.display_id != expected_display_id
    ):
        return None
    runtime = _extract_detail_field(html, "长度", "長度", "时长", "時長", "収録時間")
    maker = _extract_detail_field(html, "制作商", "製作商", "メーカー")
    return JavBusReadOnlyMatch(
        normalized_content_id=content_match.normalized_content_id,
        display_id=content_match.display_id,
        archive_category=content_match.archive_category,
        title=title,
        detail_url=detail_url.strip(),
        source_site="javbus",
        poster_url=_extract_detail_poster_url(html, detail_url=detail_url),
        release_date=_extract_detail_field(html, "发行时间", "發行時間", "发行日期", "發行日期", "発売日"),
        runtime=runtime,
        duration=runtime,
        maker=maker,
        studio=maker,
        label=_extract_detail_field(html, "发行商", "發行商", "厂牌", "廠牌", "レーベル"),
        series=_extract_detail_field(html, "系列", "シリーズ"),
        director=_extract_detail_field(html, "导演", "導演", "監督"),
        genres=_extract_detail_genres(html),
        actors=_extract_detail_actors(html),
    )


def _extract_detail_title(html: str) -> str:
    matched = _H3_PATTERN.search(html)
    if matched is not None:
        title = _clean_html_text(str(matched.group("title") or ""))
        if title:
            return title

    matched = _TITLE_PATTERN.search(html)
    if matched is None:
        return ""
    title = _clean_html_text(str(matched.group("title") or ""))
    if " - " in title:
        title = title.split(" - ", 1)[0].strip()
    return title


def _extract_detail_id(html: str) -> str:
    detail_id = _extract_detail_field(html, "识别码", "識別碼", "品番", "番号", "ID")
    content_match = extract_exact_adult_content_match(detail_id, source_site="javbus")
    if content_match is None:
        return ""
    return content_match.display_id


def _extract_detail_poster_url(html: str, *, detail_url: str) -> str:
    for attrs, inner_html in _iter_anchor_blocks_with_class(html, "bigImage"):
        href = _extract_attr(attrs, "href")
        if href:
            return urljoin(detail_url, unescape(href))
        image_url = _extract_first_image_url(inner_html)
        if image_url:
            return urljoin(detail_url, unescape(image_url))
    return _extract_first_image_url(html, base_url=detail_url)


def _extract_detail_field(html: str, *label_aliases: str) -> str:
    row_html = _extract_detail_field_html(html, *label_aliases)
    if not row_html:
        return ""
    return _clean_html_text(_HEADER_LABEL_PATTERN.sub(" ", row_html, count=1))


def _extract_detail_field_html(html: str, *label_aliases: str) -> str:
    normalized_aliases = {_normalize_label(label) for label in label_aliases}
    rows = tuple(
        (str(matched.group("attrs") or ""), str(matched.group("html") or ""))
        for matched in _P_ROW_PATTERN.finditer(html)
    )
    for row_index, (attrs, row_html) in enumerate(rows):
        label_match = _HEADER_LABEL_PATTERN.search(row_html)
        if label_match is not None:
            label = _normalize_label(_clean_html_text(str(label_match.group("label") or "")))
            if label in normalized_aliases:
                value_html = _HEADER_LABEL_PATTERN.sub(" ", row_html, count=1)
                if not _clean_html_text(value_html) and row_index + 1 < len(rows):
                    return rows[row_index + 1][1]
                return row_html
            continue

        if not _has_html_class(attrs, "header"):
            continue
        label = _normalize_label(_clean_html_text(row_html))
        if label in normalized_aliases and row_index + 1 < len(rows):
            return rows[row_index + 1][1]
    return ""


def _extract_detail_genres(html: str) -> tuple[str, ...]:
    row_html = _extract_detail_field_html(html, "类别", "類別", "ジャンル")
    if row_html:
        values = _extract_link_values(row_html)
        if values:
            return values
        return _split_metadata_values(_extract_detail_field(html, "类别", "類別", "ジャンル"))
    return ()


def _extract_detail_actors(html: str) -> tuple[str, ...]:
    actor_values: list[str] = []
    for _, inner_html in _iter_anchor_blocks_with_class(html, "avatar-box"):
        span_values = re.findall(r"<span\b[^>]*>(?P<text>.*?)</span>", inner_html, flags=re.IGNORECASE | re.DOTALL)
        if span_values:
            actor_values.extend(_clean_html_text(value) for value in span_values)
            continue
        actor_values.append(_clean_html_text(inner_html))
    actor_values = [value for value in actor_values if value]
    if actor_values:
        return _dedupe_texts(actor_values)
    return _split_metadata_values(_extract_detail_field(html, "演员", "演員", "女優"))


def _extract_link_values(html: str) -> tuple[str, ...]:
    values = tuple(
        _clean_html_text(value)
        for value in re.findall(r"<a\b[^>]*>(?P<text>.*?)</a>", html, flags=re.IGNORECASE | re.DOTALL)
    )
    return tuple(value for value in values if value)


def _extract_first_image_url(html: str, *, base_url: str = "") -> str:
    matched = _IMAGE_PATTERN.search(html)
    if matched is None:
        return ""
    image_url = str(matched.group("src") or "").strip()
    if not image_url:
        return ""
    if base_url:
        return urljoin(base_url, unescape(image_url))
    return image_url


def _iter_anchor_blocks_with_class(html: str, class_name: str) -> tuple[tuple[str, str], ...]:
    pattern = re.compile(
        rf"""<a\b(?P<attrs>[^>]*\bclass=["'][^"']*\b{re.escape(class_name)}\b[^"']*["'][^>]*)>(?P<html>.*?)</a>""",
        re.IGNORECASE | re.DOTALL,
    )
    return tuple((str(matched.group("attrs") or ""), str(matched.group("html") or "")) for matched in pattern.finditer(html))


def _extract_attr(attrs: str, key: str) -> str:
    matched = re.search(rf"""\b{re.escape(key)}=["'](?P<value>[^"']+)["']""", attrs, flags=re.IGNORECASE)
    if matched is None:
        return ""
    return str(matched.group("value") or "").strip()


def _clean_html_text(value: str) -> str:
    text = _TAG_PATTERN.sub(" ", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_label(value: str) -> str:
    return re.sub(r"[\s:：]+", "", value).strip().lower()


def _has_html_class(attrs: str, class_name: str) -> bool:
    matched = _CLASS_ATTR_PATTERN.search(attrs)
    if matched is None:
        return False
    classes = {item.strip().lower() for item in str(matched.group("classes") or "").split() if item.strip()}
    return class_name.lower() in classes


def _split_metadata_values(value: str) -> tuple[str, ...]:
    parts = [part.strip() for part in re.split(r"[,，/]+", value) if part.strip()]
    return tuple(parts)


def _dedupe_texts(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned_value = value.strip()
        if not cleaned_value or cleaned_value in seen:
            continue
        seen.add(cleaned_value)
        ordered.append(cleaned_value)
    return tuple(ordered)


def _looks_like_expected_display_id(text: str, *, expected_display_id: str) -> bool:
    return expected_display_id in text.upper()


def _is_detail_url(url: str, *, expected_display_id: str) -> bool:
    parsed = urlparse(url)
    if "/search/" in parsed.path.lower():
        return False
    return parsed.path.rstrip("/").upper().endswith(f"/{expected_display_id}")


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower()).geturl()
