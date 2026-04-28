from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeVar

_T = TypeVar("_T")


class ConfigError(ValueError):
    """Raised when required runtime configuration is missing."""


@dataclass(frozen=True, slots=True)
class RawBtDestinationOption:
    key: str
    label: str
    target_dir: str


@dataclass(frozen=True, slots=True)
class AdultArchiveDestination:
    category: str
    label: str
    target_dir: str


@dataclass(frozen=True, slots=True)
class DownloaderInstanceConfig:
    name: str
    downloader_type: str
    base_url: str
    download_dir: str
    dispatch_download_dir: str = ""
    username: str = ""
    password: str = ""


@dataclass(frozen=True, slots=True)
class DownloaderRoleBinding:
    pt_downloader: str
    bt_downloader: str


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    outbound_proxy_url: str
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
    media_server_provider: str
    emby_base_url: str
    emby_api_key: str
    jellyfin_base_url: str
    jellyfin_api_key: str
    plex_base_url: str
    plex_token: str
    subtitle_translation_api_key: str
    subtitle_translation_base_url: str
    subtitle_translation_model: str
    subtitle_translation_timeout_seconds: float
    pt_min_seed_hours: int
    sqlite_db_path: str
    raw_bt_destination_options: tuple[RawBtDestinationOption, ...]
    adult_archive_destinations: tuple[AdultArchiveDestination, ...]
    adult_bt_retention_hours: int
    bt_web_sources: tuple[str, ...]
    downloader_instances: tuple[DownloaderInstanceConfig, ...]
    downloader_role_binding: DownloaderRoleBinding | None
    feishu_app_id: str
    feishu_app_secret: str
    feishu_base_url: str
    wecom_token: str
    wecom_encoding_aes_key: str
    wecom_receive_id: str
    wecom_webhook_host: str
    wecom_webhook_port: int
    wecom_webhook_path: str

    def has_prowlarr_search(self) -> bool:
        return bool(self.prowlarr_base_url and self.prowlarr_api_key)

    def has_legacy_transmission_downloader(self) -> bool:
        return bool(self.transmission_base_url)

    def has_any_downloader_dispatch(self) -> bool:
        return self.has_legacy_transmission_downloader() or bool(self.downloader_instances)


def _read_required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


def _normalize_proxy_url(raw_value: str) -> str:
    cleaned_value = raw_value.strip()
    if not cleaned_value:
        return ""
    lowered_value = cleaned_value.lower()
    if lowered_value.startswith(("http://", "https://", "socks5://")):
        return cleaned_value
    raise ConfigError("OUTBOUND_PROXY_URL must start with http://, https:// or socks5://")


def _resolve_lower_choice(
    raw_value: str,
    *,
    aliases: Mapping[str, str],
    default: str,
    error_message: str,
) -> str:
    normalized_value = raw_value.strip().lower()
    if not normalized_value:
        return default
    resolved_value = aliases.get(normalized_value, "")
    if not resolved_value:
        raise ConfigError(error_message)
    return resolved_value


def _read_optional(env: Mapping[str, str], key: str) -> str:
    return env.get(key, "").strip()


def _read_optional_int_with_validator(
    env: Mapping[str, str],
    key: str,
    default: int,
    *,
    predicate: Callable[[int], bool],
    error_message: str,
) -> int:
    return _read_optional_parsed_value(
        env,
        key,
        default,
        parse=int,
        parse_error_message=f"{key} must be an integer",
        predicate=predicate,
        validation_error_message=error_message,
    )


def _read_optional_parsed_value(
    env: Mapping[str, str],
    key: str,
    default: _T,
    *,
    parse: Callable[[str], _T],
    parse_error_message: str,
    predicate: Callable[[_T], bool] | None = None,
    validation_error_message: str = "",
) -> _T:
    raw_value = _read_optional(env, key)
    if not raw_value:
        return default
    try:
        value = parse(raw_value)
    except ValueError as error:
        raise ConfigError(parse_error_message) from error
    if predicate is not None and not predicate(value):
        raise ConfigError(validation_error_message)
    return value


def _read_optional_float(env: Mapping[str, str], key: str, default: float) -> float:
    return _read_optional_parsed_value(
        env,
        key,
        default,
        parse=float,
        parse_error_message=f"{key} must be a number",
    )


def _read_optional_int(env: Mapping[str, str], key: str, default: int) -> int:
    return _read_optional_int_with_validator(
        env,
        key,
        default,
        predicate=lambda value: value > 0,
        error_message=f"{key} must be a positive integer",
    )


