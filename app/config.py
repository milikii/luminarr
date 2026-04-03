from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(ValueError):
    """Raised when required runtime configuration is missing."""


@dataclass(frozen=True, slots=True)
class RawBtDestinationOption:
    key: str
    label: str
    target_dir: str


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
    subtitle_translation_api_key: str
    subtitle_translation_base_url: str
    subtitle_translation_model: str
    subtitle_translation_timeout_seconds: float
    sqlite_db_path: str
    raw_bt_destination_options: tuple[RawBtDestinationOption, ...]


def _read_required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


def _read_optional(env: Mapping[str, str], key: str) -> str:
    return env.get(key, "").strip()


def _read_raw_bt_destination_options(env: Mapping[str, str]) -> tuple[RawBtDestinationOption, ...]:
    raw_value = _read_optional(env, "RAW_BT_DESTINATIONS")
    if not raw_value:
        return ()

    options: list[RawBtDestinationOption] = []
    seen_keys: set[str] = set()
    for raw_item in raw_value.split(";"):
        cleaned_item = raw_item.strip()
        if not cleaned_item:
            continue

        parts = [part.strip() for part in cleaned_item.split("|")]
        if len(parts) == 2:
            key, target_dir = parts
            label = key
        elif len(parts) == 3:
            key, label, target_dir = parts
        else:
            raise ConfigError(
                "RAW_BT_DESTINATIONS format must be `key|target_dir` or `key|label|target_dir`, separated by `;`"
            )

        normalized_key = key.lower().strip()
        if not normalized_key:
            raise ConfigError("RAW_BT_DESTINATIONS key cannot be empty")
        if normalized_key in seen_keys:
            raise ConfigError(f"RAW_BT_DESTINATIONS contains duplicate key: {normalized_key}")
        if not label:
            raise ConfigError(f"RAW_BT_DESTINATIONS label cannot be empty: {normalized_key}")
        if not target_dir:
            raise ConfigError(f"RAW_BT_DESTINATIONS target_dir cannot be empty: {normalized_key}")

        seen_keys.add(normalized_key)
        options.append(
            RawBtDestinationOption(
                key=normalized_key,
                label=label,
                target_dir=target_dir,
            )
        )

    return tuple(options)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    emby_base_url = _read_optional(env, "EMBY_BASE_URL").rstrip("/")
    tmdb_base_url = _read_optional(env, "TMDB_BASE_URL").rstrip("/")
    fanart_base_url = _read_optional(env, "FANART_BASE_URL").rstrip("/")
    subtitle_translation_base_url = _read_optional(env, "SUBTITLE_TRANSLATION_BASE_URL").rstrip("/")
    subtitle_translation_timeout_raw = _read_optional(env, "SUBTITLE_TRANSLATION_TIMEOUT_SECONDS")
    subtitle_translation_timeout_seconds = 60.0
    if subtitle_translation_timeout_raw:
        try:
            subtitle_translation_timeout_seconds = float(subtitle_translation_timeout_raw)
        except ValueError:
            raise ConfigError("SUBTITLE_TRANSLATION_TIMEOUT_SECONDS must be a number")
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
        subtitle_translation_api_key=_read_optional(env, "SUBTITLE_TRANSLATION_API_KEY"),
        subtitle_translation_base_url=subtitle_translation_base_url or "https://api.openai.com/v1",
        subtitle_translation_model=_read_optional(env, "SUBTITLE_TRANSLATION_MODEL") or "gpt-5.4",
        subtitle_translation_timeout_seconds=subtitle_translation_timeout_seconds,
        sqlite_db_path=_read_optional(env, "SQLITE_DB_PATH") or "/data/luminarr.db",
        raw_bt_destination_options=_read_raw_bt_destination_options(env),
    )
