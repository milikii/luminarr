from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram.error import NetworkError

from app.bot import telegram_bot as tg
from app.bot.channel_contact_runtime import CHANNEL_CONTACT_REGISTRY_KEY, ChannelContactRegistry
from app.bot.shared_private_chat_sender import build_shared_private_chat_send_text_func
from app.bot.feishu_long_connection import FEISHU_LONG_CONNECTION_SERVICE_KEY
from app.bot.sidecar_host_runtime import SIDECAR_HOST_SEND_TEXT_FUNC_KEY
from app.bot.telegram_sidecar_runtime import (
    BT_SUBSCRIPTION_SCHEDULER_TASK_KEY,
    DOWNLOADER_INSTANCES_KEY,
    DOWNLOADER_ROLE_BINDING_KEY,
    MANAGE_BT_SUBSCRIPTION_SERVICE_KEY,
    _start_bt_subscription_scheduler_if_configured,
)
from app.bot.wecom_adapter import (
    WECOM_ENCODING_AES_KEY_BOT_DATA_KEY,
    WECOM_RECEIVE_ID_BOT_DATA_KEY,
    WECOM_TOKEN_BOT_DATA_KEY,
)
from app.bot.wecom_webhook_server import WeComWebhookServerConfig
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding, load_settings
from app.db.job_repo import JobPersistenceError
from app.downloader_route_lookup import (
    DownloaderRouteLookupError,
    _get_torrent_import_source_with_routing,
    _get_torrent_status_with_routing,
    _resolve_downloader_task_route,
    _resolve_lookup_client_for_task,
)
from app.main import (
    _build_ai_cast_localization_service,
    _build_adult_read_only_lookup_func,
    _build_bt_source_providers,
    _build_refresh_media_server_func,
    _resolve_downloader_client_for_dispatch,
    _run_application_polling,
    main as run_main,
)


def test_run_application_polling_prints_colored_fix_hint_on_network_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = SimpleNamespace(run_polling=lambda **_: (_ for _ in ()).throw(NetworkError("dns fail")))

    with pytest.raises(NetworkError):
        _run_application_polling(app)

    captured = capsys.readouterr()
    assert "[Telegram 启动失败]" in captured.out
    assert "[处理建议]" in captured.out


def test_build_shared_private_chat_send_text_func_avoids_adapter_import_cycle() -> None:
    bot_data = {
        CHANNEL_CONTACT_REGISTRY_KEY: ChannelContactRegistry(),
    }
    sender = build_shared_private_chat_send_text_func(bot_data=bot_data)
    assert callable(sender)


def test_run_application_polling_uses_bootstrap_retries_for_transient_proxy_network() -> None:
    run_polling = Mock()
    app = SimpleNamespace(run_polling=run_polling)

    _run_application_polling(app)

    run_polling.assert_called_once_with(drop_pending_updates=True, timeout=20, bootstrap_retries=3)


def test_resolve_downloader_name_for_task_fails_closed_when_lookup_is_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: None,
    )
    assert _resolve_downloader_task_route(task_ref="87", chat_id=1001, job_repo=job_repo) is None
    captured = capsys.readouterr()
    assert "[下载器路由未命中]" in captured.out
    assert "[处理建议]" in captured.out


def test_resolve_downloader_name_for_task_logs_lookup_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: (_ for _ in ()).throw(JobPersistenceError("db down")),
    )

    assert _resolve_downloader_task_route(task_ref="87", chat_id=1001, job_repo=job_repo) is None

    captured = capsys.readouterr()
    assert "[下载器路由查询失败]" in captured.out
    assert "task_ref=87" in captured.out
    assert "db down" in captured.out
    assert "[处理建议]" in captured.out


def test_resolve_downloader_name_for_task_propagates_unexpected_error() -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: (_ for _ in ()).throw(RuntimeError("programming error")),
    )

    with pytest.raises(RuntimeError, match="programming error"):
        _resolve_downloader_task_route(task_ref="87", chat_id=1001, job_repo=job_repo)


@pytest.mark.parametrize(
    ("payload_json", "expected_reason"),
    [
        ("", "payload_json empty"),
        ("{", "payload_json invalid json"),
        ("[]", "payload_json not object"),
    ],
)
def test_resolve_downloader_name_for_task_logs_payload_corruption(
    payload_json: str,
    expected_reason: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: SimpleNamespace(payload_json=payload_json),
    )

    assert _resolve_downloader_task_route(task_ref="87", chat_id=1001, job_repo=job_repo) is None

    captured = capsys.readouterr()
    assert "[下载器路由载荷损坏]" in captured.out
    assert expected_reason in captured.out
    assert "[处理建议]" in captured.out


def test_resolve_downloader_client_for_lookup_raises_for_unknown_instance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: SimpleNamespace(payload_json='{"downloader_name":"missing"}'),
    )

    with pytest.raises(DownloaderRouteLookupError, match="downloader client unavailable for import task: 87"):
        asyncio.run(
            _resolve_lookup_client_for_task(
                task_ref="87",
                chat_id=1001,
                job_repo=job_repo,
                downloader_instances_by_name={},
                transmission_clients_by_name={},
                qbittorrent_clients_by_name={},
                operation="import",
            )
        )

    captured = capsys.readouterr()
    assert "[下载器实例不存在]" in captured.out
    assert "[处理建议]" in captured.out


def test_resolve_downloader_client_for_lookup_logs_missing_client(capsys: pytest.CaptureFixture[str]) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: SimpleNamespace(payload_json='{"downloader_name":"pt-main"}'),
    )

    with pytest.raises(DownloaderRouteLookupError, match="downloader client unavailable for import task: 87"):
        asyncio.run(
            _resolve_lookup_client_for_task(
                task_ref="87",
                chat_id=1001,
                job_repo=job_repo,
                downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
                transmission_clients_by_name={},
                qbittorrent_clients_by_name={},
                operation="import",
            )
        )

    captured = capsys.readouterr()
    assert "[下载器客户端未配置]" in captured.out
    assert "downloader_name=pt-main" in captured.out
    assert "downloader_type=transmission" in captured.out
    assert "[处理建议]" in captured.out


def test_resolve_downloader_client_for_lookup_returns_route_instance_and_client() -> None:
    client = object()
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: SimpleNamespace(
            payload_json='{"downloader_name":"pt-main","download_dir":"/data/downloads/tr"}',
        ),
    )

    route, instance, resolved_client = _resolve_lookup_client_for_task(
        task_ref="87",
        chat_id=1001,
        job_repo=job_repo,
        downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
        transmission_clients_by_name={"pt-main": client},
        qbittorrent_clients_by_name={},
        operation="import",
    )

    assert route == ("pt-main", "/data/downloads/tr", "87")
    assert instance is not None
    assert instance.downloader_type == "transmission"
    assert resolved_client is client


def test_get_torrent_import_source_with_routing_raises_when_route_lookup_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: (_ for _ in ()).throw(JobPersistenceError("db down")),
    )

    with pytest.raises(DownloaderRouteLookupError, match="downloader route unavailable for import task: 87"):
        asyncio.run(
            _get_torrent_import_source_with_routing(
                task_ref="87",
                chat_id=1001,
                job_repo=job_repo,
                downloader_instances_by_name={},
                transmission_clients_by_name={},
                qbittorrent_clients_by_name={},
            )
        )

    captured = capsys.readouterr()
    assert "[下载器路由查询失败]" in captured.out
    assert "task_ref=87" in captured.out
    assert "db down" in captured.out


def test_get_torrent_import_source_with_routing_raises_when_client_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: SimpleNamespace(payload_json='{"downloader_name":"pt-main"}'),
    )

    with pytest.raises(DownloaderRouteLookupError, match="downloader client unavailable for import task: 87"):
        asyncio.run(
            _get_torrent_import_source_with_routing(
                task_ref="87",
                chat_id=1001,
                job_repo=job_repo,
                downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
                transmission_clients_by_name={},
                qbittorrent_clients_by_name={},
            )
        )

    captured = capsys.readouterr()
    assert "[下载器客户端未配置]" in captured.out
    assert "downloader_name=pt-main" in captured.out


