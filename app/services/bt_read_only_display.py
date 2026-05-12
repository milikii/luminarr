from __future__ import annotations

import re
import sqlite3
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.db.adult_content_registry_repo import AdultContentRegistryPersistenceError, AdultContentRegistryRepo
from app.operational_logging import emit_operational_log
from app.search_title_normalization import BT_RESULT_TITLE_NOISE_TOKENS, compact_match_key, normalize_match_key
from app.services.adult_content import AdultContentMatch, extract_exact_adult_content_match
from app.services.adult_metadata_sources import get_adult_metadata_source_profile
from app.services.bt_sources import attach_bt_source_profile, canonicalize_bt_source_name, get_bt_source_priority

AdultReadOnlyLookupFunc = Callable[[str], Awaitable[JavLibraryReadOnlyMatch | None]]
BT_READ_ONLY_HELPER_TITLE_NOISE_TOKENS = frozenset(
    {
        "collection",
        "compilation",
        "edition",
        "complete",
    }
)
_TITLE_RELEVANCE_NOISE_TOKENS = frozenset(
    {
        "jav",
        "fc2",
        "ppv",
        "sample",
        "sub",
        "subtitle",
        "subbed",
        "uncensored",
        "censored",
        "中字",
        "字幕",
        "中文字幕",
        "中文",
        "无码",
        "有码",
        "流出",
        "破解",
        "合集",
        "complete",
        "edition",
    }
)


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
        include_explicit_adult_metadata: bool = False,
    ) -> list[dict[str, Any]]:
        selected_limit = max(1, limit)
        display_candidates = [_to_candidate_dict(item) for item in candidates]
        if not display_candidates:
            return []
        helper_match = None
        if _should_lookup_helper_metadata(
            display_candidates,
            lookup_query=lookup_query,
            include_explicit_adult_metadata=include_explicit_adult_metadata,
        ):
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
            include_explicit_adult_metadata=include_explicit_adult_metadata,
        )

    async def decorate_display_candidates(
        self,
        candidates: Sequence[Mapping[str, Any]],
        *,
        lookup_query: str,
        helper_match: JavLibraryReadOnlyMatch | None = None,
        include_explicit_adult_metadata: bool = False,
    ) -> list[dict[str, Any]]:
        display_candidates = [_to_candidate_dict(item) for item in candidates]
        if not display_candidates:
            return [self._annotate_adult_history(item) for item in display_candidates]
        if helper_match is None and _should_lookup_helper_metadata(
            display_candidates,
            lookup_query=lookup_query,
            include_explicit_adult_metadata=include_explicit_adult_metadata,
        ):
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
        content_match = extract_exact_adult_content_match(lookup_query)
        if content_match is None:
            return None
        try:
            return await self.adult_read_only_lookup_func(content_match.display_id)
        except httpx.HTTPError as error:
            emit_operational_log(
                title="JavLibrary 只读补全失败",
                detail=f"query={lookup_query} 错误={error}",
                fix_hint="检查 JavLibrary 可达性、代理和 HTML 结构；当前只跳过只读补全，不影响 BT 候选展示。",
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
            emit_operational_log(
                title="成人资源历史查询失败",
                detail=f"content_id={content_id} 错误={error}",
                fix_hint="检查 adult_content_registry 表读取是否正常；当前只跳过历史提示，不影响候选展示。",
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
        _copy_optional_helper_metadata(candidate, helper_match=helper_match)
        return candidate


def _should_lookup_helper_metadata(
    candidates: Sequence[Mapping[str, Any]],
    *,
    lookup_query: str,
    include_explicit_adult_metadata: bool,
) -> bool:
    if any(not str(item.get("adult_content_id", "")).strip() for item in candidates):
        return True
    if not include_explicit_adult_metadata:
        return False
    return extract_exact_adult_content_match(lookup_query) is not None


def _copy_optional_helper_metadata(candidate: dict[str, Any], *, helper_match: JavLibraryReadOnlyMatch) -> None:
    optional_fields = {
        "poster_url": "read_only_adult_poster_url",
        "release_date": "read_only_adult_release_date",
        "runtime": "read_only_adult_runtime",
        "duration": "read_only_adult_runtime",
        "maker": "read_only_adult_maker",
        "studio": "read_only_adult_maker",
        "label": "read_only_adult_label",
        "series": "read_only_adult_series",
        "director": "read_only_adult_director",
        "genres": "read_only_adult_genres",
        "actors": "read_only_adult_actors",
    }
    for helper_field, candidate_field in optional_fields.items():
        value = getattr(helper_match, helper_field, "")
        if value:
            candidate[candidate_field] = value

    source_profile = get_adult_metadata_source_profile(str(helper_match.source_site))
    if source_profile is None:
        return
    candidate["read_only_adult_metadata_source_role"] = source_profile.role
    candidate["read_only_adult_metadata_source_priority"] = source_profile.priority


def _to_candidate_dict(item: Mapping[str, Any]) -> dict[str, Any]:
    return attach_bt_source_profile({str(key): value for key, value in item.items()})


def prepare_bt_read_only_selection_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    helper_match: JavLibraryReadOnlyMatch | None,
) -> list[dict[str, Any]]:
    display_candidates = [_to_candidate_dict(item) for item in candidates]
    if helper_match is None:
        return display_candidates
    prioritized: list[dict[str, Any]] = []
    remainder: list[dict[str, Any]] = []
    for candidate in display_candidates:
        if _is_bt_read_only_helper_related(candidate, helper_match=helper_match):
            prioritized.append(candidate)
            continue
        remainder.append(candidate)
    return prioritized + remainder


def should_apply_bt_read_only_helper(
    candidate: Mapping[str, Any],
    *,
    helper_match: JavLibraryReadOnlyMatch,
) -> bool:
    return _is_bt_read_only_helper_related(candidate, helper_match=helper_match)


def _is_bt_read_only_helper_related(
    candidate: Mapping[str, Any],
    *,
    helper_match: JavLibraryReadOnlyMatch,
) -> bool:
    title = _safe_text(candidate.get("title"), default="")
    candidate_content_id = _safe_text(candidate.get("adult_content_id"), default="") or _safe_text(
        candidate.get("read_only_adult_content_id"),
        default="",
    )
    if candidate_content_id == helper_match.normalized_content_id:
        return True
    candidate_display_id = _safe_text(candidate.get("adult_display_id"), default="") or _safe_text(
        candidate.get("read_only_adult_display_id"),
        default="",
    )
    if candidate_display_id == helper_match.display_id:
        return True
    if not title:
        return False
    display_id_key = compact_match_key(normalize_match_key(helper_match.display_id))
    title_key = compact_match_key(normalize_match_key(title))
    if display_id_key and display_id_key in title_key:
        return True
    helper_tokens = _extract_bt_read_only_helper_tokens(helper_match.title, display_id=helper_match.display_id)
    candidate_tokens = _extract_bt_read_only_helper_tokens(title, display_id=helper_match.display_id)
    return bool(helper_tokens and candidate_tokens and helper_tokens.intersection(candidate_tokens))


def _extract_bt_read_only_helper_tokens(value: str, *, display_id: str) -> set[str]:
    normalized = normalize_match_key(value)
    if not normalized:
        return set()
    display_id_tokens = {token for token in normalize_match_key(display_id).split() if token}
    tokens: set[str] = set()
    for token in normalized.split():
        if (
            token in BT_RESULT_TITLE_NOISE_TOKENS
            or token in BT_READ_ONLY_HELPER_TITLE_NOISE_TOKENS
            or token in display_id_tokens
        ):
            continue
        if len(token) <= 1 or re.fullmatch(r"(?:19|20)\d{2}", token):
            continue
        tokens.add(token)
    return tokens


def _safe_text(value: Any, *, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text


def order_adult_bt_candidates(
    results: Sequence[Mapping[str, Any]],
    *,
    query: str,
) -> list[dict[str, Any]]:
    query_match = extract_exact_adult_content_match(query)
    annotated_results = [_to_candidate_dict(item) for item in results]
    return sorted(
        annotated_results,
        key=lambda item: _candidate_sort_key(item, query_match=query_match, query=query),
        reverse=True,
    )


def build_adult_history_text(*, status: str, archive_path: str) -> str:
    if status == "pending":
        return "历史: 该番号已有待确认下载记录。"
    if status == "downloading":
        return "历史: 该番号已有下载任务在运行。"
    if status == "archived_present":
        if archive_path:
            return f"历史: 该番号已归档保留：{archive_path}"
        return "历史: 该番号已归档保留。"
    if status == "archived_deleted":
        if archive_path:
            return f"历史: 该番号曾归档，当前源资源已清理：{archive_path}"
        return "历史: 该番号曾归档，当前源资源已清理。"
    return ""


def _candidate_sort_key(
    item: Mapping[str, Any],
    *,
    query_match: AdultContentMatch | None,
    query: str,
) -> tuple[float, float, float, float, float, float, str]:
    candidate_match = _resolve_candidate_match(item)
    exact_id_score = 1.0 if _content_id_matches(candidate_match, query_match=query_match) else 0.0
    explicit_id_title_score = _resolve_explicit_id_title_score(item, query_match=query_match)
    title_relevance_score = _resolve_title_relevance_score(item, query=query)
    source_priority = _resolve_source_priority(item)
    seeders = float(_safe_int(item.get("seeders")))
    size_bytes = float(_safe_int(item.get("size")))
    return (
        exact_id_score,
        explicit_id_title_score,
        title_relevance_score,
        source_priority,
        seeders,
        size_bytes,
        str(item.get("title", "")).strip().lower(),
    )


def _resolve_candidate_match(item: Mapping[str, Any]) -> AdultContentMatch | None:
    raw_match = item.get("adult_content_match")
    if isinstance(raw_match, AdultContentMatch):
        return raw_match
    return extract_exact_adult_content_match(
        str(item.get("title", "")).strip(),
        source_site=str(item.get("sourceProvider", "")).strip() or str(item.get("indexerName", "")).strip(),
    )


def _content_id_matches(candidate_match: AdultContentMatch | None, *, query_match: AdultContentMatch | None) -> bool:
    if candidate_match is None or query_match is None:
        return False
    return candidate_match.normalized_content_id == query_match.normalized_content_id


def _resolve_source_priority(item: Mapping[str, Any]) -> float:
    source_provider = canonicalize_bt_source_name(str(item.get("sourceProvider", "")).strip())
    indexer_name = canonicalize_bt_source_name(str(item.get("indexerName", "")).strip())
    return max(get_bt_source_priority(source_provider), get_bt_source_priority(indexer_name))


def _safe_int(value: Any) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return 0
    if resolved > 0:
        return resolved
    return 0

def _resolve_explicit_id_title_score(item: Mapping[str, Any], *, query_match: AdultContentMatch | None) -> float:
    if query_match is None:
        return 0.0
    title = str(item.get("title", "")).strip()
    if not title:
        return 0.0
    query_display_id = compact_match_key(normalize_match_key(query_match.display_id))
    title_compact = compact_match_key(normalize_match_key(title))
    if not query_display_id or not title_compact:
        return 0.0
    return 1.0 if query_display_id in title_compact else 0.0


def _resolve_title_relevance_score(item: Mapping[str, Any], *, query: str) -> float:
    query_tokens = _extract_relevance_tokens(query)
    if not query_tokens:
        return 0.0

    title = str(item.get("title", "")).strip()
    title_tokens = _extract_relevance_tokens(title)
    if not title_tokens:
        return 0.0

    overlap = len(query_tokens.intersection(title_tokens))
    if overlap <= 0:
        return 0.0

    query_compact = compact_match_key(normalize_match_key(query))
    title_compact = compact_match_key(normalize_match_key(title))
    if query_compact and title_compact and query_compact in title_compact:
        return float(overlap + len(query_tokens))
    return float(overlap)


def _extract_relevance_tokens(value: str) -> set[str]:
    normalized = normalize_match_key(value)
    if not normalized:
        return set()
    tokens: set[str] = set()
    for token in normalized.split():
        if token in _TITLE_RELEVANCE_NOISE_TOKENS:
            continue
        if len(token) <= 1:
            continue
        tokens.add(token)
    return tokens
