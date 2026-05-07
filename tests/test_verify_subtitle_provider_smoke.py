from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass(frozen=True, slots=True)
class _FakeResponse:
    status_code: int
    payload: object | None = None
    text: str = ""

    def json(self) -> object:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class _FakeHttpxClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.request_log: list[tuple[str, str, dict[str, str]]] = []

    def __enter__(self) -> _FakeHttpxClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str, *, headers: dict[str, str]) -> _FakeResponse:
        self.request_log.append(("GET", url, headers))
        return self._response


def test_load_subtitle_provider_smoke_config_reads_only_subtitle_related_env() -> None:
    from app.maintenance import verify_subtitle_provider_smoke as module

    config = module.load_subtitle_provider_smoke_config(
        {
            "SUBTITLE_TRANSLATION_API_KEY": "demo-key",
            "SUBTITLE_TRANSLATION_BASE_URL": "https://openai.example/v1/",
            "SUBTITLE_TRANSLATION_MODEL": "gpt-5.4-mini",
            "SUBTITLE_TRANSLATION_TIMEOUT_SECONDS": "45",
            "OUTBOUND_PROXY_URL": "http://proxy.local:7890",
        }
    )

    assert config == module.SubtitleProviderSmokeConfig(
        api_key="demo-key",
        base_url="https://openai.example/v1",
        model="gpt-5.4-mini",
        timeout_seconds=45.0,
        proxy_url="http://proxy.local:7890",
    )


def test_verify_subtitle_provider_smoke_succeeds_when_provider_and_translation_chain_pass(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.maintenance import verify_subtitle_provider_smoke as module

    config = module.SubtitleProviderSmokeConfig(
        api_key="demo-key",
        base_url="https://openai.example/v1",
        model="gpt-5.4-mini",
        timeout_seconds=45.0,
        proxy_url="",
    )
    client = _FakeHttpxClient(_FakeResponse(status_code=200, payload={"data": [{"id": "gpt-5.4-mini"}]}))
    seen_client_kwargs: list[dict[str, object]] = []

    def fake_client_ctor(*, timeout: float, proxy: str | None):
        seen_client_kwargs.append({"timeout": timeout, "proxy": proxy})
        return client

    class _FakeTranslator:
        def __init__(self, **kwargs) -> None:
            assert kwargs["api_key"] == "demo-key"
            assert kwargs["base_url"] == "https://openai.example/v1"
            assert kwargs["model"] == "gpt-5.4-mini"
            assert kwargs["timeout_seconds"] == 45.0
            assert kwargs["proxy_url"] == ""

        def _translate_lines_professional(
            self,
            *,
            source_lines: list[str],
            movie_title: str,
            trusted_name_map: dict[str, str] | None = None,
        ) -> list[str]:
            assert movie_title == "Subtitle Provider Smoke Check"
            assert trusted_name_map == {}
            return [f"译文：{line}" for line in source_lines]

    monkeypatch.setattr(module, "load_subtitle_provider_smoke_config", lambda environ=None: config)
    monkeypatch.setattr(module.httpx, "Client", fake_client_ctor)
    monkeypatch.setattr(module, "SubtitleTranslatorService", _FakeTranslator)

    exit_code = module.main([])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "字幕 provider 自检通过" in output
    assert "base_url=https://openai.example/v1" in output
    assert "model=gpt-5.4-mini" in output
    assert "proxy=direct" in output
    assert "/models: ok" in output
    assert "translation: ok (3/3)" in output
    assert seen_client_kwargs == [{"timeout": 45.0, "proxy": None}]
    assert client.request_log == [
        (
            "GET",
            "https://openai.example/v1/models",
            {"Authorization": "Bearer demo-key"},
        )
    ]


def test_verify_subtitle_provider_smoke_keeps_going_when_models_endpoint_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.maintenance import verify_subtitle_provider_smoke as module

    config = module.SubtitleProviderSmokeConfig(
        api_key="demo-key",
        base_url="https://compatible.example/v1",
        model="demo-model",
        timeout_seconds=30.0,
        proxy_url="http://proxy.local:7890",
    )

    class _FakeTranslator:
        def __init__(self, **kwargs) -> None:
            assert kwargs["proxy_url"] == "http://proxy.local:7890"

        def _translate_lines_professional(
            self,
            *,
            source_lines: list[str],
            movie_title: str,
            trusted_name_map: dict[str, str] | None = None,
        ) -> list[str]:
            return [f"译文：{line}" for line in source_lines]

    monkeypatch.setattr(module, "load_subtitle_provider_smoke_config", lambda environ=None: config)
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda *, timeout, proxy: _FakeHttpxClient(_FakeResponse(status_code=404, text="not found")),
    )
    monkeypatch.setattr(module, "SubtitleTranslatorService", _FakeTranslator)

    exit_code = module.main([])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "字幕 provider 自检通过" in output
    assert "proxy=http://proxy.local:7890" in output
    assert "/models: warning" in output
    assert "provider 未提供可校验的 /models 能力" in output
    assert "translation: ok (3/3)" in output


