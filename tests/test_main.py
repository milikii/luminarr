from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from telegram.error import NetworkError

from app.downloader_route_lookup import _resolve_downloader_name_for_task
from app.main import (
    DownloaderRouteLookupError,
    _build_refresh_media_server_func,
    _get_torrent_import_source_with_routing,
    _get_torrent_status_with_routing,
    _resolve_downloader_client_for_dispatch,
    _resolve_downloader_client_for_lookup,
    _run_application_polling,
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


def test_resolve_downloader_name_for_task_fails_closed_when_lookup_is_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: None,
    )
    assert _resolve_downloader_name_for_task(task_ref="87", chat_id=1001, job_repo=job_repo) is None
    captured = capsys.readouterr()
    assert "[下载器路由未命中]" in captured.out
    assert "[处理建议]" in captured.out


def test_resolve_downloader_name_for_task_logs_lookup_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    assert _resolve_downloader_name_for_task(task_ref="87", chat_id=1001, job_repo=job_repo) is None

    captured = capsys.readouterr()
    assert "[下载器路由查询失败]" in captured.out
    assert "task_ref=87" in captured.out
    assert "db down" in captured.out
    assert "[处理建议]" in captured.out


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

    assert _resolve_downloader_name_for_task(task_ref="87", chat_id=1001, job_repo=job_repo) is None

    captured = capsys.readouterr()
    assert "[下载器路由载荷损坏]" in captured.out
    assert expected_reason in captured.out
    assert "[处理建议]" in captured.out


def test_resolve_downloader_client_for_lookup_returns_none_for_unknown_instance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    known_client = object()
    assert _resolve_downloader_client_for_lookup(
        downloader_name="missing",
        downloader_instances_by_name={},
        transmission_clients_by_name={},
        qbittorrent_clients_by_name={},
    ) is None
    captured = capsys.readouterr()
    assert "[下载器实例不存在]" in captured.out
    assert "[处理建议]" in captured.out
    assert _resolve_downloader_client_for_lookup(
        downloader_name="pt-main",
        downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
        transmission_clients_by_name={"pt-main": known_client},
        qbittorrent_clients_by_name={},
    ) is known_client


def test_resolve_downloader_client_for_lookup_logs_missing_client(capsys: pytest.CaptureFixture[str]) -> None:
    assert _resolve_downloader_client_for_lookup(
        downloader_name="pt-main",
        downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
        transmission_clients_by_name={},
        qbittorrent_clients_by_name={},
    ) is None

    captured = capsys.readouterr()
    assert "[下载器客户端未配置]" in captured.out
    assert "downloader_name=pt-main" in captured.out
    assert "downloader_type=transmission" in captured.out
    assert "[处理建议]" in captured.out


def test_get_torrent_import_source_with_routing_raises_when_route_lookup_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: (_ for _ in ()).throw(RuntimeError("db down")),
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


def test_build_refresh_media_server_func_returns_none_without_media_server_settings() -> None:
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


async def _return_async(value):
    return value
