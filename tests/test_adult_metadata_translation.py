from __future__ import annotations

import asyncio
import json

from app.services.adult_metadata_translation import (
    AdultMetadataTranslationRequest,
    AdultMetadataTranslationResult,
    AdultMetadataTranslatorService,
    apply_adult_metadata_translation_results,
    build_adult_metadata_translation_requests,
)


def test_build_adult_metadata_translation_requests_collects_expected_fields() -> None:
    requests = build_adult_metadata_translation_requests(
        (
            {
                "read_only_adult_display_id": "SSIS-842",
                "read_only_adult_source_site": "avmoo.shop",
                "read_only_adult_title": "SSIS-842 日本語タイトル",
                "read_only_adult_overview": "日本語のあらすじ",
                "read_only_adult_series": "シリーズ名",
                "read_only_adult_maker": "片商名",
                "read_only_adult_label": "レーベル名",
                "read_only_adult_director": "監督名",
            },
        )
    )

    assert requests == (
        AdultMetadataTranslationRequest(
            request_id="candidate-1",
            display_id="SSIS-842",
            source_site="avmoo.shop",
            title="SSIS-842 日本語タイトル",
            overview="日本語のあらすじ",
            series="シリーズ名",
            maker="片商名",
            label="レーベル名",
            director="監督名",
        ),
    )


def test_apply_adult_metadata_translation_results_merges_translated_fields() -> None:
    translated = apply_adult_metadata_translation_results(
        (
            {
                "read_only_adult_display_id": "SSIS-842",
                "read_only_adult_title": "SSIS-842 日本語タイトル",
                "read_only_adult_series": "シリーズ名",
                "read_only_adult_maker": "片商名",
                "read_only_adult_director": "監督名",
            },
        ),
        (
            AdultMetadataTranslationResult(
                request_id="candidate-1",
                title_zh="SSIS-842 中文标题",
                overview_zh="中文简介",
                series_zh="中文系列",
                maker_zh="中文片商",
                label_zh="中文厂牌",
                director_zh="中文导演",
            ),
        ),
    )

    assert translated == (
        {
            "read_only_adult_display_id": "SSIS-842",
            "read_only_adult_title": "SSIS-842 日本語タイトル",
            "read_only_adult_series": "シリーズ名",
            "read_only_adult_maker": "片商名",
            "read_only_adult_director": "監督名",
            "adult_translation_title_zh": "SSIS-842 中文标题",
            "adult_translation_overview_zh": "中文简介",
            "adult_translation_series_zh": "中文系列",
            "adult_translation_maker_zh": "中文片商",
            "adult_translation_label_zh": "中文厂牌",
            "adult_translation_director_zh": "中文导演",
        },
    )


def test_translate_requests_returns_empty_without_api_key() -> None:
    service = AdultMetadataTranslatorService(api_key="")

    results = asyncio.run(
        service.translate_requests(
            (
                AdultMetadataTranslationRequest(
                    request_id="candidate-1",
                    display_id="SSIS-842",
                    source_site="avmoo.shop",
                    title="SSIS-842 日本語タイトル",
                ),
            )
        )
    )

    assert results == ()


def test_translate_candidates_without_api_key_logs_and_keeps_original_candidates(monkeypatch) -> None:
    logged: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "app.services.adult_metadata_translation.emit_operational_log",
        lambda *, title, detail, fix_hint: logged.append((title, detail)),
    )
    service = AdultMetadataTranslatorService(api_key="")
    candidates = (
        {
            "read_only_adult_display_id": "SSIS-842",
            "read_only_adult_source_site": "avmoo.shop",
            "read_only_adult_title": "SSIS-842 日本語タイトル",
            "read_only_adult_overview": "日本語のあらすじ",
        },
    )

    translated = asyncio.run(service.translate_candidates(candidates))

    assert translated == candidates
    assert logged == [("成人 metadata 翻译未启用", "request_count=1 原因=missing api key")]