def test_verify_subtitle_provider_smoke_fails_when_configured_model_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.maintenance import verify_subtitle_provider_smoke as module

    config = module.SubtitleProviderSmokeConfig(
        api_key="demo-key",
        base_url="https://openai.example/v1",
        model="gpt-5.4-mini",
        timeout_seconds=30.0,
        proxy_url="",
    )

    class _FakeTranslator:
        def __init__(self, **kwargs) -> None:
            return None

        def _translate_lines_professional(
            self,
            *,
            source_lines: list[str],
            movie_title: str,
            trusted_name_map: dict[str, str] | None = None,
        ) -> list[str]:
            return [f"译文：{line}" for line in source_lines]

    monkeypatch.setattr(module, "load_subtitle_provider_smoke_config", lambda environ=None: config)
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda *, timeout, proxy: _FakeHttpxClient(_FakeResponse(status_code=200, payload={"data": [{"id": "other-model"}]})),
    )
    monkeypatch.setattr(module, "SubtitleTranslatorService", _FakeTranslator)

    exit_code = module.main([])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "/models: fail" in output
    assert "当前 model 未出现在 provider 模型列表中：gpt-5.4-mini" in output
    assert "字幕 provider 自检失败" in output


def test_verify_subtitle_provider_smoke_fails_when_translation_chain_returns_blank_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.maintenance import verify_subtitle_provider_smoke as module

    config = module.SubtitleProviderSmokeConfig(
        api_key="demo-key",
        base_url="https://openai.example/v1",
        model="gpt-5.4-mini",
        timeout_seconds=30.0,
        proxy_url="",
    )

    class _FakeTranslator:
        def __init__(self, **kwargs) -> None:
            return None

        def _translate_lines_professional(
            self,
            *,
            source_lines: list[str],
            movie_title: str,
            trusted_name_map: dict[str, str] | None = None,
        ) -> list[str]:
            return ["译文一", " ", "译文三"]

    monkeypatch.setattr(module, "load_subtitle_provider_smoke_config", lambda environ=None: config)
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda *, timeout, proxy: _FakeHttpxClient(_FakeResponse(status_code=404, text="not found")),
    )
    monkeypatch.setattr(module, "SubtitleTranslatorService", _FakeTranslator)

    exit_code = module.main([])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "translation: fail" in output
    assert "字幕翻译链返回了空译文行：index=2" in output
    assert "字幕 provider 自检失败" in output


def test_verify_subtitle_provider_smoke_fails_when_translation_chain_returns_non_string_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.maintenance import verify_subtitle_provider_smoke as module

    config = module.SubtitleProviderSmokeConfig(
        api_key="demo-key",
        base_url="https://openai.example/v1",
        model="gpt-5.4-mini",
        timeout_seconds=30.0,
        proxy_url="",
    )

    class _FakeTranslator:
        def __init__(self, **kwargs) -> None:
            return None

        def _translate_lines_professional(
            self,
            *,
            source_lines: list[str],
            movie_title: str,
            trusted_name_map: dict[str, str] | None = None,
        ) -> list[object]:
            _ = source_lines, movie_title, trusted_name_map
            return ["译文一", 2, "译文三"]

    monkeypatch.setattr(module, "load_subtitle_provider_smoke_config", lambda environ=None: config)
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda *, timeout, proxy: _FakeHttpxClient(_FakeResponse(status_code=404, text="not found")),
    )
    monkeypatch.setattr(module, "SubtitleTranslatorService", _FakeTranslator)

    exit_code = module.main([])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "translation: fail" in output
    assert "字幕翻译链返回了非字符串译文行：index=2, type=int" in output
    assert "字幕 provider 自检失败" in output


def test_verify_subtitle_provider_smoke_fails_when_translation_chain_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.maintenance import verify_subtitle_provider_smoke as module

    config = module.SubtitleProviderSmokeConfig(
        api_key="demo-key",
        base_url="https://openai.example/v1",
        model="gpt-5.4-mini",
        timeout_seconds=30.0,
        proxy_url="",
    )

    class _FakeTranslator:
        def __init__(self, **kwargs) -> None:
            return None

        def _translate_lines_professional(
            self,
            *,
            source_lines: list[str],
            movie_title: str,
            trusted_name_map: dict[str, str] | None = None,
        ) -> list[str]:
            raise RuntimeError("请求超时：provider slow")

    monkeypatch.setattr(module, "load_subtitle_provider_smoke_config", lambda environ=None: config)
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda *, timeout, proxy: _FakeHttpxClient(_FakeResponse(status_code=404, text="not found")),
    )
    monkeypatch.setattr(module, "SubtitleTranslatorService", _FakeTranslator)

    exit_code = module.main([])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "translation: fail - 请求超时：provider slow" in output
    assert "字幕 provider 自检失败" in output
