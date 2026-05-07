from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx

from app.config import ConfigError
from app.services.subtitle_translator import SubtitleTranslatorService

_SMOKE_MOVIE_TITLE = "Subtitle Provider Smoke Check"
_SMOKE_SOURCE_LINES = (
    "Hello there.",
    "This is a subtitle provider smoke test.",
    "Keep one subtitle line mapped to exactly one Chinese line.",
)


@dataclass(frozen=True, slots=True)
class SubtitleProviderSmokeConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    proxy_url: str


def load_subtitle_provider_smoke_config(environ: Mapping[str, str] | None = None) -> SubtitleProviderSmokeConfig:
    """Load only the subtitle-provider env needed by the smoke tool."""
    env = os.environ if environ is None else environ
    raw_timeout = env.get("SUBTITLE_TRANSLATION_TIMEOUT_SECONDS", "").strip()
    timeout_seconds = 60.0
    if raw_timeout:
        try:
            timeout_seconds = float(raw_timeout)
        except ValueError as exc:
            raise ConfigError("SUBTITLE_TRANSLATION_TIMEOUT_SECONDS must be a number") from exc
    raw_proxy = env.get("OUTBOUND_PROXY_URL", "").strip()
    if raw_proxy and not raw_proxy.lower().startswith(("http://", "https://", "socks5://")):
        raise ConfigError("OUTBOUND_PROXY_URL must start with http://, https:// or socks5://")
    return SubtitleProviderSmokeConfig(
        api_key=env.get("SUBTITLE_TRANSLATION_API_KEY", "").strip(),
        base_url=(env.get("SUBTITLE_TRANSLATION_BASE_URL", "").strip() or "https://api.openai.com/v1").rstrip("/"),
        model=env.get("SUBTITLE_TRANSLATION_MODEL", "").strip() or "gpt-5.4",
        timeout_seconds=timeout_seconds,
        proxy_url=raw_proxy,
    )


def _print_summary(*, config: SubtitleProviderSmokeConfig) -> None:
    print("字幕 provider 自检")
    print(f"base_url={config.base_url}")
    print(f"model={config.model}")
    print(f"proxy={config.proxy_url or 'direct'}")


def _extract_model_ids(payload: object) -> list[str]:
    if isinstance(payload, dict):
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise ValueError("models payload missing data array")
    elif isinstance(payload, list):
        rows = payload
    else:
        raise ValueError("models payload root must be object or list")
    result: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = row.get("id")
        if isinstance(model_id, str) and model_id.strip():
            result.append(model_id.strip())
    return result


def _check_models_endpoint(config: SubtitleProviderSmokeConfig) -> tuple[str, str]:
    try:
        with httpx.Client(timeout=config.timeout_seconds, proxy=config.proxy_url or None) as client:
            response = client.get(
                f"{config.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {config.api_key}"},
            )
    except httpx.HTTPError as exc:
        return "warning", f"provider 未提供可校验的 /models 能力：{exc}"
    if response.status_code >= 400:
        return "warning", f"provider 未提供可校验的 /models 能力：HTTP {response.status_code}"
    try:
        model_ids = _extract_model_ids(response.json())
    except (ValueError, TypeError) as exc:
        return "warning", f"provider 未提供可校验的 /models 能力：{exc}"
    if not model_ids:
        return "warning", "provider 未提供可校验的 /models 能力：模型列表为空"
    if config.model not in model_ids:
        return "fail", f"当前 model 未出现在 provider 模型列表中：{config.model}"
    return "ok", f"provider 已声明当前 model：{config.model}"


def _run_translation_smoke(config: SubtitleProviderSmokeConfig) -> tuple[str, str]:
    translator = SubtitleTranslatorService(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
        proxy_url=config.proxy_url,
    )
    try:
        translated_lines = translator._translate_lines_professional(
            source_lines=list(_SMOKE_SOURCE_LINES),
            movie_title=_SMOKE_MOVIE_TITLE,
            trusted_name_map={},
        )
    except RuntimeError as exc:
        return "fail", str(exc)
    if len(translated_lines) != len(_SMOKE_SOURCE_LINES):
        return "fail", f"字幕翻译链返回了异常行数：source={len(_SMOKE_SOURCE_LINES)}, translated={len(translated_lines)}"
    for index, line in enumerate(translated_lines, start=1):
        if not isinstance(line, str):
            return "fail", f"字幕翻译链返回了非字符串译文行：index={index}, type={type(line).__name__}"
        if not line.strip():
            return "fail", f"字幕翻译链返回了空译文行：index={index}"
    return "ok", f"{len(translated_lines)}/{len(_SMOKE_SOURCE_LINES)}"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the operator-facing subtitle provider smoke verification."""
    _ = argv
    try:
        config = load_subtitle_provider_smoke_config()
    except ConfigError as exc:
        print("字幕 provider 自检失败")
        print(str(exc))
        return 1

    _print_summary(config=config)
    if not config.api_key.strip():
        print("/models: warning - 缺少 API Key，跳过 provider 模型列表校验。")
        print("translation: fail - 缺少 SUBTITLE_TRANSLATION_API_KEY。")
        print("字幕 provider 自检失败")
        return 1

    models_status, models_message = _check_models_endpoint(config)
    print(f"/models: {models_status} - {models_message}")
    if models_status == "fail":
        print("字幕 provider 自检失败")
        return 1

    translation_status, translation_message = _run_translation_smoke(config)
    print(f"translation: {translation_status} ({translation_message})" if translation_status == "ok" else f"translation: {translation_status} - {translation_message}")
    if translation_status != "ok":
        print("字幕 provider 自检失败")
        return 1

    print("字幕 provider 自检通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
