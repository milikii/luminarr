from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import quote_plus, urljoin

import httpx

_ROW_PATTERN = re.compile(r"<tr\b[^>]*>(?P<html>.*?)</tr>", re.IGNORECASE | re.DOTALL)
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


@dataclass(frozen=True, slots=True)
class WebSourceRule:
    name: str
    base_url: str
    search_path_template: str


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
    ) -> None:
        self._rule = rule
        self._timeout_seconds = timeout_seconds

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

    def _build_search_url(self, query: str) -> str:
        encoded_query = quote_plus(query)
        path = self._rule.search_path_template.format(query=encoded_query)
        return f"{self._rule.base_url}{path}"

    async def _get(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url)
        response.raise_for_status()
        return response


def parse_web_source_html(html: str, *, rule: WebSourceRule) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row_html in _ROW_PATTERN.findall(html):
        title = _extract_title(row_html)
        source = _extract_source(row_html, base_url=rule.base_url)
        if not title or not source:
            continue
        candidates.append(
            {
                "title": title,
                "source": source,
                "indexerName": rule.name,
            }
        )
    return candidates


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


def _clean_html_text(value: str) -> str:
    without_tags = _TAG_PATTERN.sub(" ", value)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def _log_web_source_error(*, source_name: str, query: str, error: Exception) -> None:
    print(
        f"\033[31m[BT 外部站点源失败]\033[0m 来源={source_name} 查询={query} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查站点可达性、HTML 页面结构和网络连通性后重试。"
    )
