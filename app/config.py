from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(ValueError):
    """Raised when required runtime configuration is missing."""


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    prowlarr_base_url: str
    prowlarr_api_key: str


def _read_required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    return Settings(
        telegram_bot_token=_read_required(env, "TELEGRAM_BOT_TOKEN"),
        prowlarr_base_url=_read_required(env, "PROWLARR_BASE_URL").rstrip("/"),
        prowlarr_api_key=_read_required(env, "PROWLARR_API_KEY"),
    )
