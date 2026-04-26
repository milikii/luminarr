from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import socket
import sys
import threading
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.clients.qbittorrent import QbittorrentClient
from app.config import AdultArchiveDestination
from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.db.download_monitor_repo import DownloadMonitorRecord
from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.adult_archive_service import AdultArchiveService
from app.services.post_download_auto_import import PostDownloadAutoImportService


QB_LOG_PATH = ROOT / "docker/test/qbittorrent/qBittorrent/logs/qbittorrent.log"
QB_BASE_URL = "http://127.0.0.1:18098"
QB_API_BASE = f"{QB_BASE_URL}/api/v2"
SMOKE_ROOT = Path("/tmp/luminarr_adult_archive_qb_real_smoke")
DOWNLOAD_DIR = Path("/data/downloads/qb/luminarr_adult_archive_smoke")
ARCHIVE_DIR = SMOKE_ROOT / "archive" / "censored"
TORRENT_PATH = SMOKE_ROOT / "SSIS-123-smoke.torrent"
EVIDENCE_PATH = SMOKE_ROOT / "evidence.json"
DB_PATH = SMOKE_ROOT / "state.sqlite3"
WEBSEED_ROOT = SMOKE_ROOT / "webseed"
SOURCE_NAME = "SSIS-123-smoke.mp4"
WEBSEED_FILE_PATH = WEBSEED_ROOT / SOURCE_NAME
SOURCE_PATH = DOWNLOAD_DIR / SOURCE_NAME
SOURCE_BYTES = b"luminarr adult archive qb real smoke\n"
SOURCE_SITE = "javbus"
CONTENT_ID = "censored:ssis-123"
DISPLAY_ID = "SSIS-123"
CHAT_ID = 1001
USER_ID = 2001
FINISHED_STATES = {"uploading", "forcedup", "stalledup", "pausedup", "queuedup"}


def _bencode(value: object) -> bytes:
    if isinstance(value, int):
        return f"i{value}e".encode("ascii")
    if isinstance(value, bytes):
        return str(len(value)).encode("ascii") + b":" + value
    if isinstance(value, str):
        return _bencode(value.encode("utf-8"))
    if isinstance(value, (list, tuple)):
        return b"l" + b"".join(_bencode(item) for item in value) + b"e"
    if isinstance(value, dict):
        encoded_items: list[bytes] = []
        normalized_items: list[tuple[bytes, object]] = []
        for key, item in value.items():
            if isinstance(key, bytes):
                encoded_key = key
            else:
                encoded_key = str(key).encode("utf-8")
            normalized_items.append((encoded_key, item))
        for encoded_key, item in sorted(normalized_items, key=lambda pair: pair[0]):
            encoded_items.append(_bencode(encoded_key))
            encoded_items.append(_bencode(item))
        return b"d" + b"".join(encoded_items) + b"e"
    raise TypeError(f"unsupported bencode type: {type(value)!r}")


def _build_single_file_torrent_bytes(
    *,
    file_name: str,
    file_bytes: bytes,
    webseed_urls: tuple[str, ...],
) -> tuple[bytes, str]:
    piece_length = 16384
    info = {
        "length": len(file_bytes),
        "name": file_name,
        "piece length": piece_length,
        "pieces": hashlib.sha1(file_bytes).digest(),
    }
    info_bytes = _bencode(info)
    torrent_payload: dict[str, object] = {
        "announce": "http://tracker.invalid/announce",
        "created by": "luminarr adult archive smoke",
        "creation date": int(datetime.now(UTC).timestamp()),
        "info": info,
    }
    if webseed_urls:
        torrent_payload["url-list"] = webseed_urls
    torrent_bytes = _bencode(torrent_payload)
    return torrent_bytes, hashlib.sha1(info_bytes).hexdigest()