def _read_optional_non_negative_int(env: Mapping[str, str], key: str, default: int) -> int:
    return _read_optional_int_with_validator(
        env,
        key,
        default,
        predicate=lambda value: value >= 0,
        error_message=f"{key} must be a non-negative integer",
    )


def _normalize_http_path(raw_value: str, *, default: str) -> str:
    cleaned_value = raw_value.strip() or default
    if not cleaned_value.startswith("/"):
        return f"/{cleaned_value}"
    return cleaned_value


def _normalize_base_url(raw_value: str) -> str:
    return raw_value.strip().rstrip("/")


def _read_base_url(env: Mapping[str, str], key: str, *, required: bool = False) -> str:
    raw_value = _read_required(env, key) if required else _read_optional(env, key)
    return _normalize_base_url(raw_value)


def _read_optional_lower_choice(
    env: Mapping[str, str],
    key: str,
    *,
    default: str,
    allowed_values: tuple[str, ...],
    error_message: str,
) -> str:
    return _resolve_lower_choice(
        _read_optional(env, key),
        aliases={allowed_value: allowed_value for allowed_value in allowed_values},
        default=default,
        error_message=error_message,
    )


def _read_media_server_provider(env: Mapping[str, str]) -> str:
    return _read_optional_lower_choice(
        env,
        "MEDIA_SERVER_PROVIDER",
        default="emby",
        allowed_values=("emby", "jellyfin", "plex"),
        error_message="MEDIA_SERVER_PROVIDER must be emby, jellyfin or plex",
    )


def _iter_semicolon_entries(raw_value: str) -> tuple[str, ...]:
    return tuple(cleaned_item for raw_item in raw_value.split(";") if (cleaned_item := raw_item.strip()))


def _split_pipe_fields(cleaned_item: str) -> list[str]:
    return [part.strip() for part in cleaned_item.split("|")]


def _read_semicolon_delimited_records(
    env: Mapping[str, str],
    *,
    env_key: str,
    parser: Callable[[list[str]], _T],
) -> tuple[_T, ...]:
    raw_value = _read_optional(env, env_key)
    if not raw_value:
        return ()
    return tuple(parser(_split_pipe_fields(cleaned_item)) for cleaned_item in _iter_semicolon_entries(raw_value))


def _parse_labelled_destination_record(
    parts: list[str],
    *,
    kind: str,
    empty_value_name: str,
    build: Callable[[str, str, str], _T],
) -> _T:
    if len(parts) == 2:
        raw_value, target_dir = parts
        label = raw_value
    elif len(parts) == 3:
        raw_value, label, target_dir = parts
    else:
        raise ConfigError(
            f"{kind} format must be `{empty_value_name}|target_dir` or "
            f"`{empty_value_name}|label|target_dir`, separated by `;`"
        )

    normalized_value = raw_value.lower().strip()
    if not normalized_value:
        raise ConfigError(f"{kind} {empty_value_name} cannot be empty")
    if not label:
        raise ConfigError(f"{kind} label cannot be empty: {normalized_value}")
    if not target_dir:
        raise ConfigError(f"{kind} target_dir cannot be empty: {normalized_value}")

    return build(normalized_value, label, target_dir)


def _parse_raw_bt_destination(parts: list[str]) -> RawBtDestinationOption:
    return _parse_labelled_destination_record(
        parts,
        kind="RAW_BT_DESTINATIONS",
        empty_value_name="key",
        build=lambda key, label, target_dir: RawBtDestinationOption(
            key=key,
            label=label,
            target_dir=target_dir,
        ),
    )


def _parse_adult_archive_destination(parts: list[str]) -> AdultArchiveDestination:
    return _parse_labelled_destination_record(
        parts,
        kind="ADULT_ARCHIVE_DESTINATIONS",
        empty_value_name="category",
        build=lambda category, label, target_dir: AdultArchiveDestination(
            category=category,
            label=label,
            target_dir=target_dir,
        ),
    )


def _read_raw_bt_destination_options(env: Mapping[str, str]) -> tuple[RawBtDestinationOption, ...]:
    return _read_semicolon_delimited_records(env, env_key="RAW_BT_DESTINATIONS", parser=_parse_raw_bt_destination)


def _read_adult_archive_destinations(env: Mapping[str, str]) -> tuple[AdultArchiveDestination, ...]:
    return _read_semicolon_delimited_records(
        env,
        env_key="ADULT_ARCHIVE_DESTINATIONS",
        parser=_parse_adult_archive_destination,
    )


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
    return _resolve_lower_choice(
        raw_value,
        aliases={
            "transmission": "transmission",
            "tr": "transmission",
            "qbittorrent": "qbittorrent",
            "qb": "qbittorrent",
        },
        default="",
        error_message=f"DOWNLOADER_INSTANCES downloader_type must be transmission or qbittorrent, got: {raw_value}",
    )


