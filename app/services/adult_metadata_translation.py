from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.operational_logging import emit_operational_log
from app.services.subtitle_translation_support import _request_subtitle_chat_completion


@dataclass(frozen=True, slots=True)
class AdultMetadataTranslationRequest:
    request_id: str
    display_id: str
    source_site: str = ""
    title: str = ""
    overview: str = ""
    series: str = ""
    maker: str = ""
    label: str = ""
    director: str = ""

    def to_payload(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "display_id": self.display_id,
            "source_site": self.source_site,
            "title": self.title,
            "overview": self.overview,
            "series": self.series,
            "maker": self.maker,
            "label": self.label,
            "director": self.director,
        }


@dataclass(frozen=True, slots=True)
class AdultMetadataTranslationResult:
    request_id: str
    title_zh: str = ""
    overview_zh: str = ""
    series_zh: str = ""
    maker_zh: str = ""
    label_zh: str = ""
    director_zh: str = ""


@dataclass(frozen=True, slots=True)
class _AdultMetadataTranslationGroup:
    request: AdultMetadataTranslationRequest
    candidate_indexes: tuple[int, ...]


_TITLE_KEYS = (
    "adult_title",
    "metadataTitle",
    "metadata_title",
    "read_only_adult_title",
    "title",
)
_OVERVIEW_KEYS = (
    "adult_overview",
    "read_only_adult_overview",
    "overview",
    "description",
    "summary",
    "plot",
)
_SERIES_KEYS = ("adult_series", "series", "read_only_adult_series")
_MAKER_KEYS = (
    "adult_maker",
    "adult_studio",
    "maker",
    "studio",
    "publisher",
    "read_only_adult_maker",
    "read_only_adult_studio",
)
_LABEL_KEYS = ("adult_label", "label", "read_only_adult_label")
_DIRECTOR_KEYS = ("adult_director", "director", "read_only_adult_director")
_DETAIL_URL_KEYS = ("read_only_adult_detail_url", "adult_detail_url", "detail_url")


def build_adult_metadata_translation_requests(
    candidates: Sequence[Mapping[str, Any]],
) -> tuple[AdultMetadataTranslationRequest, ...]:
    requests: list[AdultMetadataTranslationRequest] = []
    for index, item in enumerate(candidates, start=1):
        request = _build_translation_request(item, index=index)
        if request is not None:
            requests.append(request)
    return tuple(requests)


def apply_adult_metadata_translation_results(
    candidates: Sequence[Mapping[str, Any]],
    results: Sequence[AdultMetadataTranslationResult],
) -> tuple[dict[str, Any], ...]:
    results_by_id = {result.request_id: result for result in results}
    translated_candidates: list[dict[str, Any]] = []
    for index, item in enumerate(candidates, start=1):
        candidate = {str(key): value for key, value in item.items()}
        result = results_by_id.get(f"candidate-{index}")
        if result is not None:
            _apply_translation_result(candidate, result=result)
        translated_candidates.append(candidate)
    return tuple(translated_candidates)