def test_translate_candidates_deduplicates_shared_metadata_and_fans_out_translations() -> None:
    captured_request_batches: list[list[dict[str, object]]] = []

    def fake_request_chat_completion(_system_prompt: str, user_payload: dict[str, object]) -> str:
        requests = user_payload["requests"]
        assert isinstance(requests, list)
        captured_request_batches.append(list(requests))
        assert len(requests) == 1
        request_id = str(requests[0]["request_id"])
        return json.dumps(
            {
                "translations": [
                    {
                        "request_id": request_id,
                        "title_zh": "SSIS-491 中文标题",
                        "overview_zh": "中文简介",
                        "series_zh": "中文系列",
                    }
                ]
            },
            ensure_ascii=False,
        )

    service = AdultMetadataTranslatorService(
        api_key="adult-translate-key",
        request_chat_completion_func=fake_request_chat_completion,
    )
    candidates = (
        {
            "title": "SSIS-491 release A",
            "read_only_adult_display_id": "SSIS-491",
            "read_only_adult_source_site": "avmoo.shop",
            "read_only_adult_detail_url": "https://avmoo.shop/cn/movie/491",
            "read_only_adult_title": "SSIS-491 日本語タイトル",
            "read_only_adult_overview": "日本語のあらすじ",
            "read_only_adult_series": "シリーズ名",
        },
        {
            "title": "SSIS-491 release B",
            "read_only_adult_display_id": "SSIS-491",
            "read_only_adult_source_site": "avmoo.shop",
            "read_only_adult_detail_url": "https://avmoo.shop/cn/movie/491",
            "read_only_adult_title": "SSIS-491 日本語タイトル",
            "read_only_adult_overview": "日本語のあらすじ",
            "read_only_adult_series": "シリーズ名",
        },
    )

    translated = asyncio.run(service.translate_candidates(candidates))

    assert len(captured_request_batches) == 1
    assert captured_request_batches[0] == [
        {
            "request_id": "candidate-1",
            "display_id": "SSIS-491",
            "source_site": "avmoo.shop",
            "title": "SSIS-491 日本語タイトル",
            "overview": "日本語のあらすじ",
            "series": "シリーズ名",
            "maker": "",
            "label": "",
            "director": "",
        }
    ]
    assert translated[0]["adult_translation_title_zh"] == "SSIS-491 中文标题"
    assert translated[1]["adult_translation_title_zh"] == "SSIS-491 中文标题"
    assert translated[0]["adult_translation_overview_zh"] == "中文简介"
    assert translated[1]["adult_translation_series_zh"] == "中文系列"


def test_translate_candidates_falls_back_when_batch_response_is_empty(monkeypatch) -> None:
    logged: list[tuple[str, str]] = []
    request_batches: list[list[str]] = []

    monkeypatch.setattr(
        "app.services.adult_metadata_translation.emit_operational_log",
        lambda *, title, detail, fix_hint: logged.append((title, detail)),
    )

    def fake_request_chat_completion(_system_prompt: str, user_payload: dict[str, object]) -> str:
        requests = user_payload["requests"]
        assert isinstance(requests, list)
        request_ids = [str(item["request_id"]) for item in requests]
        request_batches.append(request_ids)
        if len(requests) > 1:
            return ""
        request_id = request_ids[0]
        display_id = str(requests[0]["display_id"])
        return json.dumps(
            {
                "translations": [
                    {
                        "request_id": request_id,
                        "title_zh": f"{display_id} 中文标题",
                    }
                ]
            },
            ensure_ascii=False,
        )

    service = AdultMetadataTranslatorService(
        api_key="adult-translate-key",
        request_chat_completion_func=fake_request_chat_completion,
    )
    candidates = (
        {
            "read_only_adult_display_id": "SSIS-842",
            "read_only_adult_title": "SSIS-842 日本語タイトル",
        },
        {
            "read_only_adult_display_id": "SSIS-843",
            "read_only_adult_title": "SSIS-843 日本語タイトル",
        },
    )

    translated = asyncio.run(service.translate_candidates(candidates))

    assert request_batches == [["candidate-1", "candidate-2"], ["candidate-1"], ["candidate-2"]]
    assert translated[0]["adult_translation_title_zh"] == "SSIS-842 中文标题"
    assert translated[1]["adult_translation_title_zh"] == "SSIS-843 中文标题"
    assert logged[0][0] == "成人 metadata 翻译批量失败"
    assert "candidate-1,candidate-2" in logged[0][1]