def _read_downloader_instances(env: Mapping[str, str]) -> tuple[DownloaderInstanceConfig, ...]:
    raw_value = _read_optional(env, "DOWNLOADER_INSTANCES")
    if not raw_value:
        return ()

    instances: list[DownloaderInstanceConfig] = []
    seen_names: set[str] = set()
    def parse_instance(parts: list[str]) -> DownloaderInstanceConfig:
        if len(parts) not in {4, 5, 6, 7}:
            raise ConfigError(
                "DOWNLOADER_INSTANCES format must be `name|type|base_url|download_dir`, "
                "`name|type|base_url|download_dir|dispatch_download_dir`, "
                "`name|type|base_url|download_dir|username|password` or "
                "`name|type|base_url|download_dir|dispatch_download_dir|username|password`, separated by `;`"
            )

        name = parts[0]
        downloader_type = _normalize_downloader_type(parts[1])
        if not downloader_type:
            raise ConfigError(
                f"DOWNLOADER_INSTANCES downloader_type must be transmission (tr) or qbittorrent (qb), got: {parts[1]!r}"
            )
        base_url = _normalize_base_url(parts[2])
        download_dir = parts[3]
        dispatch_download_dir = ""
        username = ""
        password = ""
        if len(parts) in {5, 7}:
            dispatch_download_dir = parts[4]
        if len(parts) == 6:
            username = parts[4]
            password = parts[5]
        if len(parts) == 7:
            username = parts[5]
            password = parts[6]

        if not name:
            raise ConfigError("DOWNLOADER_INSTANCES name cannot be empty")
        if name in seen_names:
            raise ConfigError(f"DOWNLOADER_INSTANCES contains duplicate name: {name}")
        if not base_url:
            raise ConfigError(f"DOWNLOADER_INSTANCES base_url cannot be empty: {name}")
        if not download_dir:
            raise ConfigError(f"DOWNLOADER_INSTANCES download_dir cannot be empty: {name}")
        if len(parts) in {5, 7} and not dispatch_download_dir:
            raise ConfigError(f"DOWNLOADER_INSTANCES dispatch_download_dir cannot be empty: {name}")

        seen_names.add(name)
        return DownloaderInstanceConfig(
            name=name,
            downloader_type=downloader_type,
            base_url=base_url,
            download_dir=download_dir,
            dispatch_download_dir=dispatch_download_dir,
            username=username,
            password=password,
        )

    for cleaned_item in _iter_semicolon_entries(raw_value):
        instances.append(parse_instance(_split_pipe_fields(cleaned_item)))

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