class AdultMetadataTranslatorService:
    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        timeout_seconds: float = 60.0,
        proxy_url: str = "",
        request_chat_completion_func: Callable[[str, dict[str, object]], str] | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = (base_url.strip() or "https://api.openai.com/v1").rstrip("/")
        self._model = model.strip() or "gpt-5.4"
        self._timeout_seconds = max(10.0, timeout_seconds)
        self._proxy_url = proxy_url.strip()
        self._request_chat_completion_func = request_chat_completion_func

    async def translate_requests(
        self,
        requests: Sequence[AdultMetadataTranslationRequest],
    ) -> tuple[AdultMetadataTranslationResult, ...]:
        if not self._api_key or not requests:
            return ()
        system_prompt, user_payload = _build_adult_metadata_translation_payload(requests)
        if self._request_chat_completion_func is not None:
            response_text = self._request_chat_completion_func(system_prompt, user_payload)
        else:
            response_text = await asyncio.to_thread(
                _request_subtitle_chat_completion,
                api_key=self._api_key,
                base_url=self._base_url,
                model=self._model,
                timeout_seconds=self._timeout_seconds,
                proxy_url=self._proxy_url,
                system_prompt=system_prompt,
                user_payload=user_payload,
            )
        return _parse_adult_metadata_translation_results(response_text)

    async def translate_candidates(
        self,
        candidates: Sequence[Mapping[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        cloned_candidates = tuple({str(key): value for key, value in item.items()} for item in candidates)
        groups = _build_adult_metadata_translation_groups(cloned_candidates)
        if not groups:
            return cloned_candidates
        if not self._api_key:
            emit_operational_log(
                title="成人 metadata 翻译未启用",
                detail=f"request_count={len(groups)} 原因=missing api key",
                fix_hint="补齐 SUBTITLE_TRANSLATION_API_KEY；当前会保留原始成人 metadata，不影响资源卡片展示。",
            )
            return cloned_candidates
        requests = tuple(group.request for group in groups)
        results_by_id = await self._translate_requests_with_fallback(requests)
        if not results_by_id:
            return cloned_candidates
        return _apply_grouped_translation_results(
            cloned_candidates,
            groups=groups,
            results_by_id=results_by_id,
        )

    async def _translate_requests_with_fallback(
        self,
        requests: Sequence[AdultMetadataTranslationRequest],
    ) -> dict[str, AdultMetadataTranslationResult]:
        try:
            batch_results = await self.translate_requests(requests)
        except Exception as error:
            emit_operational_log(
                title="成人 metadata 翻译批量失败",
                detail=f"request_ids={_join_request_ids(request.request_id for request in requests)} 错误={error}",
                fix_hint="检查翻译接口可达性和响应内容；当前会回退逐条翻译并尽量保留可用中文结果。",
            )
            return await self._translate_requests_individually(requests)
        if not batch_results:
            emit_operational_log(
                title="成人 metadata 翻译批量无结果",
                detail=f"request_ids={_join_request_ids(request.request_id for request in requests)}",
                fix_hint="检查翻译接口是否返回空结果；当前会回退逐条翻译并尽量保留可用中文结果。",
            )
            return await self._translate_requests_individually(requests)

        results_by_id = _collect_translation_results_by_request_id(requests=requests, results=batch_results)
        if len(results_by_id) == len(requests):
            return results_by_id

        emit_operational_log(
            title="成人 metadata 翻译结果不完整",
            detail=(
                f"request_ids={_join_request_ids(request.request_id for request in requests)} "
                f"result_ids={_join_request_ids(result.request_id for result in batch_results)}"
            ),
            fix_hint="检查成人 metadata 翻译 request_id 对齐与响应完整性；当前会回退缺失项逐条翻译并尽量保留已拿到的结果。",
        )
        missing_requests = tuple(request for request in requests if request.request_id not in results_by_id)
        results_by_id.update(await self._translate_requests_individually(missing_requests))
        return results_by_id

    async def _translate_requests_individually(
        self,
        requests: Sequence[AdultMetadataTranslationRequest],
    ) -> dict[str, AdultMetadataTranslationResult]:
        results_by_id: dict[str, AdultMetadataTranslationResult] = {}
        for request in requests:
            try:
                single_results = await self.translate_requests((request,))
            except Exception as error:
                emit_operational_log(
                    title="成人 metadata 单条翻译失败",
                    detail=f"request_id={request.request_id} display_id={request.display_id or '-'} 错误={error}",
                    fix_hint="检查翻译接口可达性和响应内容；当前只会保留该条原文，不影响其他资源候选展示。",
                )
                continue
            matched_result = _collect_translation_results_by_request_id(
                requests=(request,),
                results=single_results,
            ).get(request.request_id)
            if matched_result is None:
                continue
            results_by_id[request.request_id] = matched_result
        return results_by_id


def _build_translation_request(
    item: Mapping[str, Any],
    *,
    index: int,
) -> AdultMetadataTranslationRequest | None:
    request = AdultMetadataTranslationRequest(
        request_id=f"candidate-{index}",
        display_id=_first_text(item, ("adult_display_id", "read_only_adult_display_id", "display_id")) or f"candidate-{index}",
        source_site=_first_text(item, ("adult_metadata_source", "metadataSource", "read_only_adult_source_site")),
        title=_first_text(item, _TITLE_KEYS),
        overview=_first_text(item, _OVERVIEW_KEYS),
        series=_first_text(item, _SERIES_KEYS),
        maker=_first_text(item, _MAKER_KEYS),
        label=_first_text(item, _LABEL_KEYS),
        director=_first_text(item, _DIRECTOR_KEYS),
    )
    if not any(
        (
            request.title,
            request.overview,
            request.series,
            request.maker,
            request.label,
            request.director,
        )
    ):
        return None
    return request


def _build_adult_metadata_translation_groups(
    candidates: Sequence[Mapping[str, Any]],
) -> tuple[_AdultMetadataTranslationGroup, ...]:
    grouped_entries: dict[tuple[str, ...], dict[str, Any]] = {}
    for index, item in enumerate(candidates, start=1):
        request = _build_translation_request(item, index=index)
        if request is None:
            continue
        dedupe_key = _build_translation_dedupe_key(item, request=request)
        entry = grouped_entries.get(dedupe_key)
        if entry is None:
            grouped_entries[dedupe_key] = {
                "request": request,
                "candidate_indexes": [index - 1],
            }
            continue
        entry["candidate_indexes"].append(index - 1)

    return tuple(
        _AdultMetadataTranslationGroup(
            request=entry["request"],
            candidate_indexes=tuple(entry["candidate_indexes"]),
        )
        for entry in grouped_entries.values()
    )


def _build_translation_dedupe_key(
    item: Mapping[str, Any],
    *,
    request: AdultMetadataTranslationRequest,
) -> tuple[str, ...]:
    metadata_fingerprint = _build_translation_metadata_fingerprint(request)
    if metadata_fingerprint:
        return ("fingerprint", metadata_fingerprint)
    display_id = _normalize_identifier(request.display_id)
    if display_id:
        return ("display_id", display_id)
    detail_url = _normalize_identifier(_first_text(item, _DETAIL_URL_KEYS))
    if detail_url:
        return ("detail_url", detail_url)
    return ("request_id", request.request_id)


def _build_translation_metadata_fingerprint(request: AdultMetadataTranslationRequest) -> str:
    values = (
        request.source_site,
        request.title,
        request.overview,
        request.series,
        request.maker,
        request.label,
        request.director,
    )
    normalized_values = tuple(_normalize_identifier(value) for value in values)
    if not any(normalized_values):
        return ""
    return "|".join(normalized_values)


def _build_adult_metadata_translation_payload(
    requests: Sequence[AdultMetadataTranslationRequest],
) -> tuple[str, dict[str, object]]:
    system_prompt = (
        "你是成人影片 metadata 翻译助手。"
        "任务：把给定的日文或其他原文 metadata 字段准确翻译为简体中文。"
        "必须保留番号、专有 ID、站点无关字段结构，不要编造信息，不要输出解释。"
        "演员字段不会提供给你，禁止补充演员翻译。"
        "如果某个字段本来就不需要翻译，可以返回空字符串。"
    )
    user_payload: dict[str, object] = {
        "task": "adult_metadata_translation",
        "rules": {
            "target_language": "zh-CN",
            "return_json_only": True,
            "json_schema": {
                "translations": [
                    {
                        "request_id": "must match input",
                        "title_zh": "string",
                        "overview_zh": "string",
                        "series_zh": "string",
                        "maker_zh": "string",
                        "label_zh": "string",
                        "director_zh": "string",
                    }
                ]
            },
        },
        "requests": [request.to_payload() for request in requests],
    }
    return system_prompt, user_payload


def _parse_adult_metadata_translation_results(
    response_text: str,
) -> tuple[AdultMetadataTranslationResult, ...]:
    try:
        body = json.loads(response_text)
    except ValueError as exc:
        raise RuntimeError(f"成人 metadata 翻译响应不是合法 JSON：{exc}") from exc
    items = body.get("translations")
    if not isinstance(items, list):
        raise RuntimeError("成人 metadata 翻译响应缺少 translations 数组。")

    results: list[AdultMetadataTranslationResult] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        request_id = _safe_text(item.get("request_id"))
        if not request_id:
            continue
        results.append(
            AdultMetadataTranslationResult(
                request_id=request_id,
                title_zh=_safe_text(item.get("title_zh")),
                overview_zh=_safe_text(item.get("overview_zh")),
                series_zh=_safe_text(item.get("series_zh")),
                maker_zh=_safe_text(item.get("maker_zh")),
                label_zh=_safe_text(item.get("label_zh")),
                director_zh=_safe_text(item.get("director_zh")),
            )
        )
    return tuple(results)


def _collect_translation_results_by_request_id(
    *,
    requests: Sequence[AdultMetadataTranslationRequest],
    results: Sequence[AdultMetadataTranslationResult],
) -> dict[str, AdultMetadataTranslationResult]:
    expected_ids = {request.request_id for request in requests if request.request_id}
    results_by_id: dict[str, AdultMetadataTranslationResult] = {}
    for result in results:
        request_id = _safe_text(result.request_id)
        if not request_id or request_id not in expected_ids or request_id in results_by_id:
            continue
        results_by_id[request_id] = result
    return results_by_id


def _apply_grouped_translation_results(
    candidates: Sequence[Mapping[str, Any]],
    *,
    groups: Sequence[_AdultMetadataTranslationGroup],
    results_by_id: Mapping[str, AdultMetadataTranslationResult],
) -> tuple[dict[str, Any], ...]:
    translated_candidates = [{str(key): value for key, value in item.items()} for item in candidates]
    for group in groups:
        result = results_by_id.get(group.request.request_id)
        if result is None:
            continue
        for candidate_index in group.candidate_indexes:
            _apply_translation_result(translated_candidates[candidate_index], result=result)
    return tuple(translated_candidates)


def _apply_translation_result(
    candidate: dict[str, Any],
    *,
    result: AdultMetadataTranslationResult,
) -> None:
    _apply_translated_text(
        candidate,
        target_key="adult_translation_title_zh",
        source_text=_first_text(candidate, _TITLE_KEYS),
        translated_text=result.title_zh,
    )
    _apply_translated_text(
        candidate,
        target_key="adult_translation_overview_zh",
        source_text=_first_text(candidate, _OVERVIEW_KEYS),
        translated_text=result.overview_zh,
    )
    _apply_translated_text(
        candidate,
        target_key="adult_translation_series_zh",
        source_text=_first_text(candidate, _SERIES_KEYS),
        translated_text=result.series_zh,
    )
    _apply_translated_text(
        candidate,
        target_key="adult_translation_maker_zh",
        source_text=_first_text(candidate, _MAKER_KEYS),
        translated_text=result.maker_zh,
    )
    _apply_translated_text(
        candidate,
        target_key="adult_translation_label_zh",
        source_text=_first_text(candidate, _LABEL_KEYS),
        translated_text=result.label_zh,
    )
    _apply_translated_text(
        candidate,
        target_key="adult_translation_director_zh",
        source_text=_first_text(candidate, _DIRECTOR_KEYS),
        translated_text=result.director_zh,
    )


def _apply_translated_text(
    candidate: dict[str, Any],
    *,
    target_key: str,
    source_text: str,
    translated_text: str,
) -> None:
    cleaned_translation = _safe_text(translated_text)
    if not cleaned_translation:
        return
    if _normalize_text(cleaned_translation) == _normalize_text(source_text):
        return
    candidate[target_key] = cleaned_translation


def _has_complete_translation_results(
    *,
    requests: Sequence[AdultMetadataTranslationRequest],
    results: Sequence[AdultMetadataTranslationResult],
) -> bool:
    request_ids = tuple(request.request_id for request in requests if request.request_id)
    result_ids = tuple(result.request_id for result in results if result.request_id)
    return (
        len(result_ids) == len(request_ids)
        and len(set(result_ids)) == len(result_ids)
        and set(result_ids) == set(request_ids)
    )


def _join_request_ids(values: Sequence[str] | Any) -> str:
    return ",".join(str(value).strip() for value in values if str(value).strip()) or "-"


def _first_text(item: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        text = _safe_text(item.get(key))
        if text:
            return text
    return ""


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_identifier(value: str) -> str:
    return _normalize_text(value).casefold()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
