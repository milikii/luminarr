from __future__ import annotations

import pytest

from app.config import ConfigError, load_settings


def test_load_settings_reads_token() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "TRANSMISSION_USERNAME": "tr-user",
            "TRANSMISSION_PASSWORD": "tr-pass",
        }
    )
    assert settings.telegram_bot_token == "token-value"
    assert settings.outbound_proxy_url == ""
    assert settings.prowlarr_base_url == "http://prowlarr:9696"
    assert settings.prowlarr_api_key == "api-key"
    assert settings.tmdb_base_url == "https://api.themoviedb.org"
    assert settings.tmdb_api_key == ""
    assert settings.fanart_base_url == "https://webservice.fanart.tv/v3"
    assert settings.fanart_api_key == ""
    assert settings.transmission_base_url == "http://transmission:9091"
    assert settings.transmission_username == "tr-user"
    assert settings.transmission_password == "tr-pass"
    assert settings.library_target_dir == "/data/library/movies"
    assert settings.media_server_provider == "emby"
    assert settings.emby_base_url == ""
    assert settings.emby_api_key == ""
    assert settings.jellyfin_base_url == ""
    assert settings.jellyfin_api_key == ""
    assert settings.plex_base_url == ""
    assert settings.plex_token == ""
    assert settings.subtitle_translation_api_key == ""
    assert settings.subtitle_translation_base_url == "https://api.openai.com/v1"
    assert settings.subtitle_translation_model == "gpt-5.4"
    assert settings.subtitle_translation_timeout_seconds == 60.0
    assert settings.sqlite_db_path == "/data/luminarr.db"
    assert settings.feishu_app_id == ""
    assert settings.feishu_app_secret == ""
    assert settings.feishu_encrypt_key == ""
    assert settings.feishu_inbound_mode == "webhook"
    assert settings.feishu_base_url == "https://open.feishu.cn"
    assert settings.feishu_webhook_host == "0.0.0.0"
    assert settings.feishu_webhook_port == 18095
    assert settings.feishu_webhook_path == "/feishu/webhook"
    assert settings.wecom_token == ""
    assert settings.wecom_encoding_aes_key == ""
    assert settings.wecom_receive_id == ""
    assert settings.wecom_webhook_host == "0.0.0.0"
    assert settings.wecom_webhook_port == 18097
    assert settings.wecom_webhook_path == "/wecom/webhook"
    assert settings.adult_archive_destinations == ()
    assert settings.adult_bt_retention_hours == 96


def test_load_settings_reads_outbound_proxy_url() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "OUTBOUND_PROXY_URL": "http://192.168.2.110:7890",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
        }
    )
    assert settings.outbound_proxy_url == "http://192.168.2.110:7890"


def test_load_settings_rejects_proxy_without_supported_scheme() -> None:
    with pytest.raises(ConfigError, match="OUTBOUND_PROXY_URL"):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token-value",
                "OUTBOUND_PROXY_URL": "192.168.2.110:7890",
                "PROWLARR_BASE_URL": "http://prowlarr:9696/",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            }
        )


def test_load_settings_reads_library_target_dir() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "LIBRARY_TARGET_DIR": "/data/library/anime",
        }
    )
    assert settings.library_target_dir == "/data/library/anime"


def test_load_settings_reads_emby_settings() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "EMBY_BASE_URL": "http://emby:8096/",
            "EMBY_API_KEY": "emby-api-key",
        }
    )
    assert settings.emby_base_url == "http://emby:8096"
    assert settings.emby_api_key == "emby-api-key"


def test_load_settings_reads_jellyfin_settings() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "MEDIA_SERVER_PROVIDER": "jellyfin",
            "JELLYFIN_BASE_URL": "http://jellyfin:8096/",
            "JELLYFIN_API_KEY": "jellyfin-api-key",
        }
    )
    assert settings.media_server_provider == "jellyfin"
    assert settings.jellyfin_base_url == "http://jellyfin:8096"
    assert settings.jellyfin_api_key == "jellyfin-api-key"


def test_load_settings_rejects_unknown_media_server_provider() -> None:
    with pytest.raises(ConfigError, match="MEDIA_SERVER_PROVIDER"):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token-value",
                "PROWLARR_BASE_URL": "http://prowlarr:9696/",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091/",
                "MEDIA_SERVER_PROVIDER": "kodi",
            }
        )


def test_load_settings_reads_plex_settings() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "MEDIA_SERVER_PROVIDER": "plex",
            "PLEX_BASE_URL": "http://plex:32400/",
            "PLEX_TOKEN": "plex-token",
        }
    )
    assert settings.media_server_provider == "plex"
    assert settings.plex_base_url == "http://plex:32400"
    assert settings.plex_token == "plex-token"