def test_translate_candidates_falls_back_for_missing_request_ids(monkeypatch) -> None:
    logged: list[tuple[str, str]] = []
    request_batches: list[list[str]] = []

    monkeypatch.setattr(
        "app.services.adult_metadata_translation.emit_operational_log",
        lambda *, title, detail, fix_hint: logged.append((title, detail)),
    )

    def fake_request_chat_completion(_system_prompt: str, user_payload: dict[str, object]) -> str:
        requests = user_payload["requests"]
        assert isinstance(requests, list)
        request_ids = [str(item["request_id"]) for item in requests]
        request_batches.append(request_ids)
        if len(requests) > 1:
            return json.dumps(
                {
                    "translations": [
                        {
                            "request_id": "candidate-1",
                            "title_zh": "候选一中文标题",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        request_id = request_ids[0]
        display_id = str(requests[0]["display_id"])
        return json.dumps(
            {
                "translations": [
                    {
                        "request_id": request_id,
                        "title_zh": f"{display_id} 中文标题",
                    }
                ]
            },
            ensure_ascii=False,
        )

    service = AdultMetadataTranslatorService(
        api_key="adult-translate-key",
        request_chat_completion_func=fake_request_chat_completion,
    )
    candidates = (
        {
            "read_only_adult_display_id": "SSIS-842",
            "read_only_adult_title": "SSIS-842 日本語タイトル",
        },
        {
            "read_only_adult_display_id": "SSIS-843",
            "read_only_adult_title": "SSIS-843 日本語タイトル",
        },
    )

    translated = asyncio.run(service.translate_candidates(candidates))

    assert request_batches == [["candidate-1", "candidate-2"], ["candidate-2"]]
    assert translated[0]["adult_translation_title_zh"] == "候选一中文标题"
    assert translated[1]["adult_translation_title_zh"] == "SSIS-843 中文标题"
    assert logged == [("成人 metadata 翻译结果不完整", "request_ids=candidate-1,candidate-2 result_ids=candidate-1")]


def test_translate_candidates_requests_json_and_enriches_candidates() -> None:
    captured: dict[str, object] = {}

    def fake_request_chat_completion(system_prompt: str, user_payload: dict[str, object]) -> str:
        captured["system_prompt"] = system_prompt
        captured["user_payload"] = user_payload
        return json.dumps(
            {
                "translations": [
                    {
                        "request_id": "candidate-1",
                        "title_zh": "SSIS-842 中文标题",
                        "overview_zh": "中文简介",
                        "series_zh": "中文系列",
                        "maker_zh": "中文片商",
                        "label_zh": "中文厂牌",
                        "director_zh": "中文导演",
                    }
                ]
            },
            ensure_ascii=False,
        )

    service = AdultMetadataTranslatorService(
        api_key="adult-translate-key",
        request_chat_completion_func=fake_request_chat_completion,
    )

    translated = asyncio.run(
        service.translate_candidates(
            (
                {
                    "read_only_adult_display_id": "SSIS-842",
                    "read_only_adult_source_site": "avmoo.shop",
                    "read_only_adult_title": "SSIS-842 日本語タイトル",
                    "read_only_adult_overview": "日本語のあらすじ",
                    "read_only_adult_series": "シリーズ名",
                    "read_only_adult_maker": "片商名",
                    "read_only_adult_label": "レーベル名",
                    "read_only_adult_director": "監督名",
                },
            )
        )
    )

    payload = captured["user_payload"]
    assert isinstance(payload, dict)
    assert "成人影片 metadata 翻译" in str(captured["system_prompt"])
    assert payload["requests"] == [
        {
            "request_id": "candidate-1",
            "display_id": "SSIS-842",
            "source_site": "avmoo.shop",
            "title": "SSIS-842 日本語タイトル",
            "overview": "日本語のあらすじ",
            "series": "シリーズ名",
            "maker": "片商名",
            "label": "レーベル名",
            "director": "監督名",
        }
    ]
    assert translated[0]["adult_translation_title_zh"] == "SSIS-842 中文标题"
    assert translated[0]["adult_translation_overview_zh"] == "中文简介"