def test_get_torrent_import_source_with_routing_returns_none_for_real_not_found() -> None:
    client = SimpleNamespace(get_torrent_import_source=lambda task_ref: _return_async(None))
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: SimpleNamespace(payload_json='{"downloader_name":"pt-main"}'),
    )

    result = asyncio.run(
        _get_torrent_import_source_with_routing(
            task_ref="87",
            chat_id=1001,
            job_repo=job_repo,
            downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
            transmission_clients_by_name={"pt-main": client},
            qbittorrent_clients_by_name={},
        )
    )

    assert result is None


def test_get_torrent_status_with_routing_raises_when_route_lookup_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    with pytest.raises(DownloaderRouteLookupError, match="downloader route unavailable for status task: 87"):
        asyncio.run(
            _get_torrent_status_with_routing(
                task_ref="87",
                chat_id=1001,
                job_repo=job_repo,
                downloader_instances_by_name={},
                transmission_clients_by_name={},
                qbittorrent_clients_by_name={},
            )
        )

    captured = capsys.readouterr()
    assert "[下载器路由查询失败]" in captured.out
    assert "task_ref=87" in captured.out
    assert "db down" in captured.out


def test_get_torrent_status_with_routing_raises_when_client_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: SimpleNamespace(payload_json='{"downloader_name":"pt-main"}'),
    )

    with pytest.raises(DownloaderRouteLookupError, match="downloader client unavailable for status task: 87"):
        asyncio.run(
            _get_torrent_status_with_routing(
                task_ref="87",
                chat_id=1001,
                job_repo=job_repo,
                downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
                transmission_clients_by_name={},
                qbittorrent_clients_by_name={},
            )
        )

    captured = capsys.readouterr()
    assert "[下载器客户端未配置]" in captured.out
    assert "downloader_name=pt-main" in captured.out


def test_get_torrent_status_with_routing_returns_none_for_real_not_found() -> None:
    client = SimpleNamespace(get_torrent_status=lambda task_ref: _return_async(None))
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: SimpleNamespace(payload_json='{"downloader_name":"pt-main"}'),
    )

    result = asyncio.run(
        _get_torrent_status_with_routing(
            task_ref="87",
            chat_id=1001,
            job_repo=job_repo,
            downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
            transmission_clients_by_name={"pt-main": client},
            qbittorrent_clients_by_name={},
        )
    )

    assert result is None


def test_get_torrent_status_with_routing_accepts_real_downloader_task_id_lookup() -> None:
    captured_task_refs: list[str] = []

    async def _get_status(task_ref: str):
        captured_task_refs.append(task_ref)
        return "status-result"

    client = SimpleNamespace(get_torrent_status=_get_status)
    seen_queries: list[str] = []

    def _get_job_for_chat_ref(**kwargs):
        seen_queries.append(kwargs["task_ref"])
        assert kwargs["task_ref"] == "42"
        return SimpleNamespace(
            payload_json='{"downloader_name":"pt-main"}',
            task_id="42",
            task_hash="hash-42",
        )

    job_repo = SimpleNamespace(get_downloader_job_for_chat_ref=_get_job_for_chat_ref)

    result = asyncio.run(
        _get_torrent_status_with_routing(
            task_ref="42",
            chat_id=1001,
            job_repo=job_repo,
            downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
            transmission_clients_by_name={"pt-main": client},
            qbittorrent_clients_by_name={},
        )
    )

    assert seen_queries == ["42"]
    assert captured_task_refs == ["hash-42"]
    assert result == "status-result"


def test_resolve_downloader_client_for_dispatch_rejects_unknown_explicit_instance() -> None:
    default_client = object()
    assert _resolve_downloader_client_for_dispatch(
        downloader_name="",
        transmission_client=default_client,
        downloader_instances_by_name={},
        transmission_clients_by_name={},
        qbittorrent_clients_by_name={},
    ) is default_client
    with pytest.raises(ValueError):
        _resolve_downloader_client_for_dispatch(
            downloader_name="missing",
            transmission_client=default_client,
            downloader_instances_by_name={},
            transmission_clients_by_name={},
            qbittorrent_clients_by_name={},
        )


def test_resolve_downloader_client_for_dispatch_rejects_implicit_fallback_without_legacy_client(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ValueError, match="legacy transmission client not configured for implicit fallback"):
        _resolve_downloader_client_for_dispatch(
            downloader_name="",
            transmission_client=None,
            downloader_instances_by_name={},
            transmission_clients_by_name={},
            qbittorrent_clients_by_name={},
        )

    captured = capsys.readouterr()
    assert "[下载器投递路由失败]" in captured.out
    assert "原因=legacy fallback unavailable" in captured.out
    assert "[处理建议]" in captured.out


def test_resolve_downloader_client_for_dispatch_logs_unknown_explicit_instance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ValueError, match="unknown downloader instance: missing"):
        _resolve_downloader_client_for_dispatch(
            downloader_name="missing",
            transmission_client=object(),
            downloader_instances_by_name={},
            transmission_clients_by_name={},
            qbittorrent_clients_by_name={},
        )

    captured = capsys.readouterr()
    assert "[下载器投递路由失败]" in captured.out
    assert "downloader_name=missing" in captured.out
    assert "原因=instance missing" in captured.out
    assert "[处理建议]" in captured.out


def test_resolve_downloader_client_for_dispatch_logs_missing_client(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ValueError, match="downloader client not configured: pt-main"):
        _resolve_downloader_client_for_dispatch(
            downloader_name="pt-main",
            transmission_client=object(),
            downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
            transmission_clients_by_name={},
            qbittorrent_clients_by_name={},
        )

    captured = capsys.readouterr()
    assert "[下载器投递路由失败]" in captured.out
    assert "downloader_name=pt-main" in captured.out
    assert "downloader_type=transmission" in captured.out
    assert "原因=client not configured" in captured.out
    assert "[处理建议]" in captured.out


def test_build_refresh_media_server_func_logs_missing_emby_settings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = SimpleNamespace(
        media_server_provider="emby",
        emby_base_url="",
        emby_api_key="",
        jellyfin_base_url="",
        jellyfin_api_key="",
        plex_base_url="",
        plex_token="",
    )

    assert _build_refresh_media_server_func(settings) is None

    captured = capsys.readouterr()
    assert "[媒体服务器配置缺失]" in captured.out
    assert "provider=emby" in captured.out
    assert "EMBY_BASE_URL" in captured.out
    assert "EMBY_API_KEY" in captured.out
    assert "[处理建议]" in captured.out


def test_build_refresh_media_server_func_logs_missing_jellyfin_settings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = SimpleNamespace(
        media_server_provider="jellyfin",
        emby_base_url="",
        emby_api_key="",
        jellyfin_base_url="http://jellyfin:8096",
        jellyfin_api_key="",
        plex_base_url="",
        plex_token="",
    )

    assert _build_refresh_media_server_func(settings) is None

    captured = capsys.readouterr()
    assert "[媒体服务器配置缺失]" in captured.out
    assert "provider=jellyfin" in captured.out
    assert "JELLYFIN_API_KEY" in captured.out
    assert "[处理建议]" in captured.out


def test_build_refresh_media_server_func_logs_missing_plex_settings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = SimpleNamespace(
        media_server_provider="plex",
        emby_base_url="",
        emby_api_key="",
        jellyfin_base_url="",
        jellyfin_api_key="",
        plex_base_url="",
        plex_token="plex-token",
    )

    assert _build_refresh_media_server_func(settings) is None

    captured = capsys.readouterr()
    assert "[媒体服务器配置缺失]" in captured.out
    assert "provider=plex" in captured.out
    assert "PLEX_BASE_URL" in captured.out
    assert "[处理建议]" in captured.out


