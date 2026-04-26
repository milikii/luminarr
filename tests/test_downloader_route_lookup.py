from __future__ import annotations

import asyncio

from app.clients.transmission import TransmissionImportSource
from app.config import DownloaderInstanceConfig
from app.downloader_route_lookup import (
    _get_torrent_import_source_with_routing,
    resolve_downloader_dispatch_download_dir,
)


def test_resolve_downloader_dispatch_download_dir_uses_instance_dispatch_path() -> None:
    resolved = resolve_downloader_dispatch_download_dir(
        downloader_name="tr-bt",
        requested_download_dir="/data/downloads/tr-bt",
        downloader_instances_by_name={
            "tr-bt": DownloaderInstanceConfig(
                name="tr-bt",
                downloader_type="transmission",
                base_url="http://127.0.0.1:19092",
                download_dir="/data/downloads/tr-bt",
                dispatch_download_dir="/downloads/complete",
            )
        },
    )

    assert resolved == "/downloads/complete"


def test_resolve_downloader_dispatch_download_dir_keeps_custom_target_dir() -> None:
    resolved = resolve_downloader_dispatch_download_dir(
        downloader_name="tr-bt",
        requested_download_dir="/data/downloads/custom-bt",
        downloader_instances_by_name={
            "tr-bt": DownloaderInstanceConfig(
                name="tr-bt",
                downloader_type="transmission",
                base_url="http://127.0.0.1:19092",
                download_dir="/data/downloads/tr-bt",
                dispatch_download_dir="/downloads/complete",
            )
        },
    )

    assert resolved == "/data/downloads/custom-bt"


def test_resolve_downloader_dispatch_download_dir_keeps_requested_dir_without_dispatch_override() -> None:
    resolved = resolve_downloader_dispatch_download_dir(
        downloader_name="tr-bt",
        requested_download_dir="/data/downloads/tr-bt",
        downloader_instances_by_name={
            "tr-bt": DownloaderInstanceConfig(
                name="tr-bt",
                downloader_type="transmission",
                base_url="http://127.0.0.1:19092",
                download_dir="/data/downloads/tr-bt",
            )
        },
    )

    assert resolved == "/data/downloads/tr-bt"


def test_get_torrent_import_source_with_routing_restores_host_download_dir() -> None:
    class FakeJobRepo:
        def get_downloader_job_for_chat_ref(self, *, chat_id: int, task_ref: str):
            assert chat_id == 1001
            assert task_ref == "hash-42"
            return type(
                "FakeJob",
                (),
                {
                    "payload_json": (
                        '{"downloader_name":"tr-bt","download_dir":"/data/downloads/tr-bt"}'
                    )
                },
            )()

    class FakeTransmissionClient:
        async def get_torrent_import_source(self, task_ref: str) -> TransmissionImportSource | None:
            assert task_ref == "hash-42"
            return TransmissionImportSource(
                task_id="42",
                task_hash="hash-42",
                name="SSIS-456-smoke.mp4",
                download_dir="/downloads/complete",
                is_finished=True,
                percent_done=1.0,
            )

    import_source = asyncio.run(
        _get_torrent_import_source_with_routing(
            task_ref="hash-42",
            chat_id=1001,
            job_repo=FakeJobRepo(),
            downloader_instances_by_name={
                "tr-bt": DownloaderInstanceConfig(
                    name="tr-bt",
                    downloader_type="transmission",
                    base_url="http://127.0.0.1:19092",
                    download_dir="/data/downloads/tr-bt",
                    dispatch_download_dir="/downloads/complete",
                )
            },
            transmission_clients_by_name={"tr-bt": FakeTransmissionClient()},
            qbittorrent_clients_by_name={},
        )
    )

    assert import_source is not None
    assert import_source.download_dir == "/data/downloads/tr-bt"
    assert import_source.name == "SSIS-456-smoke.mp4"
