from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import parse_qs, parse_qsl, quote_plus, urlencode, urljoin, urlparse, urlunparse

import httpx

_ROW_PATTERN = re.compile(r"<tr\b[^>]*>(?P<html>.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL_PATTERN = re.compile(r"<t[dh]\b[^>]*>(?P<html>.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
_TITLE_ATTR_PATTERN = re.compile(
    r"""href=["'][^"']*/view/\d+(?:#[^"']*)?["'][^>]*title=["'](?P<title>[^"']+)["']""",
    re.IGNORECASE | re.DOTALL,
)
_TITLE_LINK_PATTERN = re.compile(
    r"""<a[^>]+href=["'][^"']*/view/\d+(?:#[^"']*)?["'][^>]*>(?P<title>.*?)</a>""",
    re.IGNORECASE | re.DOTALL,
)
_MAGNET_PATTERN = re.compile(r"""href=["'](?P<link>magnet:\?[^"']+)["']""", re.IGNORECASE)
_TORRENT_PATTERN = re.compile(r"""href=["'](?P<link>[^"']+\.torrent(?:\?[^"']*)?)["']""", re.IGNORECASE)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_SIZE_PATTERN = re.compile(r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>tib|gib|mib|kib|tb|gb|mb|kb|b)\b", re.IGNORECASE)
_PAGE_NUMBER_TOKEN_PATTERN = re.compile(r"^p=(?P<page>[1-9]\d*)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class WebSourceRule:
    name: str
    base_url: str
    search_path_template: str


class UnsupportedWebSourcePageError(ValueError):
    pass


NYAA_RULE = WebSourceRule(
    name="nyaa",
    base_url="https://nyaa.si",
    search_path_template="/?f=0&c=0_0&q={query}",
)

SUPPORTED_WEB_SOURCE_RULES: dict[str, WebSourceRule] = {
    NYAA_RULE.name: NYAA_RULE,
}


class WebSourceClient:
    def __init__(
        self,
        rule: WebSourceRule,
        timeout_seconds: float = 10.0,
        proxy_url: str = "",
    ) -> None:
        self._rule = rule
        self._timeout_seconds = timeout_seconds
        self._proxy_url = proxy_url.strip()

    @property
    def name(self) -> str:
        return self._rule.name

    async def search(self, query: str) -> list[Mapping[str, Any]]:
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        try:
            response = await self._get(self._build_search_url(cleaned_query))
        except Exception as error:
            _log_web_source_error(source_name=self._rule.name, query=cleaned_query, error=error)
            return []

        return parse_web_source_html(response.text, rule=self._rule)

    async def search_page(self, page_url: str) -> list[Mapping[str, Any]]:
        cleaned_page_url = page_url.strip()
        if not cleaned_page_url:
            return []
        if not is_supported_web_source_page_url(cleaned_page_url, rule=self._rule):
            raise UnsupportedWebSourcePageError(cleaned_page_url)

        try:
            response = await self._get(cleaned_page_url)
        except Exception as error:
            _log_web_source_error(source_name=self._rule.name, query=cleaned_page_url, error=error)
            return []

        return parse_web_source_html(response.text, rule=self._rule)

    def _build_search_url(self, query: str) -> str:
        encoded_query = quote_plus(query)
        path = self._rule.search_path_template.format(query=encoded_query)
        return f"{self._rule.base_url}{path}"

    async def _get(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
            proxy=self._proxy_url or None,
        ) as client:
            response = await client.get(url)
        response.raise_for_status()
        return response


def looks_like_http_url(text: str) -> bool:
    cleaned_text = text.strip()
    if not cleaned_text:
        return False
    if any(character.isspace() for character in cleaned_text):
        return False
    parsed = urlparse(cleaned_text)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_supported_web_source_page_url(url: str, *, rule: WebSourceRule | None = None) -> bool:
    cleaned_url = url.strip()
    if not looks_like_http_url(cleaned_url):
        return False

    if rule is not None:
        return _is_supported_page_url_for_rule(cleaned_url, rule=rule)
    return any(_is_supported_page_url_for_rule(cleaned_url, rule=item) for item in SUPPORTED_WEB_SOURCE_RULES.values())


def looks_like_web_source_page_request(text: str) -> bool:
    cleaned_text = text.strip()
    if looks_like_http_url(cleaned_text):
        return True

    base_url, separator, page_token = cleaned_text.rpartition(" ")
    return bool(separator and looks_like_http_url(base_url) and _PAGE_NUMBER_TOKEN_PATTERN.fullmatch(page_token))


def resolve_supported_web_source_page_request(text: str) -> str | None:
    cleaned_text = text.strip()
    if not cleaned_text:
        return None
    if looks_like_http_url(cleaned_text):
        return cleaned_text if is_supported_web_source_page_url(cleaned_text) else None

    base_url, separator, page_token = cleaned_text.rpartition(" ")
    if not separator or not looks_like_http_url(base_url):
        return None
    matched = _PAGE_NUMBER_TOKEN_PATTERN.fullmatch(page_token)
    if matched is None:
        return None

    resolved_page_url = _replace_page_number(base_url, page_number=str(matched.group("page") or "").strip())
    return resolved_page_url if is_supported_web_source_page_url(resolved_page_url) else None


def parse_web_source_html(html: str, *, rule: WebSourceRule) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row_html in _ROW_PATTERN.findall(html):
        title = _extract_title(row_html)
        source = _extract_source(row_html, base_url=rule.base_url)
        if not title or not source:
            continue
        candidate = {
            "title": title,
            "source": source,
            "indexerName": rule.name,
        }
        candidate.update(_extract_metadata(row_html))
        candidates.append(candidate)
    return candidates


def _replace_page_number(url: str, *, page_number: str) -> str:
    parsed = urlparse(url.strip())
    query_pairs = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=False) if key.lower() != "p"]
    query_pairs.append(("p", page_number))
    return urlunparse(parsed._replace(query=urlencode(query_pairs)))


def _is_supported_page_url_for_rule(url: str, *, rule: WebSourceRule) -> bool:
    parsed = urlparse(url.strip())
    rule_host = urlparse(rule.base_url).netloc.lower()
    if parsed.netloc.lower() != rule_host:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.path not in {"", "/"}:
        return False

    query = parse_qs(parsed.query, keep_blank_values=False)
    if any(key.lower() not in {"f", "c", "q", "u", "p"} for key in query):
        return False
    user_name = next((item.strip() for item in query.get("u", ()) if item.strip()), "")
    search_text = next((item.strip() for item in query.get("q", ()) if item.strip()), "")
    category_text = next((item.strip() for item in query.get("c", ()) if item.strip()), "")
    page_number = next((item.strip() for item in query.get("p", ()) if item.strip()), "")
    return bool(user_name or search_text or category_text or _PAGE_NUMBER_TOKEN_PATTERN.fullmatch(f"p={page_number}"))


def _extract_title(row_html: str) -> str:
    title_attr_match = _TITLE_ATTR_PATTERN.search(row_html)
    if title_attr_match is not None:
        title = _clean_html_text(title_attr_match.group("title"))
        if title:
            return title

    title_matches = _TITLE_LINK_PATTERN.findall(row_html)
    for matched_title in reversed(title_matches):
        title = _clean_html_text(matched_title)
        if title:
            return title
    return ""


def _extract_source(row_html: str, *, base_url: str) -> str:
    magnet_match = _MAGNET_PATTERN.search(row_html)
    if magnet_match is not None:
        magnet_link = str(magnet_match.group("link") or "").strip()
        if magnet_link:
            return unescape(magnet_link)

    torrent_match = _TORRENT_PATTERN.search(row_html)
    if torrent_match is None:
        return ""
    torrent_link = str(torrent_match.group("link") or "").strip()
    if not torrent_link:
        return ""
    return urljoin(base_url, unescape(torrent_link))


def _extract_metadata(row_html: str) -> dict[str, Any]:
    cell_texts = [_clean_html_text(cell_html) for cell_html in _CELL_PATTERN.findall(row_html)]
    size_index, size_bytes = _extract_size_bytes(cell_texts)
    seeders = _extract_seeders(cell_texts, size_index=size_index)

    metadata: dict[str, Any] = {}
    if size_bytes > 0:
        metadata["size"] = size_bytes
    if seeders >= 0:
        metadata["seeders"] = seeders
    return metadata


def _extract_size_bytes(cell_texts: list[str]) -> tuple[int, int]:
    for index, text in enumerate(cell_texts):
        size_bytes = _parse_size_bytes(text)
        if size_bytes > 0:
            return index, size_bytes
    return -1, 0


def _extract_seeders(cell_texts: list[str], *, size_index: int) -> int:
    if size_index < 0:
        return -1
    for text in cell_texts[size_index + 1 :]:
        cleaned_text = text.strip()
        if re.fullmatch(r"\d+", cleaned_text) is None:
            continue
        return int(cleaned_text)
    return -1


def _parse_size_bytes(text: str) -> int:
    matched = _SIZE_PATTERN.search(text.strip())
    if matched is None:
        return 0

    try:
        number = float(str(matched.group("number") or "0"))
    except ValueError:
        return 0

    unit = str(matched.group("unit") or "").strip().lower()
    multiplier = {
        "b": 1,
        "kb": 1024,
        "kib": 1024,
        "mb": 1024**2,
        "mib": 1024**2,
        "gb": 1024**3,
        "gib": 1024**3,
        "tb": 1024**4,
        "tib": 1024**4,
    }.get(unit, 0)
    if multiplier <= 0:
        return 0
    return int(number * multiplier)


def _clean_html_text(value: str) -> str:
    without_tags = _TAG_PATTERN.sub(" ", value)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def _log_web_source_error(*, source_name: str, query: str, error: Exception) -> None:
    print(
        f"\033[31m[BT 外部站点源失败]\033[0m 来源={source_name} 查询={query} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查站点可达性、HTML 页面结构和网络连通性后重试。"
    )
