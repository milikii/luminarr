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
    transmission_base_url: str
    transmission_username: str
    transmission_password: str
    library_target_dir: str


def _read_required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


def _read_optional(env: Mapping[str, str], key: str) -> str:
    return env.get(key, "").strip()


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    return Settings(
        telegram_bot_token=_read_required(env, "TELEGRAM_BOT_TOKEN"),
        prowlarr_base_url=_read_required(env, "PROWLARR_BASE_URL").rstrip("/"),
        prowlarr_api_key=_read_required(env, "PROWLARR_API_KEY"),
        transmission_base_url=_read_required(env, "TRANSMISSION_BASE_URL").rstrip("/"),
        transmission_username=_read_optional(env, "TRANSMISSION_USERNAME"),
        transmission_password=_read_optional(env, "TRANSMISSION_PASSWORD"),
        library_target_dir=_read_optional(env, "LIBRARY_TARGET_DIR") or "/data/library/movies",
    )
