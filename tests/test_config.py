from __future__ import annotations

import pytest

from app.config import ConfigError, load_settings


def test_load_settings_reads_token() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
        }
    )
    assert settings.telegram_bot_token == "token-value"
    assert settings.prowlarr_base_url == "http://prowlarr:9696"
    assert settings.prowlarr_api_key == "api-key"


def test_load_settings_requires_token() -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
                "PROWLARR_API_KEY": "api-key",
            }
        )


def test_load_settings_requires_prowlarr_fields() -> None:
    with pytest.raises(ConfigError):
        load_settings({"TELEGRAM_BOT_TOKEN": "token"})
    with pytest.raises(ConfigError):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "PROWLARR_BASE_URL": "http://prowlarr:9696",
            }
        )