def _require_complete_credential_set(*, has_any: bool, has_all: bool, error_message: str) -> None:
    if has_any and not has_all:
        raise ConfigError(error_message)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    emby_base_url = _read_base_url(env, "EMBY_BASE_URL")
    jellyfin_base_url = _read_base_url(env, "JELLYFIN_BASE_URL")
    plex_base_url = _read_base_url(env, "PLEX_BASE_URL")
    tmdb_base_url = _read_base_url(env, "TMDB_BASE_URL")
    fanart_base_url = _read_base_url(env, "FANART_BASE_URL")
    subtitle_translation_base_url = _read_base_url(env, "SUBTITLE_TRANSLATION_BASE_URL")
    feishu_base_url = _read_base_url(env, "FEISHU_BASE_URL")
    prowlarr_base_url = _read_base_url(env, "PROWLARR_BASE_URL")
    prowlarr_api_key = _read_optional(env, "PROWLARR_API_KEY")
    _require_complete_credential_set(
        has_any=bool(prowlarr_base_url or prowlarr_api_key),
        has_all=bool(prowlarr_base_url and prowlarr_api_key),
        error_message="PROWLARR_BASE_URL and PROWLARR_API_KEY must be set together",
    )
    transmission_base_url = _read_base_url(env, "TRANSMISSION_BASE_URL")
    subtitle_translation_timeout_seconds = _read_optional_float(
        env,
        "SUBTITLE_TRANSLATION_TIMEOUT_SECONDS",
        60.0,
    )
    feishu_app_id = _read_optional(env, "FEISHU_APP_ID")
    feishu_app_secret = _read_optional(env, "FEISHU_APP_SECRET")
    has_any_feishu_credential = bool(feishu_app_id or feishu_app_secret)
    has_feishu_app_credentials = bool(feishu_app_id and feishu_app_secret)
    _require_complete_credential_set(
        has_any=has_any_feishu_credential,
        has_all=has_feishu_app_credentials,
        error_message="FEISHU_APP_ID and FEISHU_APP_SECRET must be set together",
    )
    wecom_token = _read_optional(env, "WECOM_TOKEN")
    wecom_encoding_aes_key = _read_optional(env, "WECOM_ENCODING_AES_KEY")
    wecom_receive_id = _read_optional(env, "WECOM_RECEIVE_ID")
    has_any_wecom_credential = bool(wecom_token or wecom_encoding_aes_key or wecom_receive_id)
    has_all_wecom_credentials = bool(wecom_token and wecom_encoding_aes_key and wecom_receive_id)
    _require_complete_credential_set(
        has_any=has_any_wecom_credential,
        has_all=has_all_wecom_credentials,
        error_message="WECOM_TOKEN, WECOM_ENCODING_AES_KEY and WECOM_RECEIVE_ID must be set together",
    )
    downloader_instances = _read_downloader_instances(env)
    if not transmission_base_url and not downloader_instances:
        raise ConfigError("TRANSMISSION_BASE_URL or DOWNLOADER_INSTANCES is required")
    return Settings(
        telegram_bot_token=_read_required(env, "TELEGRAM_BOT_TOKEN"),
        outbound_proxy_url=_normalize_proxy_url(_read_optional(env, "OUTBOUND_PROXY_URL")),
        prowlarr_base_url=prowlarr_base_url,
        prowlarr_api_key=prowlarr_api_key,
        tmdb_base_url=tmdb_base_url or "https://api.themoviedb.org",
        tmdb_api_key=_read_optional(env, "TMDB_API_KEY"),
        fanart_base_url=fanart_base_url or "https://webservice.fanart.tv/v3",
        fanart_api_key=_read_optional(env, "FANART_API_KEY"),
        transmission_base_url=transmission_base_url,
        transmission_username=_read_optional(env, "TRANSMISSION_USERNAME"),
        transmission_password=_read_optional(env, "TRANSMISSION_PASSWORD"),
        library_target_dir=_read_optional(env, "LIBRARY_TARGET_DIR") or "/data/library/movies",
        media_server_provider=_read_media_server_provider(env),
        emby_base_url=emby_base_url,
        emby_api_key=_read_optional(env, "EMBY_API_KEY"),
        jellyfin_base_url=jellyfin_base_url,
        jellyfin_api_key=_read_optional(env, "JELLYFIN_API_KEY"),
        plex_base_url=plex_base_url,
        plex_token=_read_optional(env, "PLEX_TOKEN"),
        subtitle_translation_api_key=_read_optional(env, "SUBTITLE_TRANSLATION_API_KEY"),
        subtitle_translation_base_url=subtitle_translation_base_url or "https://api.openai.com/v1",
        subtitle_translation_model=_read_optional(env, "SUBTITLE_TRANSLATION_MODEL") or "gpt-5.4",
        subtitle_translation_timeout_seconds=subtitle_translation_timeout_seconds,
        pt_min_seed_hours=_read_optional_non_negative_int(env, "PT_MIN_SEED_HOURS", 0),
        sqlite_db_path=_read_optional(env, "SQLITE_DB_PATH") or "/data/luminarr.db",
        raw_bt_destination_options=_read_raw_bt_destination_options(env),
        adult_archive_destinations=_read_adult_archive_destinations(env),
        adult_bt_retention_hours=_read_optional_non_negative_int(env, "ADULT_BT_RETENTION_HOURS", 96),
        bt_web_sources=_read_bt_web_sources(env),
        downloader_instances=downloader_instances,
        downloader_role_binding=_read_downloader_role_binding(env, downloader_instances),
        feishu_app_id=feishu_app_id,
        feishu_app_secret=feishu_app_secret,
        feishu_base_url=feishu_base_url or "https://open.feishu.cn",
        wecom_token=wecom_token,
        wecom_encoding_aes_key=wecom_encoding_aes_key,
        wecom_receive_id=wecom_receive_id,
        wecom_webhook_host=_read_optional(env, "WECOM_WEBHOOK_HOST") or "0.0.0.0",
        wecom_webhook_port=_read_optional_int(env, "WECOM_WEBHOOK_PORT", 18097),
        wecom_webhook_path=_normalize_http_path(
            _read_optional(env, "WECOM_WEBHOOK_PATH"),
            default="/wecom/webhook",
        ),
    )
