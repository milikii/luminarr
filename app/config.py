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
    tmdb_base_url: str
    tmdb_api_key: str
    fanart_base_url: str
    fanart_api_key: str
    transmission_base_url: str
    transmission_username: str
    transmission_password: str
    library_target_dir: str
    emby_base_url: str
    emby_api_key: str
    sqlite_db_path: str


def _read_required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


def _read_optional(env: Mapping[str, str], key: str) -> str:
    return env.get(key, "").strip()


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    emby_base_url = _read_optional(env, "EMBY_BASE_URL").rstrip("/")
    tmdb_base_url = _read_optional(env, "TMDB_BASE_URL").rstrip("/")
    fanart_base_url = _read_optional(env, "FANART_BASE_URL").rstrip("/")
    return Settings(
        telegram_bot_token=_read_required(env, "TELEGRAM_BOT_TOKEN"),
        prowlarr_base_url=_read_required(env, "PROWLARR_BASE_URL").rstrip("/"),
        prowlarr_api_key=_read_required(env, "PROWLARR_API_KEY"),
        tmdb_base_url=tmdb_base_url or "https://api.themoviedb.org",
        tmdb_api_key=_read_optional(env, "TMDB_API_KEY"),
        fanart_base_url=fanart_base_url or "https://webservice.fanart.tv/v3",
        fanart_api_key=_read_optional(env, "FANART_API_KEY"),
        transmission_base_url=_read_required(env, "TRANSMISSION_BASE_URL").rstrip("/"),
        transmission_username=_read_optional(env, "TRANSMISSION_USERNAME"),
        transmission_password=_read_optional(env, "TRANSMISSION_PASSWORD"),
        library_target_dir=_read_optional(env, "LIBRARY_TARGET_DIR") or "/data/library/movies",
        emby_base_url=emby_base_url,
        emby_api_key=_read_optional(env, "EMBY_API_KEY"),
        sqlite_db_path=_read_optional(env, "SQLITE_DB_PATH") or "/data/luminarr.db",
    )