def test_build_refresh_media_server_func_wraps_emby_client(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    class FakeEmbyClient:
        def __init__(self, *, base_url: str, api_key: str) -> None:
            calls["base_url"] = base_url
            calls["api_key"] = api_key
            calls["refresh_library"] = self.refresh_library

        async def refresh_library(self) -> None:
            return None

    class FakeRefreshService:
        def __init__(self, refresh_func, *, provider_name: str, target_url: str) -> None:
            calls["refresh_func"] = refresh_func
            calls["provider_name"] = provider_name
            calls["target_url"] = target_url
            self.refresh_text = object()

    monkeypatch.setattr("app.main.EmbyClient", FakeEmbyClient)
    monkeypatch.setattr("app.main.RefreshMediaServerService", FakeRefreshService)

    settings = SimpleNamespace(
        media_server_provider="emby",
        emby_base_url="http://emby:8096",
        emby_api_key="emby-key",
        jellyfin_base_url="",
        jellyfin_api_key="",
        plex_base_url="",
        plex_token="",
    )

    refresh_func = _build_refresh_media_server_func(settings)

    assert calls["base_url"] == "http://emby:8096"
    assert calls["api_key"] == "emby-key"
    assert calls["provider_name"] == "emby"
    assert calls["target_url"] == "http://emby:8096"
    assert getattr(calls["refresh_func"], "__self__", None).__class__ is FakeEmbyClient
    assert getattr(calls["refresh_func"], "__name__", "") == "refresh_library"
    assert refresh_func is not None


def test_build_refresh_media_server_func_wraps_jellyfin_client(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    class FakeJellyfinClient:
        def __init__(self, *, base_url: str, api_key: str) -> None:
            calls["base_url"] = base_url
            calls["api_key"] = api_key
            calls["refresh_library"] = self.refresh_library

        async def refresh_library(self) -> None:
            return None

    class FakeRefreshService:
        def __init__(self, refresh_func, *, provider_name: str, target_url: str) -> None:
            calls["refresh_func"] = refresh_func
            calls["provider_name"] = provider_name
            calls["target_url"] = target_url
            self.refresh_text = object()

    monkeypatch.setattr("app.main.JellyfinClient", FakeJellyfinClient)
    monkeypatch.setattr("app.main.RefreshMediaServerService", FakeRefreshService)

    settings = SimpleNamespace(
        media_server_provider="jellyfin",
        emby_base_url="",
        emby_api_key="",
        jellyfin_base_url="http://jellyfin:8096",
        jellyfin_api_key="jelly-key",
        plex_base_url="",
        plex_token="",
    )

    refresh_func = _build_refresh_media_server_func(settings)

    assert calls["base_url"] == "http://jellyfin:8096"
    assert calls["api_key"] == "jelly-key"
    assert calls["provider_name"] == "jellyfin"
    assert calls["target_url"] == "http://jellyfin:8096"
    assert getattr(calls["refresh_func"], "__self__", None).__class__ is FakeJellyfinClient
    assert getattr(calls["refresh_func"], "__name__", "") == "refresh_library"
    assert refresh_func is not None


def test_build_refresh_media_server_func_wraps_plex_client(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    class FakePlexClient:
        def __init__(self, *, base_url: str, token: str) -> None:
            calls["base_url"] = base_url
            calls["token"] = token
            calls["refresh_library"] = self.refresh_library

        async def refresh_library(self) -> None:
            return None

    class FakeRefreshService:
        def __init__(self, refresh_func, *, provider_name: str, target_url: str) -> None:
            calls["refresh_func"] = refresh_func
            calls["provider_name"] = provider_name
            calls["target_url"] = target_url
            self.refresh_text = object()

    monkeypatch.setattr("app.main.PlexClient", FakePlexClient)
    monkeypatch.setattr("app.main.RefreshMediaServerService", FakeRefreshService)

    settings = SimpleNamespace(
        media_server_provider="plex",
        emby_base_url="",
        emby_api_key="",
        jellyfin_base_url="",
        jellyfin_api_key="",
        plex_base_url="http://plex:32400",
        plex_token="plex-token",
    )

    refresh_func = _build_refresh_media_server_func(settings)

    assert calls["base_url"] == "http://plex:32400"
    assert calls["token"] == "plex-token"
    assert calls["provider_name"] == "plex"
    assert calls["target_url"] == "http://plex:32400"
    assert getattr(calls["refresh_func"], "__self__", None).__class__ is FakePlexClient
    assert getattr(calls["refresh_func"], "__name__", "") == "refresh_library"
    assert refresh_func is not None


def test_build_bt_source_providers_skips_helper_only_web_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_rules: list[str] = []

    class FakeWebSourceClient:
        def __init__(self, *, rule, proxy_url: str) -> None:
            created_rules.append(rule.name)
            self.search = AsyncMock(return_value=[])
            self.search_page = AsyncMock(return_value=[])

    monkeypatch.setattr("app.main.WebSourceClient", FakeWebSourceClient)

    providers = _build_bt_source_providers(
        configured_web_source_names=("nyaa", "tokyotosho", "javlibrary", "javbus"),
        proxy_url="http://proxy.local:7890",
    )

    assert [provider.name for provider in providers] == ["nyaa", "tokyotosho", "javbus"]
    assert created_rules == ["nyaa", "tokyotosho", "javbus"]


def test_build_bt_source_providers_uses_curated_adult_defaults_when_config_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_rules: list[str] = []

    class FakeWebSourceClient:
        def __init__(self, *, rule, proxy_url: str) -> None:
            created_rules.append(rule.name)
            self.search = AsyncMock(return_value=[])
            self.search_page = AsyncMock(return_value=[])

    monkeypatch.setattr("app.main.WebSourceClient", FakeWebSourceClient)

    providers = _build_bt_source_providers(
        configured_web_source_names=(),
        proxy_url="http://proxy.local:7890",
    )

    assert [provider.name for provider in providers] == ["tokyotosho", "sukebei", "javbus"]
    assert created_rules == ["tokyotosho", "sukebei", "javbus"]


def test_build_bt_source_providers_skips_supported_but_unmodeled_web_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.clients import web_source as web_source_module

    created_rules: list[str] = []

    class FakeWebSourceClient:
        def __init__(self, *, rule, proxy_url: str) -> None:
            created_rules.append(rule.name)
            self.search = AsyncMock(return_value=[])
            self.search_page = AsyncMock(return_value=[])

    unmodeled_rule = web_source_module.WebSourceRule(
        name="unmodeled-source",
        base_url="https://example.com",
        search_path_template="/search?q={query}",
    )
    patched_rules = dict(web_source_module.SUPPORTED_WEB_SOURCE_RULES)
    patched_rules["unmodeled-source"] = unmodeled_rule

    monkeypatch.setattr(web_source_module, "SUPPORTED_WEB_SOURCE_RULES", patched_rules)
    monkeypatch.setattr("app.main.WebSourceClient", FakeWebSourceClient)

    providers = _build_bt_source_providers(
        configured_web_source_names=("tokyotosho", "unmodeled-source", "javbus"),
        proxy_url="http://proxy.local:7890",
    )

    assert [provider.name for provider in providers] == ["tokyotosho", "javbus"]
    assert created_rules == ["tokyotosho", "javbus"]


def test_build_adult_read_only_lookup_func_wires_avmoo_before_javlibrary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakeAvmooReadOnlyHelperClient:
        def __init__(self, *, proxy_url: str) -> None:
            calls.append(f"avmoo:init:{proxy_url}")

        async def lookup(self, lookup_text: str):
            calls.append(f"avmoo:lookup:{lookup_text}")
            return None

    class FakeAvsoxReadOnlyHelperClient:
        def __init__(self, *, proxy_url: str) -> None:
            calls.append(f"avsox:init:{proxy_url}")

        async def lookup(self, lookup_text: str):
            calls.append(f"avsox:lookup:{lookup_text}")
            return None

    class FakeJavBusReadOnlyHelperClient:
        def __init__(self, *, proxy_url: str) -> None:
            calls.append(f"javbus:init:{proxy_url}")

        async def lookup(self, lookup_text: str):
            calls.append(f"javbus:lookup:{lookup_text}")
            return SimpleNamespace(source_site="javbus")

    class FakeCaribbeancomReadOnlyHelperClient:
        def __init__(self, *, proxy_url: str) -> None:
            calls.append(f"caribbeancom:init:{proxy_url}")

        async def lookup(self, lookup_text: str):
            calls.append(f"caribbeancom:lookup:{lookup_text}")
            return None

    class FakeJavLibraryReadOnlyHelperClient:
        def __init__(self, *, proxy_url: str) -> None:
            calls.append(f"javlibrary:init:{proxy_url}")

        async def lookup(self, lookup_text: str):
            calls.append(f"javlibrary:lookup:{lookup_text}")
            return SimpleNamespace(source_site="javlibrary")

    monkeypatch.setattr("app.main.AvmooReadOnlyHelperClient", FakeAvmooReadOnlyHelperClient)
    monkeypatch.setattr("app.main.AvsoxReadOnlyHelperClient", FakeAvsoxReadOnlyHelperClient)
    monkeypatch.setattr("app.main.JavBusReadOnlyHelperClient", FakeJavBusReadOnlyHelperClient)
    monkeypatch.setattr("app.main.CaribbeancomReadOnlyHelperClient", FakeCaribbeancomReadOnlyHelperClient)
    monkeypatch.setattr("app.main.JavLibraryReadOnlyHelperClient", FakeJavLibraryReadOnlyHelperClient)

    lookup = _build_adult_read_only_lookup_func(proxy_url="http://proxy.local:7890")
    match = asyncio.run(lookup("SSIS-123"))

    assert match.source_site == "javbus"
    assert calls == [
        "avmoo:init:http://proxy.local:7890",
        "avsox:init:http://proxy.local:7890",
        "javbus:init:http://proxy.local:7890",
        "caribbeancom:init:http://proxy.local:7890",
        "javlibrary:init:http://proxy.local:7890",
        "caribbeancom:lookup:SSIS-123",
        "avmoo:lookup:SSIS-123",
        "avsox:lookup:SSIS-123",
        "javbus:lookup:SSIS-123",
    ]


class _MainSettings(SimpleNamespace):
    def has_prowlarr_search(self) -> bool:
        return bool(self.prowlarr_base_url and self.prowlarr_api_key)

    def has_legacy_transmission_downloader(self) -> bool:
        return bool(self.transmission_base_url)

    def has_any_downloader_dispatch(self) -> bool:
        return self.has_legacy_transmission_downloader() or bool(self.downloader_instances)

    def has_telegram_host(self) -> bool:
        return bool(self.telegram_bot_token)

    def has_feishu_host(self) -> bool:
        return bool(self.feishu_app_id and self.feishu_app_secret)

    def has_wecom_host(self) -> bool:
        return bool(self.wecom_token and self.wecom_encoding_aes_key and self.wecom_receive_id)


def _build_main_settings(**overrides: object) -> _MainSettings:
    defaults: dict[str, object] = {
        "telegram_bot_token": "telegram-token",
        "outbound_proxy_url": "",
        "prowlarr_base_url": "",
        "prowlarr_api_key": "",
        "tmdb_base_url": "https://api.themoviedb.org",
        "tmdb_api_key": "",
        "fanart_base_url": "https://webservice.fanart.tv/v3",
        "fanart_api_key": "",
        "douban_cast_enrichment_base_url": "",
        "transmission_base_url": "",
        "transmission_username": "",
        "transmission_password": "",
        "library_target_dir": "/data/library/movies",
        "media_server_provider": "emby",
        "emby_base_url": "",
        "emby_api_key": "",
        "jellyfin_base_url": "",
        "jellyfin_api_key": "",
        "plex_base_url": "",
        "plex_token": "",
        "subtitle_translation_api_key": "",
        "subtitle_translation_base_url": "https://api.openai.com/v1",
        "subtitle_translation_model": "gpt-5.4",
        "subtitle_translation_timeout_seconds": 60.0,
        "pt_min_seed_hours": 0,
        "sqlite_db_path": "/tmp/luminarr.db",
        "raw_bt_destination_options": (),
        "adult_archive_destinations": (),
        "adult_bt_retention_hours": 96,
        "bt_web_sources": (),
        "downloader_instances": (),
        "downloader_role_binding": None,
        "feishu_app_id": "",
        "feishu_app_secret": "",
        "feishu_base_url": "https://open.feishu.cn",
        "wecom_token": "",
        "wecom_encoding_aes_key": "",
        "wecom_receive_id": "",
        "wecom_webhook_host": "0.0.0.0",
        "wecom_webhook_port": 18097,
        "wecom_webhook_path": "/wecom/webhook",
    }
    defaults.update(overrides)
    return _MainSettings(**defaults)


def test_load_settings_reads_douban_cast_enrichment_base_url() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token-value",
            "PROWLARR_BASE_URL": "http://prowlarr:9696/",
            "PROWLARR_API_KEY": "api-key",
            "TRANSMISSION_BASE_URL": "http://transmission:9091/",
            "DOUBAN_CAST_ENRICHMENT_BASE_URL": " https://movie.douban.test/ ",
        }
    )

    assert settings.douban_cast_enrichment_base_url == "https://movie.douban.test"


def test_build_ai_cast_localization_service_returns_none_when_subtitle_translation_is_disabled() -> None:
    settings = _build_main_settings(subtitle_translation_api_key="")

    assert _build_ai_cast_localization_service(settings) is None


def test_build_ai_cast_localization_service_reuses_subtitle_translation_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_main_settings(
        subtitle_translation_api_key="cast-localize-key",
        subtitle_translation_base_url="https://openai.example/v1",
        subtitle_translation_model="gpt-5.4-mini",
        subtitle_translation_timeout_seconds=45.0,
        outbound_proxy_url="http://proxy.local:7890",
    )
    created: dict[str, object] = {}

    class FakeAICastLocalizationService:
        def __init__(self, **kwargs: object) -> None:
            created["kwargs"] = kwargs

        async def localize(self, *_args: object, **_kwargs: object):
            return ()

    monkeypatch.setattr("app.main.AICastLocalizationService", FakeAICastLocalizationService)

    service = _build_ai_cast_localization_service(settings)

    assert service is not None
    assert created["kwargs"] == {
        "api_key": "cast-localize-key",
        "base_url": "https://openai.example/v1",
        "model": "gpt-5.4-mini",
        "timeout_seconds": 45.0,
        "proxy_url": "http://proxy.local:7890",
    }


def test_main_keeps_tmdb_only_metadata_scraper_when_ai_cast_localization_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_main_settings(
        tmdb_api_key="tmdb-key",
        subtitle_translation_api_key="",
    )
    created: dict[str, object] = {}

    async def _empty_search(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return []

    def _simple_component(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace()

    class _FakeTmdbClient:
        def __init__(self, **kwargs: object) -> None:
            created["tmdb_client_kwargs"] = kwargs

        async def search_movie(self, *_args: object, **_kwargs: object):
            return None

        async def search_media_candidates(self, *_args: object, **_kwargs: object):
            return []

        async def search_movie_candidates(self, *_args: object, **_kwargs: object):
            return []

        async def search_tv_candidates(self, *_args: object, **_kwargs: object):
            return []

        async def get_movie_by_id(self, *_args: object, **_kwargs: object):
            return None

        async def get_tv_by_id(self, *_args: object, **_kwargs: object):
            return None

        async def get_movie_credits(self, *_args: object, **_kwargs: object):
            return ()

        async def get_tv_credits(self, *_args: object, **_kwargs: object):
            return ()

    class _FakeMetadataScraperService:
        def __init__(self, **kwargs: object) -> None:
            created["metadata_scraper_kwargs"] = kwargs
            self.scrape_for_import = AsyncMock()

    def _fake_build_application(
        token: str,
        search_service,
        add_to_downloader_service,
        get_download_status_service,
        import_to_library_service,
        cleanup_downloaded_source_service,
        manage_watchlist_service,
        manage_bt_subscription_service,
        **kwargs: object,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            bot_data={
                tg.SEARCH_SERVICE_KEY: search_service,
                tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: manage_bt_subscription_service,
                CHANNEL_CONTACT_REGISTRY_KEY: kwargs["channel_contact_registry"],
            }
        )

    monkeypatch.setattr("app.main.load_settings", lambda: settings)
    monkeypatch.setattr("app.main.configure_trace_log_file", lambda **_kwargs: None)
    monkeypatch.setattr("app.main.SqliteDatabase", _FakeDatabase)
    monkeypatch.setattr("app.main.CandidateMappingRepo", _simple_component)
    monkeypatch.setattr("app.main.JobEventRepo", _simple_component)
    monkeypatch.setattr("app.main.JobRepo", _simple_component)
    monkeypatch.setattr("app.main.ApprovalRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultContentRegistryRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultDuplicateMemorySnapshotRepo", _simple_component)
    monkeypatch.setattr("app.main.BtPendingRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSubscriptionRepo", _simple_component)
    monkeypatch.setattr("app.main.DownloadMonitorRepo", _simple_component)
    monkeypatch.setattr("app.main.TelegramUpdateRepo", _simple_component)
    monkeypatch.setattr("app.main.WatchlistRepo", _simple_component)
    monkeypatch.setattr("app.main.ClarificationRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSourceProvider", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(
        "app.main.BtSourceAdapter",
        lambda *_args, **_kwargs: SimpleNamespace(search=_empty_search, search_page=_empty_search),
    )
    monkeypatch.setattr("app.main._build_adult_read_only_lookup_func", lambda *, proxy_url: None)
    monkeypatch.setattr("app.main.SearchMediaService", _simple_component)
    monkeypatch.setattr("app.main.TmdbClient", _FakeTmdbClient)
    monkeypatch.setattr("app.main.MetadataScraperService", _FakeMetadataScraperService)
    monkeypatch.setattr(
        "app.main.AICastLocalizationService",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("AI cast localization should stay disabled")),
    )
    monkeypatch.setattr("app.main.AdultMetadataTranslatorService", lambda **_kwargs: SimpleNamespace(translate_candidates=None))
    monkeypatch.setattr("app.main.AdultDuplicateMemoryService", _simple_component)
    monkeypatch.setattr("app.main.AddToDownloaderService", _simple_component)
    monkeypatch.setattr("app.main.ImportToLibraryService", _simple_component)
    monkeypatch.setattr("app.main.PostDownloadAutoImportService", _simple_component)
    monkeypatch.setattr("app.main.GetDownloadStatusService", _simple_component)
    monkeypatch.setattr("app.main.CleanupDownloadedSourceService", _simple_component)
    monkeypatch.setattr("app.main.ManageWatchlistService", _simple_component)
    monkeypatch.setattr("app.main.ManageBtSubscriptionService", _simple_component)
    monkeypatch.setattr("app.main.AdultArchiveService", _simple_component)
    monkeypatch.setattr("app.main.SubtitleTranslatorService", lambda **_kwargs: SimpleNamespace(translate_for_import=None))
    monkeypatch.setattr("app.main.PersonalWeChatLoginService", _simple_component)
    monkeypatch.setattr("app.main.PersonalWeChatTextService", _simple_component)
    monkeypatch.setattr("app.main._build_refresh_media_server_func", lambda _settings: None)
    monkeypatch.setattr("app.main.build_application", _fake_build_application)
    monkeypatch.setattr("app.main._run_application_polling", lambda _application: None)

    run_main()

    assert created["metadata_scraper_kwargs"]["cast_localization_service"] is None


def test_main_injects_ai_cast_localization_into_metadata_scraper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_main_settings(
        tmdb_api_key="tmdb-key",
        subtitle_translation_api_key="cast-localize-key",
        subtitle_translation_base_url="https://openai.example/v1",
        subtitle_translation_model="gpt-5.4-mini",
        subtitle_translation_timeout_seconds=45.0,
        outbound_proxy_url="http://proxy.local:7890",
    )
    created: dict[str, object] = {}

    async def _empty_search(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return []

    def _simple_component(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace()

    class _FakeTmdbClient:
        def __init__(self, **kwargs: object) -> None:
            created["tmdb_client_kwargs"] = kwargs

        async def search_movie(self, *_args: object, **_kwargs: object):
            return None

        async def search_media_candidates(self, *_args: object, **_kwargs: object):
            return []

        async def search_movie_candidates(self, *_args: object, **_kwargs: object):
            return []

        async def search_tv_candidates(self, *_args: object, **_kwargs: object):
            return []

        async def get_movie_by_id(self, *_args: object, **_kwargs: object):
            return None

        async def get_tv_by_id(self, *_args: object, **_kwargs: object):
            return None

        async def get_movie_credits(self, *_args: object, **_kwargs: object):
            return ()

        async def get_tv_credits(self, *_args: object, **_kwargs: object):
            return ()

    class _FakeMetadataScraperService:
        def __init__(self, **kwargs: object) -> None:
            created["metadata_scraper_kwargs"] = kwargs
            self.scrape_for_import = AsyncMock()

    class _FakeAICastLocalizationService:
        def __init__(self, **kwargs: object) -> None:
            created["cast_localization_kwargs"] = kwargs

        async def localize(self, *_args: object, **_kwargs: object):
            return ()

    def _fake_build_application(
        token: str,
        search_service,
        add_to_downloader_service,
        get_download_status_service,
        import_to_library_service,
        cleanup_downloaded_source_service,
        manage_watchlist_service,
        manage_bt_subscription_service,
        **kwargs: object,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            bot_data={
                tg.SEARCH_SERVICE_KEY: search_service,
                tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: manage_bt_subscription_service,
                CHANNEL_CONTACT_REGISTRY_KEY: kwargs["channel_contact_registry"],
            }
        )

    monkeypatch.setattr("app.main.load_settings", lambda: settings)
    monkeypatch.setattr("app.main.configure_trace_log_file", lambda **_kwargs: None)
    monkeypatch.setattr("app.main.SqliteDatabase", _FakeDatabase)
    monkeypatch.setattr("app.main.CandidateMappingRepo", _simple_component)
    monkeypatch.setattr("app.main.JobEventRepo", _simple_component)
    monkeypatch.setattr("app.main.JobRepo", _simple_component)
    monkeypatch.setattr("app.main.ApprovalRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultContentRegistryRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultDuplicateMemorySnapshotRepo", _simple_component)
    monkeypatch.setattr("app.main.BtPendingRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSubscriptionRepo", _simple_component)
    monkeypatch.setattr("app.main.DownloadMonitorRepo", _simple_component)
    monkeypatch.setattr("app.main.TelegramUpdateRepo", _simple_component)
    monkeypatch.setattr("app.main.WatchlistRepo", _simple_component)
    monkeypatch.setattr("app.main.ClarificationRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSourceProvider", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(
        "app.main.BtSourceAdapter",
        lambda *_args, **_kwargs: SimpleNamespace(search=_empty_search, search_page=_empty_search),
    )
    monkeypatch.setattr("app.main._build_adult_read_only_lookup_func", lambda *, proxy_url: None)
    monkeypatch.setattr("app.main.SearchMediaService", _simple_component)
    monkeypatch.setattr("app.main.TmdbClient", _FakeTmdbClient)
    monkeypatch.setattr("app.main.MetadataScraperService", _FakeMetadataScraperService)
    monkeypatch.setattr("app.main.AICastLocalizationService", _FakeAICastLocalizationService)
    monkeypatch.setattr("app.main.AdultMetadataTranslatorService", lambda **_kwargs: SimpleNamespace(translate_candidates=None))
    monkeypatch.setattr("app.main.AdultDuplicateMemoryService", _simple_component)
    monkeypatch.setattr("app.main.AddToDownloaderService", _simple_component)
    monkeypatch.setattr("app.main.ImportToLibraryService", _simple_component)
    monkeypatch.setattr("app.main.PostDownloadAutoImportService", _simple_component)
    monkeypatch.setattr("app.main.GetDownloadStatusService", _simple_component)
    monkeypatch.setattr("app.main.CleanupDownloadedSourceService", _simple_component)
    monkeypatch.setattr("app.main.ManageWatchlistService", _simple_component)
    monkeypatch.setattr("app.main.ManageBtSubscriptionService", _simple_component)
    monkeypatch.setattr("app.main.AdultArchiveService", _simple_component)
    monkeypatch.setattr("app.main.SubtitleTranslatorService", lambda **_kwargs: SimpleNamespace(translate_for_import=None))
    monkeypatch.setattr("app.main.PersonalWeChatLoginService", _simple_component)
    monkeypatch.setattr("app.main.PersonalWeChatTextService", _simple_component)
    monkeypatch.setattr("app.main._build_refresh_media_server_func", lambda _settings: None)
    monkeypatch.setattr("app.main.build_application", _fake_build_application)
    monkeypatch.setattr("app.main._run_application_polling", lambda _application: None)

    run_main()

    assert created["cast_localization_kwargs"] == {
        "api_key": "cast-localize-key",
        "base_url": "https://openai.example/v1",
        "model": "gpt-5.4-mini",
        "timeout_seconds": 45.0,
        "proxy_url": "http://proxy.local:7890",
    }
    assert created["metadata_scraper_kwargs"]["cast_localization_service"] is not None


class _FakeDatabase:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True


def test_main_builds_qb_only_runtime_without_prowlarr_or_legacy_transmission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_main_settings(
        downloader_instances=(
            DownloaderInstanceConfig(
                name="qb-main",
                downloader_type="qbittorrent",
                base_url="http://qb:8080",
                download_dir="/data/downloads/qb",
            ),
        ),
        downloader_role_binding=DownloaderRoleBinding(pt_downloader="qb-main", bt_downloader="qb-main"),
    )
    created: dict[str, object] = {}

    async def _empty_search(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return []

    def _simple_component(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace()

    def _build_manage_watchlist_service(*args: object, **kwargs: object) -> SimpleNamespace:
        created["manage_watchlist_service_args"] = args
        created["manage_watchlist_service_kwargs"] = kwargs
        return SimpleNamespace()

    def _build_add_to_downloader_service(*args: object, **kwargs: object) -> SimpleNamespace:
        created["add_to_downloader_service_args"] = args
        created["add_to_downloader_service_kwargs"] = kwargs
        return SimpleNamespace()

    def _fake_build_application(
        token: str,
        search_service,
        add_to_downloader_service,
        get_download_status_service,
        import_to_library_service,
        cleanup_downloaded_source_service,
        manage_watchlist_service,
        manage_bt_subscription_service,
        **kwargs: object,
    ) -> SimpleNamespace:
        channel_contact_registry = kwargs["channel_contact_registry"]
        app = SimpleNamespace(
            bot_data={
                tg.SEARCH_SERVICE_KEY: search_service,
                tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: manage_bt_subscription_service,
                tg.DOWNLOADER_INSTANCES_KEY: kwargs["downloader_instances"],
                tg.DOWNLOADER_ROLE_BINDING_KEY: kwargs["downloader_role_binding"],
                CHANNEL_CONTACT_REGISTRY_KEY: channel_contact_registry,
            }
        )
        created["token"] = token
        created["app"] = app
        created["channel_contact_registry"] = channel_contact_registry
        return app

    monkeypatch.setattr("app.main.load_settings", lambda: settings)
    monkeypatch.setattr("app.main.configure_trace_log_file", lambda **_kwargs: None)
    monkeypatch.setattr("app.main.SqliteDatabase", _FakeDatabase)
    monkeypatch.setattr("app.main.CandidateMappingRepo", _simple_component)
    monkeypatch.setattr("app.main.JobEventRepo", _simple_component)
    monkeypatch.setattr("app.main.JobRepo", _simple_component)
    monkeypatch.setattr("app.main.ApprovalRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultContentRegistryRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultDuplicateMemorySnapshotRepo", _simple_component)
    monkeypatch.setattr("app.main.BtPendingRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSubscriptionRepo", _simple_component)
    monkeypatch.setattr("app.main.DownloadMonitorRepo", _simple_component)
    monkeypatch.setattr("app.main.TelegramUpdateRepo", _simple_component)
    monkeypatch.setattr("app.main.WatchlistRepo", _simple_component)
    monkeypatch.setattr("app.main.ClarificationRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSourceProvider", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(
        "app.main.BtSourceAdapter",
        lambda *_args, **_kwargs: SimpleNamespace(search=_empty_search, search_page=_empty_search),
    )
    monkeypatch.setattr(
        "app.main.JavLibraryReadOnlyHelperClient",
        lambda **_kwargs: SimpleNamespace(lookup=lambda *_args, **_inner_kwargs: None),
    )
    monkeypatch.setattr("app.main.SearchMediaService", _simple_component)
    monkeypatch.setattr("app.main.AdultDuplicateMemoryService", _simple_component)
    monkeypatch.setattr("app.main.AddToDownloaderService", _build_add_to_downloader_service)
    monkeypatch.setattr("app.main.ImportToLibraryService", _simple_component)
    monkeypatch.setattr("app.main.PostDownloadAutoImportService", _simple_component)
    monkeypatch.setattr("app.main.GetDownloadStatusService", _simple_component)
    monkeypatch.setattr("app.main.CleanupDownloadedSourceService", _simple_component)
    monkeypatch.setattr("app.main.ManageWatchlistService", _build_manage_watchlist_service)
    monkeypatch.setattr("app.main.ManageBtSubscriptionService", _simple_component)
    monkeypatch.setattr("app.main.AdultArchiveService", _simple_component)
    monkeypatch.setattr("app.main.SubtitleTranslatorService", lambda **_kwargs: SimpleNamespace(translate_for_import=None))
    monkeypatch.setattr("app.main.PersonalWeChatLoginService", _simple_component)
    monkeypatch.setattr("app.main._build_refresh_media_server_func", lambda _settings: None)
    monkeypatch.setattr("app.main.build_application", _fake_build_application)
    monkeypatch.setattr("app.main._run_application_polling", lambda _application: None)
    monkeypatch.setattr("app.main.ProwlarrClient", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("ProwlarrClient should not be created")))
    monkeypatch.setattr("app.main.TransmissionClient", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("legacy TransmissionClient should not be created")))
    monkeypatch.setattr(
        "app.main.QbittorrentClient",
        lambda **_kwargs: created.setdefault("qb_client_calls", []).append(_kwargs) or SimpleNamespace(),
    )

    run_main()

    app = created["app"]
    assert created["token"] == "telegram-token"
    assert created["channel_contact_registry"] is app.bot_data[CHANNEL_CONTACT_REGISTRY_KEY]
    assert tg.SEARCH_SERVICE_KEY in app.bot_data
    assert tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY in app.bot_data
    assert isinstance(app.bot_data[CHANNEL_CONTACT_REGISTRY_KEY], ChannelContactRegistry)
    assert app.bot_data[tg.DOWNLOADER_ROLE_BINDING_KEY] == settings.downloader_role_binding
    assert app.bot_data[tg.DOWNLOADER_INSTANCES_KEY] == settings.downloader_instances
    assert app.bot_data["search_capability_unavailable_text"].startswith("搜索能力当前不可用")
    assert app.bot_data["bt_subscription_capability_unavailable_text"].startswith("BT 订阅当前不可用")
    assert len(created["manage_watchlist_service_args"]) == 1
    assert "bt_subscription_repo" in created["manage_watchlist_service_kwargs"]
    assert "adult_duplicate_memory_service" in created["add_to_downloader_service_kwargs"]
    assert "bt_pending_repo" in created["add_to_downloader_service_kwargs"]
    assert len(created["qb_client_calls"]) == 1


def test_main_reuses_subtitle_translation_settings_for_adult_metadata_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_main_settings(
        subtitle_translation_api_key="adult-translate-key",
        subtitle_translation_base_url="https://openai.example/v1",
        subtitle_translation_model="gpt-5.4-mini",
        subtitle_translation_timeout_seconds=45.0,
        outbound_proxy_url="http://proxy.local:7890",
    )
    created: dict[str, object] = {}
    translate_candidates_sentinel = object()

    async def _empty_search(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return []

    def _simple_component(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace()

    class _FakeAdultMetadataTranslatorService:
        def __init__(self, **kwargs: object) -> None:
            created["adult_metadata_translator_kwargs"] = kwargs
            self.translate_candidates = translate_candidates_sentinel

    def _capture_search_media_service(*_args: object, **kwargs: object) -> SimpleNamespace:
        created["search_media_service_kwargs"] = kwargs
        return SimpleNamespace()

    def _fake_build_application(
        token: str,
        search_service,
        add_to_downloader_service,
        get_download_status_service,
        import_to_library_service,
        cleanup_downloaded_source_service,
        manage_watchlist_service,
        manage_bt_subscription_service,
        **kwargs: object,
    ) -> SimpleNamespace:
        return SimpleNamespace(bot_data={tg.SEARCH_SERVICE_KEY: search_service})

    monkeypatch.setattr("app.main.load_settings", lambda: settings)
    monkeypatch.setattr("app.main.configure_trace_log_file", lambda **_kwargs: None)
    monkeypatch.setattr("app.main.SqliteDatabase", _FakeDatabase)
    monkeypatch.setattr("app.main.CandidateMappingRepo", _simple_component)
    monkeypatch.setattr("app.main.JobEventRepo", _simple_component)
    monkeypatch.setattr("app.main.JobRepo", _simple_component)
    monkeypatch.setattr("app.main.ApprovalRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultContentRegistryRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultDuplicateMemorySnapshotRepo", _simple_component)
    monkeypatch.setattr("app.main.BtPendingRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSubscriptionRepo", _simple_component)
    monkeypatch.setattr("app.main.DownloadMonitorRepo", _simple_component)
    monkeypatch.setattr("app.main.TelegramUpdateRepo", _simple_component)
    monkeypatch.setattr("app.main.WatchlistRepo", _simple_component)
    monkeypatch.setattr("app.main.ClarificationRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSourceProvider", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(
        "app.main.BtSourceAdapter",
        lambda *_args, **_kwargs: SimpleNamespace(search=_empty_search, search_page=_empty_search),
    )
    monkeypatch.setattr("app.main._build_adult_read_only_lookup_func", lambda *, proxy_url: SimpleNamespace(proxy_url=proxy_url))
    monkeypatch.setattr("app.main.SearchMediaService", _capture_search_media_service)
    monkeypatch.setattr("app.main.AdultMetadataTranslatorService", _FakeAdultMetadataTranslatorService)
    monkeypatch.setattr("app.main.AdultDuplicateMemoryService", _simple_component)
    monkeypatch.setattr("app.main.AddToDownloaderService", _simple_component)
    monkeypatch.setattr("app.main.ImportToLibraryService", _simple_component)
    monkeypatch.setattr("app.main.PostDownloadAutoImportService", _simple_component)
    monkeypatch.setattr("app.main.GetDownloadStatusService", _simple_component)
    monkeypatch.setattr("app.main.CleanupDownloadedSourceService", _simple_component)
    monkeypatch.setattr("app.main.ManageWatchlistService", _simple_component)
    monkeypatch.setattr("app.main.ManageBtSubscriptionService", _simple_component)
    monkeypatch.setattr("app.main.AdultArchiveService", _simple_component)
    monkeypatch.setattr("app.main.SubtitleTranslatorService", lambda **_kwargs: SimpleNamespace(translate_for_import=None))
    monkeypatch.setattr("app.main.PersonalWeChatLoginService", _simple_component)
    monkeypatch.setattr("app.main._build_refresh_media_server_func", lambda _settings: None)
    monkeypatch.setattr("app.main.build_application", _fake_build_application)
    monkeypatch.setattr("app.main._run_application_polling", lambda _application: None)
    monkeypatch.setattr(
        "app.main.ProwlarrClient",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("ProwlarrClient should not be created")),
    )
    monkeypatch.setattr(
        "app.main.TransmissionClient",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("legacy TransmissionClient should not be created")),
    )
    monkeypatch.setattr(
        "app.main.QbittorrentClient",
        lambda **_kwargs: created.setdefault("qb_client_calls", []).append(_kwargs) or SimpleNamespace(),
    )

    run_main()

    assert created["adult_metadata_translator_kwargs"] == {
        "api_key": "adult-translate-key",
        "base_url": "https://openai.example/v1",
        "model": "gpt-5.4-mini",
        "timeout_seconds": 45.0,
        "proxy_url": "http://proxy.local:7890",
    }
    assert created["search_media_service_kwargs"]["adult_metadata_translate_func"] is translate_candidates_sentinel


def test_main_uses_non_telegram_host_when_feishu_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_main_settings(
        telegram_bot_token="",
        feishu_app_id="feishu-app-id",
        feishu_app_secret="feishu-app-secret",
    )
    created: dict[str, object] = {}

    async def _empty_search(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return []

    def _simple_component(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace()

    async def _fake_run_non_telegram_host(host, *, config) -> None:
        created["host"] = host
        created["config"] = config

    def _fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Telegram application path should not be used for Feishu-only startup")

    monkeypatch.setattr("app.main.load_settings", lambda: settings)
    monkeypatch.setattr("app.main.configure_trace_log_file", lambda **_kwargs: None)
    monkeypatch.setattr("app.main.SqliteDatabase", _FakeDatabase)
    monkeypatch.setattr("app.main.CandidateMappingRepo", _simple_component)
    monkeypatch.setattr("app.main.JobEventRepo", _simple_component)
    monkeypatch.setattr("app.main.JobRepo", _simple_component)
    monkeypatch.setattr("app.main.ApprovalRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultContentRegistryRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultDuplicateMemorySnapshotRepo", _simple_component)
    monkeypatch.setattr("app.main.BtPendingRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSubscriptionRepo", _simple_component)
    monkeypatch.setattr("app.main.DownloadMonitorRepo", _simple_component)
    monkeypatch.setattr("app.main.TelegramUpdateRepo", _simple_component)
    monkeypatch.setattr("app.main.WatchlistRepo", _simple_component)
    monkeypatch.setattr("app.main.ClarificationRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSourceProvider", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(
        "app.main.BtSourceAdapter",
        lambda *_args, **_kwargs: SimpleNamespace(search=_empty_search, search_page=_empty_search),
    )
    monkeypatch.setattr(
        "app.main.JavLibraryReadOnlyHelperClient",
        lambda **_kwargs: SimpleNamespace(lookup=lambda *_args, **_inner_kwargs: None),
    )
    monkeypatch.setattr("app.main.SearchMediaService", _simple_component)
    monkeypatch.setattr("app.main.AdultDuplicateMemoryService", _simple_component)
    monkeypatch.setattr("app.main.AddToDownloaderService", _simple_component)
    monkeypatch.setattr("app.main.ImportToLibraryService", _simple_component)
    monkeypatch.setattr("app.main.PostDownloadAutoImportService", _simple_component)
    monkeypatch.setattr("app.main.GetDownloadStatusService", _simple_component)
    monkeypatch.setattr("app.main.CleanupDownloadedSourceService", _simple_component)
    monkeypatch.setattr("app.main.ManageWatchlistService", _simple_component)
    monkeypatch.setattr("app.main.ManageBtSubscriptionService", _simple_component)
    monkeypatch.setattr("app.main.AdultArchiveService", _simple_component)
    monkeypatch.setattr("app.main.SubtitleTranslatorService", lambda **_kwargs: SimpleNamespace(translate_for_import=None))
    monkeypatch.setattr("app.main.PersonalWeChatLoginService", _simple_component)
    monkeypatch.setattr("app.main._build_refresh_media_server_func", lambda _settings: None)
    monkeypatch.setattr("app.main.build_application", _fail_if_called)
    monkeypatch.setattr("app.main._run_application_polling", _fail_if_called)
    monkeypatch.setattr("app.main._run_non_telegram_host", _fake_run_non_telegram_host)
    monkeypatch.setattr(
        "app.main.ProwlarrClient",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("ProwlarrClient should not be created")),
    )
    monkeypatch.setattr(
        "app.main.TransmissionClient",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("legacy TransmissionClient should not be created")),
    )
    monkeypatch.setattr(
        "app.main.QbittorrentClient",
        lambda **_kwargs: created.setdefault("qb_client_calls", []).append(_kwargs) or SimpleNamespace(),
    )
    monkeypatch.setattr(
        "app.main.FeishuClient",
        lambda **_kwargs: created.setdefault("feishu_client_calls", []).append(_kwargs) or SimpleNamespace(),
    )
    monkeypatch.setattr(
        "app.main.FeishuLongConnectionService",
        lambda **kwargs: created.setdefault("feishu_service_calls", []).append(kwargs) or SimpleNamespace(),
    )

    run_main()

    host = created["host"]
    assert created["config"].post_download_auto_import_service_key == "post_download_auto_import_service"
    assert FEISHU_LONG_CONNECTION_SERVICE_KEY in host.bot_data
    assert isinstance(host.bot_data[CHANNEL_CONTACT_REGISTRY_KEY], ChannelContactRegistry)
    assert callable(host.bot_data[SIDECAR_HOST_SEND_TEXT_FUNC_KEY])
    assert created["feishu_client_calls"][0]["app_id"] == "feishu-app-id"
    assert created["feishu_service_calls"][0]["config"].app_id == "feishu-app-id"
    assert created["feishu_service_calls"][0]["config"].app_secret == "feishu-app-secret"
    assert created.get("qb_client_calls", []) == []


def test_main_uses_non_telegram_host_when_wecom_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_main_settings(
        telegram_bot_token="",
        wecom_token="wecom-token",
        wecom_encoding_aes_key="wecom-aes",
        wecom_receive_id="wecom-receive-id",
    )
    created: dict[str, object] = {}

    async def _empty_search(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return []

    def _simple_component(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace()

    async def _fake_run_non_telegram_host(host, *, config) -> None:
        created["host"] = host
        created["config"] = config

    def _fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Telegram application path should not be used for WeCom-only startup")

    monkeypatch.setattr("app.main.load_settings", lambda: settings)
    monkeypatch.setattr("app.main.configure_trace_log_file", lambda **_kwargs: None)
    monkeypatch.setattr("app.main.SqliteDatabase", _FakeDatabase)
    monkeypatch.setattr("app.main.CandidateMappingRepo", _simple_component)
    monkeypatch.setattr("app.main.JobEventRepo", _simple_component)
    monkeypatch.setattr("app.main.JobRepo", _simple_component)
    monkeypatch.setattr("app.main.ApprovalRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultContentRegistryRepo", _simple_component)
    monkeypatch.setattr("app.main.AdultDuplicateMemorySnapshotRepo", _simple_component)
    monkeypatch.setattr("app.main.BtPendingRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSubscriptionRepo", _simple_component)
    monkeypatch.setattr("app.main.DownloadMonitorRepo", _simple_component)
    monkeypatch.setattr("app.main.TelegramUpdateRepo", _simple_component)
    monkeypatch.setattr("app.main.WatchlistRepo", _simple_component)
    monkeypatch.setattr("app.main.ClarificationRepo", _simple_component)
    monkeypatch.setattr("app.main.BtSourceProvider", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(
        "app.main.BtSourceAdapter",
        lambda *_args, **_kwargs: SimpleNamespace(search=_empty_search, search_page=_empty_search),
    )
    monkeypatch.setattr(
        "app.main.JavLibraryReadOnlyHelperClient",
        lambda **_kwargs: SimpleNamespace(lookup=lambda *_args, **_inner_kwargs: None),
    )
    monkeypatch.setattr("app.main.SearchMediaService", _simple_component)
    monkeypatch.setattr("app.main.AdultDuplicateMemoryService", _simple_component)
    monkeypatch.setattr("app.main.AddToDownloaderService", _simple_component)
    monkeypatch.setattr("app.main.ImportToLibraryService", _simple_component)
    monkeypatch.setattr("app.main.PostDownloadAutoImportService", _simple_component)
    monkeypatch.setattr("app.main.GetDownloadStatusService", _simple_component)
    monkeypatch.setattr("app.main.CleanupDownloadedSourceService", _simple_component)
    monkeypatch.setattr("app.main.ManageWatchlistService", _simple_component)
    monkeypatch.setattr("app.main.ManageBtSubscriptionService", _simple_component)
    monkeypatch.setattr("app.main.AdultArchiveService", _simple_component)
    monkeypatch.setattr("app.main.SubtitleTranslatorService", lambda **_kwargs: SimpleNamespace(translate_for_import=None))
    monkeypatch.setattr("app.main.PersonalWeChatLoginService", _simple_component)
    monkeypatch.setattr("app.main._build_refresh_media_server_func", lambda _settings: None)
    monkeypatch.setattr("app.main.build_application", _fail_if_called)
    monkeypatch.setattr("app.main._run_application_polling", _fail_if_called)
    monkeypatch.setattr("app.main._run_non_telegram_host", _fake_run_non_telegram_host)
    monkeypatch.setattr(
        "app.main.ProwlarrClient",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("ProwlarrClient should not be created")),
    )
    monkeypatch.setattr(
        "app.main.TransmissionClient",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("legacy TransmissionClient should not be created")),
    )
    monkeypatch.setattr(
        "app.main.QbittorrentClient",
        lambda **_kwargs: created.setdefault("qb_client_calls", []).append(_kwargs) or SimpleNamespace(),
    )
    monkeypatch.setattr(
        "app.main.FeishuClient",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("FeishuClient should not be created in WeCom-only mode")),
    )
    monkeypatch.setattr(
        "app.main.FeishuLongConnectionService",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("FeishuLongConnectionService should not be created in WeCom-only mode")),
    )

    run_main()

    host = created["host"]
    assert created["config"].post_download_auto_import_service_key == "post_download_auto_import_service"
    assert WECOM_TOKEN_BOT_DATA_KEY in host.bot_data
    assert WECOM_ENCODING_AES_KEY_BOT_DATA_KEY in host.bot_data
    assert WECOM_RECEIVE_ID_BOT_DATA_KEY in host.bot_data
    assert isinstance(host.bot_data[CHANNEL_CONTACT_REGISTRY_KEY], ChannelContactRegistry)
    assert callable(host.bot_data[SIDECAR_HOST_SEND_TEXT_FUNC_KEY])
    assert isinstance(host.bot_data["wecom_webhook_server_config"], WeComWebhookServerConfig)
    assert FEISHU_LONG_CONNECTION_SERVICE_KEY not in host.bot_data


def test_start_bt_subscription_scheduler_skips_without_send_text_callback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    host = SimpleNamespace(
        bot_data={
            MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: SimpleNamespace(run_scheduler_tick=AsyncMock(return_value=())),
            DOWNLOADER_INSTANCES_KEY: {
                "bt-main": SimpleNamespace(name="bt-main", downloader_type="transmission", download_dir="/data"),
            },
            DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="bt-main", bt_downloader="bt-main"),
        },
        create_task=Mock(),
    )

    _start_bt_subscription_scheduler_if_configured(host)

    output = capsys.readouterr().out
    assert "[BT 订阅后台扫描未启动]" in output
    assert "主动 send_text 能力" in output
    assert host.create_task.call_count == 0
    assert BT_SUBSCRIPTION_SCHEDULER_TASK_KEY not in host.bot_data


async def _return_async(value):
    return value