def test_load_settings_reads_tmdb_settings() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TMDB_BASE_URL": "https://tmdb.example/",
            "TMDB_API_KEY": "tmdb-api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
        }
    )
    assert settings.tmdb_base_url == "https://tmdb.example"
    assert settings.tmdb_api_key == "tmdb-api-key"


def test_load_settings_reads_fanart_settings() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "FANART_BASE_URL": "https://fanart.example/",
            "FANART_API_KEY": "fanart-api-key",
        }
    )
    assert settings.fanart_base_url == "https://fanart.example"
    assert settings.fanart_api_key == "fanart-api-key"


def test_load_settings_reads_sqlite_path() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "SQLITE_DB_PATH": "/data/luminarr/state.db",
        }
    )
    assert settings.sqlite_db_path == "/data/luminarr/state.db"


def test_load_settings_reads_subtitle_translation_settings() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "SUBTITLE_TRANSLATION_API_KEY": "st-key",
            "SUBTITLE_TRANSLATION_BASE_URL": "https://openai.example/v1/",
            "SUBTITLE_TRANSLATION_MODEL": "gpt-5.4",
            "SUBTITLE_TRANSLATION_TIMEOUT_SECONDS": "45",
        }
    )
    assert settings.subtitle_translation_api_key == "st-key"
    assert settings.subtitle_translation_base_url == "https://openai.example/v1"
    assert settings.subtitle_translation_model == "gpt-5.4"
    assert settings.subtitle_translation_timeout_seconds == 45.0


def test_load_settings_reads_feishu_settings() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "FEISHU_APP_ID": "cli_a",
            "FEISHU_APP_SECRET": "sec_b",
            "FEISHU_ENCRYPT_KEY": "encrypt-key-42",
            "FEISHU_BASE_URL": "https://open.feishu.test/",
            "FEISHU_WEBHOOK_HOST": "127.0.0.1",
            "FEISHU_WEBHOOK_PORT": "18096",
            "FEISHU_WEBHOOK_PATH": "hooks/feishu",
        }
    )

    assert settings.feishu_app_id == "cli_a"
    assert settings.feishu_app_secret == "sec_b"
    assert settings.feishu_encrypt_key == "encrypt-key-42"
    assert settings.feishu_base_url == "https://open.feishu.test"
    assert settings.feishu_webhook_host == "127.0.0.1"
    assert settings.feishu_webhook_port == 18096
    assert settings.feishu_webhook_path == "/hooks/feishu"


def test_load_settings_reads_wecom_settings() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "WECOM_TOKEN": "wecom-token-42",
            "WECOM_ENCODING_AES_KEY": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
            "WECOM_RECEIVE_ID": "wwcorp123",
            "WECOM_WEBHOOK_HOST": "127.0.0.1",
            "WECOM_WEBHOOK_PORT": "18101",
            "WECOM_WEBHOOK_PATH": "hooks/wecom",
        }
    )

    assert settings.wecom_token == "wecom-token-42"
    assert settings.wecom_encoding_aes_key == "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY"
    assert settings.wecom_receive_id == "wwcorp123"
    assert settings.wecom_webhook_host == "127.0.0.1"
    assert settings.wecom_webhook_port == 18101
    assert settings.wecom_webhook_path == "/hooks/wecom"


def test_load_settings_reads_feishu_long_connection_mode_without_encrypt_key() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "FEISHU_APP_ID": "cli_a",
            "FEISHU_APP_SECRET": "sec_b",
            "FEISHU_INBOUND_MODE": "long_connection",
        }
    )

    assert settings.feishu_inbound_mode == "long_connection"
    assert settings.feishu_app_id == "cli_a"
    assert settings.feishu_app_secret == "sec_b"
    assert settings.feishu_encrypt_key == ""


def test_load_settings_rejects_invalid_feishu_inbound_mode() -> None:
    with pytest.raises(ConfigError, match="FEISHU_INBOUND_MODE"):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token-value",
                "PROWLARR_BASE_URL": "http://prowlarr:9696/",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091/",
                "FEISHU_INBOUND_MODE": "sdk",
            }
        )


def test_load_settings_reads_raw_bt_destinations() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "RAW_BT_DESTINATIONS": "downloads|下载目录|/data/raw/downloads;archive|归档目录|/data/raw/archive",
        }
    )
    assert len(settings.raw_bt_destination_options) == 2
    assert settings.raw_bt_destination_options[0].key == "downloads"
    assert settings.raw_bt_destination_options[0].label == "下载目录"
    assert settings.raw_bt_destination_options[0].target_dir == "/data/raw/downloads"
    assert settings.raw_bt_destination_options[1].key == "archive"


def test_load_settings_reads_adult_archive_destinations() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "ADULT_ARCHIVE_DESTINATIONS": (
                "fc2|FC2|/data/adult/fc2;"
                "censored|有码|/data/adult/censored"
            ),
            "ADULT_BT_RETENTION_HOURS": "120",
        }
    )

    assert len(settings.adult_archive_destinations) == 2
    assert settings.adult_archive_destinations[0].category == "fc2"
    assert settings.adult_archive_destinations[0].label == "FC2"
    assert settings.adult_archive_destinations[0].target_dir == "/data/adult/fc2"
    assert settings.adult_bt_retention_hours == 120


