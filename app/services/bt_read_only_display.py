from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.db.adult_content_registry_repo import AdultContentRegistryPersistenceError, AdultContentRegistryRepo
from app.services.adult_bt_selector import build_adult_history_text, order_adult_bt_candidates
from app.services.adult_content import extract_exact_adult_content_match
from app.services.bt_read_only_helper_selection import (
    prepare_bt_read_only_selection_candidates,
    should_apply_bt_read_only_helper,
)

AdultReadOnlyLookupFunc = Callable[[str], Awaitable[JavLibraryReadOnlyMatch | None]]


@dataclass(frozen=True, slots=True)
class BtReadOnlyDisplayService:
    adult_content_registry_repo: AdultContentRegistryRepo | None = None
    adult_read_only_lookup_func: AdultReadOnlyLookupFunc | None = None

    def prepare_raw_candidates(
        self,
        raw_results: Sequence[Mapping[str, Any]],
        *,
        query: str,
    ) -> list[dict[str, Any]]:
        prepared_results = [self._annotate_adult_candidate(item) for item in raw_results]
        ordered_results = order_adult_bt_candidates(prepared_results, query=query)
        return [self._annotate_adult_history(item) for item in ordered_results]

    def prepare_selection_candidates(
        self,
        raw_results: Sequence[Mapping[str, Any]],
        *,
        helper_match: JavLibraryReadOnlyMatch | None,
    ) -> list[dict[str, Any]]:
        display_candidates = [_to_candidate_dict(item) for item in raw_results]
        return prepare_bt_read_only_selection_candidates(
            display_candidates,
            helper_match=helper_match,
        )

    async def build_display_candidates(
        self,
        candidates: Sequence[Mapping[str, Any]],
        *,
        lookup_query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        selected_limit = max(1, limit)
        display_candidates = [_to_candidate_dict(item) for item in candidates]
        if not display_candidates:
            return []
        helper_match = None
        if any(not str(item.get("adult_content_id", "")).strip() for item in display_candidates):
            helper_match = await self.lookup_helper_match(lookup_query)
        display_candidates = prepare_bt_read_only_selection_candidates(
            display_candidates,
            helper_match=helper_match,
        )
        limited_candidates = display_candidates[:selected_limit]
        return await self.decorate_display_candidates(
            limited_candidates,
            lookup_query=lookup_query,
            helper_match=helper_match,
        )

    async def decorate_display_candidates(
        self,
        candidates: Sequence[Mapping[str, Any]],
        *,
        lookup_query: str,
        helper_match: JavLibraryReadOnlyMatch | None = None,
    ) -> list[dict[str, Any]]:
        display_candidates = [_to_candidate_dict(item) for item in candidates]
        if not display_candidates or not any(not str(item.get("adult_content_id", "")).strip() for item in display_candidates):
            return [self._annotate_adult_history(item) for item in display_candidates]
        if helper_match is None:
            helper_match = await self.lookup_helper_match(lookup_query)
        if helper_match is None:
            return [self._annotate_adult_history(item) for item in display_candidates]

        annotated_candidates = [
            self._apply_bt_read_only_helper_fields(
                item,
                helper_match=helper_match,
            )
            for item in display_candidates
        ]
        return [self._annotate_adult_history(item) for item in annotated_candidates]

    async def lookup_helper_match(self, lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        if self.adult_read_only_lookup_func is None:
            return None
        content_match = extract_exact_adult_content_match(lookup_query, source_site="javlibrary")
        if content_match is None or content_match.archive_category != "censored":
            return None
        try:
            return await self.adult_read_only_lookup_func(content_match.display_id)
        except httpx.HTTPError as error:
            print(
                f"\033[31m[JavLibrary 只读补全失败]\033[0m query={lookup_query} 错误={error}\n"
                "\033[33m[处理建议]\033[0m 检查 JavLibrary 可达性、代理和 HTML 结构；当前只跳过只读补全，不影响 BT 候选展示.",
                flush=True,
            )
            return None

    def _annotate_adult_candidate(self, item: Mapping[str, Any]) -> dict[str, Any]:
        candidate = _to_candidate_dict(item)
        if candidate.get("adult_content_id"):
            if not candidate.get("adult_display_id"):
                candidate["adult_display_id"] = candidate.get("adult_content_id", "")
            return candidate
        content_match = extract_exact_adult_content_match(
            str(candidate.get("title", "")).strip(),
            source_site=str(candidate.get("sourceProvider", "")).strip() or str(candidate.get("indexerName", "")).strip(),
        )
        if content_match is None:
            return candidate
        candidate["adult_content_id"] = content_match.normalized_content_id
        candidate["adult_archive_category"] = content_match.archive_category
        candidate["adult_content_kind"] = content_match.source_kind
        candidate["adult_display_id"] = content_match.display_id
        return candidate

    def _annotate_adult_history(self, item: Mapping[str, Any]) -> dict[str, Any]:
        candidate = _to_candidate_dict(item)
        if self.adult_content_registry_repo is None:
            return candidate
        content_id = str(candidate.get("adult_content_id", "")).strip().lower() or str(
            candidate.get("read_only_adult_content_id", "")
        ).strip().lower()
        if not content_id:
            return candidate
        try:
            record = self.adult_content_registry_repo.get_by_content_id(normalized_content_id=content_id)
        except (AdultContentRegistryPersistenceError, sqlite3.Error) as error:
            print(
                f"\033[31m[成人资源历史查询失败]\033[0m content_id={content_id} 错误={error}\n"
                "\033[33m[处理建议]\033[0m 检查 adult_content_registry 表读取是否正常；当前只跳过历史提示，不影响候选展示。",
                flush=True,
            )
            return candidate
        if record is None:
            return candidate
        history_text = build_adult_history_text(
            status=record.current_status,
            archive_path=record.archive_path,
        )
        if history_text:
            candidate["adult_history_text"] = history_text
            candidate["adult_history_status"] = record.current_status
        return candidate

    def _apply_bt_read_only_helper_fields(
        self,
        item: Mapping[str, Any],
        *,
        helper_match: JavLibraryReadOnlyMatch,
    ) -> dict[str, Any]:
        candidate = _to_candidate_dict(item)
        if candidate.get("adult_content_id"):
            return candidate
        if not should_apply_bt_read_only_helper(
            candidate,
            helper_match=helper_match,
        ):
            return candidate
        candidate["read_only_adult_content_id"] = helper_match.normalized_content_id
        candidate["read_only_adult_display_id"] = helper_match.display_id
        candidate["read_only_adult_archive_category"] = helper_match.archive_category
        candidate["read_only_adult_title"] = helper_match.title
        candidate["read_only_adult_source_site"] = helper_match.source_site
        candidate["read_only_adult_detail_url"] = helper_match.detail_url
        return candidate


def _to_candidate_dict(item: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in item.items()}
