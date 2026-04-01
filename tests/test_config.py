from __future__ import annotations

import pytest

from app.config import ConfigError, load_settings


def test_load_settings_reads_token() -> None:
    settings = load_settings({"TELEGRAM_BOT_TOKEN": "token-value"})
    assert settings.telegram_bot_token == "token-value"


def test_load_settings_requires_token() -> None:
    with pytest.raises(ConfigError):
        load_settings({})