def test_load_settings_reads_downloader_instances_and_role_binding() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "DOWNLOADER_INSTANCES": (
                "tr-main|transmission|http://transmission:9091|/data/downloads/tr|user1|pass1;"
                "qb-main|qb|http://qb:8080|/data/downloads/qb"
            ),
            "PT_DOWNLOADER": "tr-main",
            "BT_DOWNLOADER": "qb-main",
        }
    )

    assert len(settings.downloader_instances) == 2
    assert settings.downloader_instances[0].name == "tr-main"
    assert settings.downloader_instances[0].downloader_type == "transmission"
    assert settings.downloader_instances[0].download_dir == "/data/downloads/tr"
    assert settings.downloader_instances[0].dispatch_download_dir == ""
    assert settings.downloader_instances[1].name == "qb-main"
    assert settings.downloader_instances[1].downloader_type == "qbittorrent"
    assert settings.downloader_instances[1].dispatch_download_dir == ""
    assert settings.downloader_role_binding is not None
    assert settings.downloader_role_binding.pt_downloader == "tr-main"
    assert settings.downloader_role_binding.bt_downloader == "qb-main"


def test_load_settings_reads_downloader_dispatch_download_dir() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "DOWNLOADER_INSTANCES": (
                "tr-main|transmission|http://transmission:9091|/data/downloads/tr|/downloads/complete;"
                "qb-main|qb|http://qb:8080|/data/downloads/qb|/data/downloads/qb|user1|pass1"
            ),
        }
    )

    assert settings.downloader_instances[0].dispatch_download_dir == "/downloads/complete"
    assert settings.downloader_instances[0].username == ""
    assert settings.downloader_instances[0].password == ""
    assert settings.downloader_instances[1].dispatch_download_dir == "/data/downloads/qb"
    assert settings.downloader_instances[1].username == "user1"
    assert settings.downloader_instances[1].password == "pass1"


def test_load_settings_defaults_role_binding_to_first_instance() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "DOWNLOADER_INSTANCES": "tr-main|transmission|http://transmission:9091|/data/downloads/tr",
        }
    )

    assert settings.downloader_role_binding is not None
    assert settings.downloader_role_binding.pt_downloader == "tr-main"
    assert settings.downloader_role_binding.bt_downloader == "tr-main"


def test_load_settings_reads_pt_min_seed_hours() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "PT_MIN_SEED_HOURS": "24",
        }
    )

    assert settings.pt_min_seed_hours == 24


def test_load_settings_rejects_unknown_role_binding_instance() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token-value",
                "PROWLARR_BASE_URL": "http://prowlarr:9696/",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091/",
                "DOWNLOADER_INSTANCES": "tr-main|transmission|http://transmission:9091|/data/downloads/tr",
                "BT_DOWNLOADER": "missing-instance",
            }
        )


def test_load_settings_rejects_negative_pt_min_seed_hours() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token-value",
                "PROWLARR_BASE_URL": "http://prowlarr:9696/",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091/",
                "PT_MIN_SEED_HOURS": "-1",
            }
        )


def test_load_settings_rejects_invalid_subtitle_timeout() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token-value",
                "PROWLARR_BASE_URL": "http://prowlarr:9696/",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091/",
                "SUBTITLE_TRANSLATION_TIMEOUT_SECONDS": "abc",
            }
        )


def test_load_settings_requires_token() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091",
            }
        )


def test_load_settings_requires_prowlarr_fields() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TRANSMISSION_BASE_URL": "http://transmission:9091",
            }
        )
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
                "TRANSMISSION_BASE_URL": "http://transmission:9091",
            }
        )


def test_load_settings_requires_transmission_base_url() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
                "PROWLARR_API_KEY": "api-key",
            }
        )


def test_load_settings_requires_complete_feishu_credentials() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091",
                "FEISHU_APP_ID": "cli_a",
            }
        )
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091",
                "FEISHU_ENCRYPT_KEY": "encrypt-key-42",
            }
        )


def test_load_settings_rejects_invalid_feishu_webhook_port() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091",
                "FEISHU_WEBHOOK_PORT": "abc",
            }
        )


def test_load_settings_requires_complete_wecom_credentials() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091",
                "WECOM_TOKEN": "wecom-token-42",
            }
        )
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091",
                "WECOM_RECEIVE_ID": "wwcorp123",
            }
        )


def test_load_settings_rejects_invalid_wecom_webhook_port() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
                "PROWLARR_API_KEY": "api-key",
                "TRANSMISSION_BASE_URL": "http://transmission:9091",
                "WECOM_WEBHOOK_PORT": "abc",
            }
        )
