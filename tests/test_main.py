from __future__ import annotations

from types import SimpleNamespace

import pytest
from telegram.error import NetworkError

from app.main import _resolve_downloader_client_for_lookup, _resolve_downloader_name_for_task, _run_application_polling


def test_run_application_polling_prints_colored_fix_hint_on_network_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = SimpleNamespace(run_polling=lambda **_: (_ for _ in ()).throw(NetworkError("dns fail")))

    with pytest.raises(NetworkError):
        _run_application_polling(app)

    captured = capsys.readouterr()
    assert "[Telegram 启动失败]" in captured.out
    assert "[处理建议]" in captured.out


def test_resolve_downloader_name_for_task_fails_closed_when_lookup_is_missing() -> None:
    job_repo = SimpleNamespace(
        get_downloader_job_for_chat_ref=lambda **_: None,
    )
    assert _resolve_downloader_name_for_task(task_ref="87", chat_id=1001, job_repo=job_repo) is None


def test_resolve_downloader_client_for_lookup_returns_none_for_unknown_instance() -> None:
    known_client = object()
    assert _resolve_downloader_client_for_lookup(
        downloader_name="missing",
        downloader_instances_by_name={},
        transmission_clients_by_name={},
        qbittorrent_clients_by_name={},
    ) is None
    assert _resolve_downloader_client_for_lookup(
        downloader_name="pt-main",
        downloader_instances_by_name={"pt-main": SimpleNamespace(downloader_type="transmission")},
        transmission_clients_by_name={"pt-main": known_client},
        qbittorrent_clients_by_name={},
    ) is known_client
