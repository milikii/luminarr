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
    assert settings.transmission_base_url == "http://transmission:9091"
    assert settings.transmission_username == "tr-user"
    assert settings.transmission_password == "tr-pass"
    assert settings.library_target_dir == "/data/library/movies"
    assert settings.emby_base_url == ""
    assert settings.emby_api_key == ""


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
