from __future__ import annotations

from app.config import DownloaderInstanceConfig
from app.downloader_route_lookup import resolve_downloader_dispatch_download_dir


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
