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
    assert settings.emby_base_url == ""
    assert settings.emby_api_key == ""
    assert settings.subtitle_translation_api_key == ""
    assert settings.subtitle_translation_base_url == "https://api.openai.com/v1"
    assert settings.subtitle_translation_model == "gpt-5.4"
    assert settings.subtitle_translation_timeout_seconds == 60.0
    assert settings.sqlite_db_path == "/data/luminarr.db"
    assert settings.feishu_app_id == ""
    assert settings.feishu_app_secret == ""
    assert settings.feishu_encrypt_key == ""
    assert settings.feishu_base_url == "https://open.feishu.cn"
    assert settings.feishu_webhook_host == "0.0.0.0"
    assert settings.feishu_webhook_port == 18095
    assert settings.feishu_webhook_path == "/feishu/webhook"


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
    assert settings.downloader_instances[1].name == "qb-main"
    assert settings.downloader_instances[1].downloader_type == "qbittorrent"
    assert settings.downloader_role_binding is not None
    assert settings.downloader_role_binding.pt_downloader == "tr-main"
    assert settings.downloader_role_binding.bt_downloader == "qb-main"


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
