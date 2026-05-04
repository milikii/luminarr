from __future__ import annotations

import asyncio

from app.services.cast_localization import (
    AICastLocalizationService,
    CastLocalizationInput,
    CastLocalizationMatch,
)


def test_ai_cast_localization_service_returns_empty_without_api_key() -> None:
    service = AICastLocalizationService(api_key="")

    result = _run(
        service.localize(
            CastLocalizationInput(
                title="爱的进行时",
                original_title="Akron",
                year="2015",
                tmdb_id="361018",
                cast_truth=(
                    {
                        "id": "10",
                        "name": "Edmund Donovan",
                        "original_name": "Edmund Donovan",
                        "character": "Christopher",
                        "original_character": "Christopher",
                        "order": 0,
                        "profile_image_url": "https://image.tmdb.org/t/p/original/edmund.jpg",
                    },
                ),
            )
        )
    )

    assert result == ()


def test_ai_cast_localization_service_reuses_subtitle_style_contract_and_only_requests_unlocalized_rows() -> None:
    seen: dict[str, object] = {}

    def fake_request(system_prompt: str, user_payload: dict[str, object]) -> str:
        seen["system_prompt"] = system_prompt
        seen["user_payload"] = user_payload
        return (
            '{"cast":[{"id":"10","localized_name":"","localized_character":"克里斯托弗"},'
            '{"id":"11","localized_name":"马修·弗莱斯","localized_character":"班尼·克鲁兹"}]}'
        )

    service = AICastLocalizationService(
        api_key="subtitle-key",
        base_url="https://openai.example/v1",
        model="gpt-5.4-mini",
        timeout_seconds=45.0,
        proxy_url="http://proxy.local:7890",
        request_chat_completion_func=fake_request,
    )

    result = _run(
        service.localize(
            CastLocalizationInput(
                title="爱的进行时",
                original_title="Akron",
                year="2015",
                tmdb_id="361018",
                cast_truth=(
                    {
                        "id": "10",
                        "name": "Edmund Donovan",
                        "original_name": "Edmund Donovan",
                        "character": "Christopher",
                        "original_character": "Christopher",
                        "order": 0,
                        "profile_image_url": "https://image.tmdb.org/t/p/original/edmund.jpg",
                    },
                    {
                        "id": "11",
                        "name": "Matthew Frias",
                        "original_name": "Matthew Frias",
                        "character": "Benny Cruz",
                        "original_character": "Benny Cruz",
                        "order": 1,
                        "profile_image_url": "https://image.tmdb.org/t/p/original/matthew.jpg",
                    },
                    {
                        "id": "12",
                        "name": "本·阿弗莱克",
                        "original_name": "Ben Affleck",
                        "character": "托尼",
                        "original_character": "Tony",
                        "order": 2,
                        "profile_image_url": "https://image.tmdb.org/t/p/original/ben.jpg",
                    },
                ),
            )
        )
    )

    assert "没把握时留空" in str(seen["system_prompt"])
    assert seen["user_payload"] == {
        "title": "爱的进行时",
        "original_title": "Akron",
        "year": "2015",
        "tmdb_id": "361018",
        "cast": [
            {
                "id": "10",
                "order": 0,
                "name": "Edmund Donovan",
                "original_name": "Edmund Donovan",
                "character": "Christopher",
                "original_character": "Christopher",
            },
            {
                "id": "11",
                "order": 1,
                "name": "Matthew Frias",
                "original_name": "Matthew Frias",
                "character": "Benny Cruz",
                "original_character": "Benny Cruz",
            },
        ],
        "rules": {
            "target_language": "zh-CN",
            "actor_name_policy": "high-confidence-only; otherwise empty string",
            "character_policy": "translate naturally when confident; otherwise empty string",
            "return_json_only": True,
            "json_schema": {
                "cast": [
                    {
                        "id": "TMDB cast id string",
                        "localized_name": "Chinese actor name or empty string",
                        "localized_character": "Chinese role name or empty string",
                    }
                ]
            },
        },
    }
    assert result == (
        CastLocalizationMatch(
            cast_id="10",
            order=0,
            original_name="Edmund Donovan",
            localized_name="",
            localized_character="克里斯托弗",
        ),
        CastLocalizationMatch(
            cast_id="11",
            order=1,
            original_name="Matthew Frias",
            localized_name="马修·弗莱斯",
            localized_character="班尼·克鲁兹",
        ),
    )


def _run(coro):
    return asyncio.run(coro)