class _StaticFileServer:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "_StaticFileServer":
        directory = self._directory

        class _Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args: object, **kwargs: object) -> None:
                super().__init__(*args, directory=str(directory), **kwargs)

            def log_message(self, format: str, *args: object) -> None:
                _ = (format, args)

        server = ThreadingHTTPServer(("0.0.0.0", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._server = server
        self._thread = thread
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    @property
    def port(self) -> int:
        if self._server is None:
            raise RuntimeError("static server not started")
        return int(self._server.server_port)


def _resolve_candidate_webseed_urls(*, file_name: str, port: int) -> tuple[str, ...]:
    host_candidates = {
        "127.0.0.1",
        "host.docker.internal",
        "172.17.0.1",
    }
    try:
        host_name = socket.gethostname()
        host_candidates.update(
            address[4][0]
            for address in socket.getaddrinfo(host_name, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
            if address[4][0]
        )
    except socket.gaierror:
        pass
    preferred = []
    for host in sorted(host_candidates):
        if host.startswith("127."):
            continue
        preferred.append(host)
    preferred.append("127.0.0.1")
    return tuple(
        f"http://{host}:{port}/{file_name}"
        for host in dict.fromkeys(preferred)
    )


async def _qb_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    data: dict[str, str] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    response = await client.request(
        method,
        f"{QB_API_BASE}{path}",
        data=data,
        files=files,
        params=params,
    )
    response.raise_for_status()
    return response


async def _fetch_torrent_snapshot(info_hash: str) -> dict[str, object] | None:
    if not info_hash:
        return None
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        response = await _qb_request(client, "GET", "/torrents/info", params={"hashes": info_hash})
    data = response.json()
    if not isinstance(data, list) or not data:
        return None
    torrent = data[0]
    if not isinstance(torrent, dict):
        return None
    return {str(key): value for key, value in torrent.items()}


def _load_qb_log_excerpt(*, needle: str, limit: int = 12) -> list[str]:
    if not QB_LOG_PATH.exists():
        return []
    lines = QB_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    matched = [line for line in lines if needle in line]
    return matched[-limit:]


def _build_path_state(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "is_file": path.is_file(),
    }


async def _delete_torrent_if_present(client: httpx.AsyncClient, info_hash: str) -> None:
    response = await _qb_request(client, "GET", "/torrents/info", params={"hashes": info_hash})
    data = response.json()
    if isinstance(data, list) and data:
        await _qb_request(
            client,
            "POST",
            "/torrents/delete",
            data={"hashes": info_hash, "deleteFiles": "true"},
        )


async def _upload_torrent_and_wait_until_complete(*, torrent_bytes: bytes, info_hash: str) -> dict[str, object]:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        await _delete_torrent_if_present(client, info_hash)
        response = await _qb_request(
            client,
            "POST",
            "/torrents/add",
            data={"savepath": str(DOWNLOAD_DIR)},
            files={"torrents": (TORRENT_PATH.name, torrent_bytes, "application/x-bittorrent")},
        )
        if response.text.strip() not in {"Ok.", ""}:
            raise RuntimeError(f"unexpected qB add response: {response.text!r}")
        await _qb_request(client, "POST", "/torrents/recheck", data={"hashes": info_hash})
        await _qb_request(client, "POST", "/torrents/start", data={"hashes": info_hash})

        last_seen: dict[str, object] | None = None
        for _ in range(40):
            info_response = await _qb_request(client, "GET", "/torrents/info", params={"hashes": info_hash})
            data = info_response.json()
            if isinstance(data, list) and data:
                torrent = data[0]
                if isinstance(torrent, dict):
                    last_seen = torrent
                    progress = float(torrent.get("progress") or 0.0)
                    state = str(torrent.get("state") or "").strip().lower()
                    if progress >= 1.0 or state in FINISHED_STATES:
                        return torrent
            await asyncio.sleep(0.5)
    raise RuntimeError(f"qB torrent did not reach completed state: {last_seen!r}")


def _build_completed_record(*, info_hash: str, completion_observed_at: str) -> DownloadMonitorRecord:
    return DownloadMonitorRecord(
        task_id=info_hash,
        task_hash=info_hash,
        name=SOURCE_NAME,
        chat_id=CHAT_ID,
        user_id=USER_ID,
        status_code=6,
        percent_done=1.0,
        is_complete=True,
        completion_observed_at=completion_observed_at,
        last_observed_at=completion_observed_at,
        created_at=completion_observed_at,
        updated_at=completion_observed_at,
    )


async def main() -> int:
    shutil.rmtree(SMOKE_ROOT, ignore_errors=True)
    SMOKE_ROOT.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    WEBSEED_ROOT.mkdir(parents=True, exist_ok=True)
    WEBSEED_FILE_PATH.write_bytes(SOURCE_BYTES)
    info_hash = ""
    webseed_urls: tuple[str, ...] = ()

    try:
        with _StaticFileServer(WEBSEED_ROOT) as static_server:
            webseed_urls = _resolve_candidate_webseed_urls(file_name=SOURCE_NAME, port=static_server.port)
            torrent_bytes, info_hash = _build_single_file_torrent_bytes(
                file_name=SOURCE_NAME,
                file_bytes=SOURCE_BYTES,
                webseed_urls=webseed_urls,
            )
            TORRENT_PATH.write_bytes(torrent_bytes)
            torrent = await _upload_torrent_and_wait_until_complete(torrent_bytes=torrent_bytes, info_hash=info_hash)

            database = SqliteDatabase(str(DB_PATH))
            database.initialize()
            registry_repo = AdultContentRegistryRepo(database)
            event_repo = JobEventRepo(database)
            registry_repo.mark_downloading(
                normalized_content_id=CONTENT_ID,
                content_id_kind="censored",
                archive_category="censored",
                display_title=DISPLAY_ID,
                latest_source_site=SOURCE_SITE,
                task_ref=info_hash,
                task_id=info_hash,
                task_hash=info_hash,
                downloader_name="qb-smoke",
            )

            qb_client = QbittorrentClient(QB_BASE_URL)

            async def _get_import_source(task_ref: str, _chat_id: int | None = None, _user_id: int | None = None):
                return await qb_client.get_torrent_import_source(task_ref)

            async def _remove_torrent(task_ref: str, _chat_id: int | None = None, delete_local_data: bool = True):
                await qb_client.remove_torrent(task_ref, delete_local_data=delete_local_data)

            archive_service = AdultArchiveService(
                get_import_source_func=_get_import_source,
                remove_torrent_func=_remove_torrent,
                registry_repo=registry_repo,
                job_event_repo=event_repo,
                archive_destinations=(
                    AdultArchiveDestination(
                        category="censored",
                        label="有码",
                        target_dir=str(ARCHIVE_DIR),
                    ),
                ),
                retention_hours=1,
            )
            auto_import_called = False

            async def _unexpected_auto_import(*_args: object) -> str:
                nonlocal auto_import_called
                auto_import_called = True
                raise RuntimeError("adult archive smoke should not enter normal auto-import")

            auto_import_service = PostDownloadAutoImportService(
                download_monitor_repo=None,
                job_event_repo=event_repo,
                auto_import_func=_unexpected_auto_import,
                adult_content_registry_repo=registry_repo,
                adult_archive_service=archive_service,
            )

            archive_reply = await auto_import_service.run_for_record(
                _build_completed_record(
                    info_hash=info_hash,
                    completion_observed_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
            archive_target = ARCHIVE_DIR / SOURCE_NAME
            archived_record = registry_repo.get_by_content_id(normalized_content_id=CONTENT_ID)
            if archive_reply is None or not archive_target.exists() or archived_record is None:
                raise RuntimeError("adult archive phase did not finish as expected")
            if archived_record.current_status != "archived_present":
                raise RuntimeError(f"adult archive status unexpected after archive: {archived_record.current_status}")

            cleanup_reply = await auto_import_service.run_for_record(
                _build_completed_record(
                    info_hash=info_hash,
                    completion_observed_at="2000-01-01 00:00:00",
                )
            )
            cleaned_record = registry_repo.get_by_content_id(normalized_content_id=CONTENT_ID)
            if cleanup_reply is None or cleaned_record is None:
                raise RuntimeError("adult archive cleanup phase did not finish as expected")
            if cleaned_record.current_status != "archived_deleted":
                raise RuntimeError(f"adult archive status unexpected after cleanup: {cleaned_record.current_status}")

            removed_from_qb = False
            for _ in range(10):
                if await qb_client.get_torrent_status(info_hash) is None:
                    removed_from_qb = True
                    break
                await asyncio.sleep(0.5)
            if not removed_from_qb:
                raise RuntimeError("qB torrent still present after adult retention cleanup")
            if SOURCE_PATH.exists():
                raise RuntimeError("adult source file still present after retention cleanup")
            if auto_import_called:
                raise RuntimeError("adult archive smoke unexpectedly entered normal auto-import path")

            events = event_repo.list_events_for_task_identity(task_id=info_hash, task_hash=info_hash)
            evidence = {
                "status": "passed",
                "qB_base_url": QB_BASE_URL,
                "info_hash": info_hash,
                "torrent_state": str(torrent.get("state") or ""),
                "webseed_urls": webseed_urls,
                "archive_reply": archive_reply,
                "cleanup_reply": cleanup_reply,
                "archive_target": str(archive_target),
                "source_path_removed": not SOURCE_PATH.exists(),
                "qb_removed": removed_from_qb,
                "registry_statuses": {
                    "after_archive": "archived_present",
                    "after_cleanup": cleaned_record.current_status,
                },
                "event_types": [event.event_type for event in events],
            }
            EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            print(EVIDENCE_PATH)
            return 0
    except Exception as error:
        failure_evidence = {
            "status": "failed",
            "error": str(error),
            "info_hash": info_hash,
            "webseed_urls": webseed_urls,
            "qb_torrent_snapshot": await _fetch_torrent_snapshot(info_hash),
            "qb_log_excerpt": _load_qb_log_excerpt(needle=SOURCE_NAME),
            "path_state": {
                "download_dir": _build_path_state(DOWNLOAD_DIR),
                "source_path": _build_path_state(SOURCE_PATH),
                "archive_dir": _build_path_state(ARCHIVE_DIR),
            },
        }
        EVIDENCE_PATH.write_text(json.dumps(failure_evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(EVIDENCE_PATH)
        raise


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
