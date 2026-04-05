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
class DownloaderInstanceConfig:
    name: str
    downloader_type: str
    base_url: str
    download_dir: str
    username: str = ""
    password: str = ""


@dataclass(frozen=True, slots=True)
class DownloaderRoleBinding:
    pt_downloader: str
    bt_downloader: str


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
    bt_web_sources: tuple[str, ...]
    downloader_instances: tuple[DownloaderInstanceConfig, ...]
    downloader_role_binding: DownloaderRoleBinding | None
    feishu_app_id: str
    feishu_app_secret: str
    feishu_encrypt_key: str
    feishu_base_url: str
    feishu_webhook_host: str
    feishu_webhook_port: int
    feishu_webhook_path: str


def _read_required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


def _read_optional(env: Mapping[str, str], key: str) -> str:
    return env.get(key, "").strip()


def _read_optional_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw_value = _read_optional(env, key)
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ConfigError(f"{key} must be an integer") from error
    if value <= 0:
        raise ConfigError(f"{key} must be a positive integer")
    return value


def _normalize_http_path(raw_value: str, *, default: str) -> str:
    cleaned_value = raw_value.strip() or default
    if not cleaned_value.startswith("/"):
        return f"/{cleaned_value}"
    return cleaned_value


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


def _read_bt_web_sources(env: Mapping[str, str]) -> tuple[str, ...]:
    raw_value = _read_optional(env, "BT_WEB_SOURCES")
    if not raw_value:
        return ()

    sources: list[str] = []
    seen_sources: set[str] = set()
    for raw_item in raw_value.replace(";", ",").split(","):
        source_name = raw_item.strip().lower()
        if not source_name or source_name in seen_sources:
            continue
        seen_sources.add(source_name)
        sources.append(source_name)
    return tuple(sources)


def _normalize_downloader_type(raw_value: str) -> str:
    normalized_value = raw_value.strip().lower()
    aliases = {
        "transmission": "transmission",
        "tr": "transmission",
        "qbittorrent": "qbittorrent",
        "qb": "qbittorrent",
    }
    resolved_value = aliases.get(normalized_value, "")
    if not resolved_value:
        raise ConfigError(
            f"DOWNLOADER_INSTANCES downloader_type must be transmission or qbittorrent, got: {raw_value}"
        )
    return resolved_value


def _read_downloader_instances(env: Mapping[str, str]) -> tuple[DownloaderInstanceConfig, ...]:
    raw_value = _read_optional(env, "DOWNLOADER_INSTANCES")
    if not raw_value:
        return ()

    instances: list[DownloaderInstanceConfig] = []
    seen_names: set[str] = set()
    for raw_item in raw_value.split(";"):
        cleaned_item = raw_item.strip()
        if not cleaned_item:
            continue

        parts = [part.strip() for part in cleaned_item.split("|")]
        if len(parts) not in {4, 6}:
            raise ConfigError(
                "DOWNLOADER_INSTANCES format must be `name|type|base_url|download_dir` or `name|type|base_url|download_dir|username|password`, separated by `;`"
            )

        name = parts[0]
        downloader_type = _normalize_downloader_type(parts[1])
        base_url = parts[2].rstrip("/")
        download_dir = parts[3]
        username = ""
        password = ""
        if len(parts) == 6:
            username = parts[4]
            password = parts[5]

        if not name:
            raise ConfigError("DOWNLOADER_INSTANCES name cannot be empty")
        if name in seen_names:
            raise ConfigError(f"DOWNLOADER_INSTANCES contains duplicate name: {name}")
        if not base_url:
            raise ConfigError(f"DOWNLOADER_INSTANCES base_url cannot be empty: {name}")
        if not download_dir:
            raise ConfigError(f"DOWNLOADER_INSTANCES download_dir cannot be empty: {name}")

        seen_names.add(name)
        instances.append(
            DownloaderInstanceConfig(
                name=name,
                downloader_type=downloader_type,
                base_url=base_url,
                download_dir=download_dir,
                username=username,
                password=password,
            )
        )

    return tuple(instances)


def _read_downloader_role_binding(
    env: Mapping[str, str],
    instances: tuple[DownloaderInstanceConfig, ...],
) -> DownloaderRoleBinding | None:
    if not instances:
        return None

    instance_names = {instance.name for instance in instances}
    default_instance_name = instances[0].name
    pt_downloader = _read_optional(env, "PT_DOWNLOADER") or default_instance_name
    bt_downloader = _read_optional(env, "BT_DOWNLOADER") or default_instance_name

    if pt_downloader not in instance_names:
        raise ConfigError(f"PT_DOWNLOADER must match a configured downloader instance: {pt_downloader}")
    if bt_downloader not in instance_names:
        raise ConfigError(f"BT_DOWNLOADER must match a configured downloader instance: {bt_downloader}")

    return DownloaderRoleBinding(
        pt_downloader=pt_downloader,
        bt_downloader=bt_downloader,
    )


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    emby_base_url = _read_optional(env, "EMBY_BASE_URL").rstrip("/")
    tmdb_base_url = _read_optional(env, "TMDB_BASE_URL").rstrip("/")
    fanart_base_url = _read_optional(env, "FANART_BASE_URL").rstrip("/")
    subtitle_translation_base_url = _read_optional(env, "SUBTITLE_TRANSLATION_BASE_URL").rstrip("/")
    feishu_base_url = _read_optional(env, "FEISHU_BASE_URL").rstrip("/")
    subtitle_translation_timeout_raw = _read_optional(env, "SUBTITLE_TRANSLATION_TIMEOUT_SECONDS")
    subtitle_translation_timeout_seconds = 60.0
    if subtitle_translation_timeout_raw:
        try:
            subtitle_translation_timeout_seconds = float(subtitle_translation_timeout_raw)
        except ValueError:
            raise ConfigError("SUBTITLE_TRANSLATION_TIMEOUT_SECONDS must be a number")
    feishu_app_id = _read_optional(env, "FEISHU_APP_ID")
    feishu_app_secret = _read_optional(env, "FEISHU_APP_SECRET")
    feishu_encrypt_key = _read_optional(env, "FEISHU_ENCRYPT_KEY")
    has_any_feishu_credential = bool(feishu_app_id or feishu_app_secret or feishu_encrypt_key)
    has_all_feishu_credentials = bool(feishu_app_id and feishu_app_secret and feishu_encrypt_key)
    if has_any_feishu_credential and not has_all_feishu_credentials:
        raise ConfigError("FEISHU_APP_ID, FEISHU_APP_SECRET and FEISHU_ENCRYPT_KEY must be set together")
    downloader_instances = _read_downloader_instances(env)
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
        bt_web_sources=_read_bt_web_sources(env),
        downloader_instances=downloader_instances,
        downloader_role_binding=_read_downloader_role_binding(env, downloader_instances),
        feishu_app_id=feishu_app_id,
        feishu_app_secret=feishu_app_secret,
        feishu_encrypt_key=feishu_encrypt_key,
        feishu_base_url=feishu_base_url or "https://open.feishu.cn",
        feishu_webhook_host=_read_optional(env, "FEISHU_WEBHOOK_HOST") or "0.0.0.0",
        feishu_webhook_port=_read_optional_int(env, "FEISHU_WEBHOOK_PORT", 18095),
        feishu_webhook_path=_normalize_http_path(
            _read_optional(env, "FEISHU_WEBHOOK_PATH"),
            default="/feishu/webhook",
        ),
    )
