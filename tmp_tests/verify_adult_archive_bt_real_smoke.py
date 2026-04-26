from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import threading
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from app.clients.transmission import TransmissionClient, TransmissionImportSource
from app.config import AdultArchiveDestination
from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.db.download_monitor_repo import DownloadMonitorRecord
from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.adult_archive_service import AdultArchiveService
from app.services.post_download_auto_import import PostDownloadAutoImportService


TR_BASE_URL = "http://127.0.0.1:19092"
SMOKE_ROOT = Path("/tmp/luminarr_adult_archive_bt_real_smoke")
ARCHIVE_DIR = SMOKE_ROOT / "archive" / "censored"
WEBSEED_ROOT = SMOKE_ROOT / "webseed"
SOURCE_NAME = "SSIS-456-smoke.mp4"
WEBSEED_FILE_PATH = WEBSEED_ROOT / SOURCE_NAME
HOST_DOWNLOAD_DIR = Path("/data/downloads/tr-bt")
DISPATCH_DOWNLOAD_DIR = "/downloads/complete"
SOURCE_PATH = HOST_DOWNLOAD_DIR / SOURCE_NAME
TORRENT_PATH = SMOKE_ROOT / "SSIS-456-smoke.torrent"
DB_PATH = SMOKE_ROOT / "state.sqlite3"
EVIDENCE_PATH = SMOKE_ROOT / "evidence.json"
SOURCE_BYTES = b"luminarr adult archive bt transmission real smoke\n"
CONTENT_ID = "censored:ssis-456"
DISPLAY_ID = "SSIS-456"
SOURCE_SITE = "javbus"
CHAT_ID = 1001
USER_ID = 2001


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
    info = {
        "length": len(file_bytes),
        "name": file_name,
        "piece length": 16384,
        "pieces": hashlib.sha1(file_bytes).digest(),
    }
    info_bytes = _bencode(info)
    payload: dict[str, object] = {
        "announce": "http://tracker.invalid/announce",
        "created by": "luminarr adult archive bt smoke",
        "creation date": int(datetime.now(UTC).timestamp()),
        "info": info,
    }
    if webseed_urls:
        payload["url-list"] = webseed_urls
    return _bencode(payload), hashlib.sha1(info_bytes).hexdigest()


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
            raise RuntimeError("server not started")
        return int(self._server.server_port)


def _resolve_torrent_url(*, port: int) -> str:
    return f"http://172.17.0.1:{port}/{TORRENT_PATH.name}"


def _build_completed_record(*, task_id: str, task_hash: str, name: str, completion_observed_at: str) -> DownloadMonitorRecord:
    return DownloadMonitorRecord(
        task_id=task_id,
        task_hash=task_hash,
        name=name,
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


async def _wait_until_finished(client: TransmissionClient, task_ref: str) -> tuple[str, str, str]:
    last_seen: tuple[str, str, str] | None = None
    for _ in range(40):
        status = await client.get_torrent_status(task_ref)
        if status is not None:
            last_seen = (status.task_id, status.task_hash, status.name)
            if status.percent_done >= 1.0 or status.status_code == 6:
                return status.task_id, status.task_hash, status.name
        await asyncio.sleep(0.5)
    raise RuntimeError(f"bt transmission task did not finish: {last_seen!r}")


async def _transmission_rpc(method: str, arguments: dict[str, Any]) -> dict[str, Any]:
    session_id = ""
    payload = {"method": method, "arguments": arguments}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for _ in range(2):
            headers: dict[str, str] = {}
            if session_id:
                headers["X-Transmission-Session-Id"] = session_id
            response = await client.post(
                f"{TR_BASE_URL}/transmission/rpc",
                json=payload,
                headers=headers,
            )
            if response.status_code == 409:
                session_id = response.headers.get("X-Transmission-Session-Id", "").strip()
                continue
            response.raise_for_status()
            return response.json()
    raise RuntimeError(f"transmission rpc failed: {method}")


async def _capture_session_snapshot() -> dict[str, Any]:
    payload = await _transmission_rpc("session-get", {})
    arguments = payload.get("arguments")
    if not isinstance(arguments, dict):
        return {"error": "session-get missing arguments"}
    return {
        "download_dir": str(arguments.get("download-dir", "")).strip(),
        "incomplete_dir": str(arguments.get("incomplete-dir", "")).strip(),
        "incomplete_dir_enabled": bool(arguments.get("incomplete-dir-enabled")),
        "download_queue_enabled": bool(arguments.get("download-queue-enabled")),
        "download_queue_size": arguments.get("download-queue-size"),
        "start_added_torrents": bool(arguments.get("start-added-torrents")),
    }


async def main() -> int:
    import shutil

    shutil.rmtree(SMOKE_ROOT, ignore_errors=True)
    SMOKE_ROOT.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    WEBSEED_ROOT.mkdir(parents=True, exist_ok=True)
    WEBSEED_FILE_PATH.write_bytes(SOURCE_BYTES)
    info_hash = ""
    torrent_url = ""
    webseed_urls: tuple[str, ...] = ()
    last_status_snapshot: dict[str, Any] | None = None
    last_import_source_snapshot: dict[str, Any] | None = None
    session_snapshot: dict[str, Any] | None = None

    try:
        HOST_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        SOURCE_PATH.write_bytes(SOURCE_BYTES)
        session_snapshot = await _capture_session_snapshot()
        with _StaticFileServer(SMOKE_ROOT) as static_server:
            torrent_bytes, info_hash = _build_single_file_torrent_bytes(
                file_name=SOURCE_NAME,
                file_bytes=SOURCE_BYTES,
                webseed_urls=(),
            )
            TORRENT_PATH.write_bytes(torrent_bytes)
            torrent_url = _resolve_torrent_url(port=static_server.port)

            client = TransmissionClient(TR_BASE_URL)
            try:
                await client.remove_torrent(info_hash, delete_local_data=True)
            except Exception:
                pass
            task = await client.add_torrent(torrent_url, DISPATCH_DOWNLOAD_DIR)
            await _transmission_rpc("torrent-verify", {"ids": [task.task_hash]})
            task_id, task_hash, task_name = await _wait_until_finished(client, task.task_hash)

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
                task_ref=task_hash,
                task_id=task_id,
                task_hash=task_hash,
                downloader_name="tr-bt",
            )

            async def _get_import_source(task_ref: str, _chat_id: int | None = None, _user_id: int | None = None):
                import_source = await client.get_torrent_import_source(task_ref)
                if import_source is None:
                    return None
                return TransmissionImportSource(
                    task_id=import_source.task_id,
                    task_hash=import_source.task_hash,
                    name=import_source.name,
                    download_dir=str(HOST_DOWNLOAD_DIR),
                    is_finished=import_source.is_finished,
                    percent_done=import_source.percent_done,
                )

            async def _remove_torrent(task_ref: str, _chat_id: int | None = None, delete_local_data: bool = True):
                await client.remove_torrent(task_ref, delete_local_data=delete_local_data)

            archive_service = AdultArchiveService(
                get_import_source_func=_get_import_source,
                remove_torrent_func=_remove_torrent,
                registry_repo=registry_repo,
                job_event_repo=event_repo,
                archive_destinations=(
                    AdultArchiveDestination(category="censored", label="有码", target_dir=str(ARCHIVE_DIR)),
                ),
                retention_hours=1,
            )
            auto_import_called = False

            async def _unexpected_auto_import(*_args: object) -> str:
                nonlocal auto_import_called
                auto_import_called = True
                raise RuntimeError("bt transmission adult archive smoke should not enter normal auto-import")

            auto_import_service = PostDownloadAutoImportService(
                download_monitor_repo=None,
                job_event_repo=event_repo,
                auto_import_func=_unexpected_auto_import,
                adult_content_registry_repo=registry_repo,
                adult_archive_service=archive_service,
            )

            archive_reply = await auto_import_service.run_for_record(
                _build_completed_record(
                    task_id=task_id,
                    task_hash=task_hash,
                    name=task_name,
                    completion_observed_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
            archive_target = ARCHIVE_DIR / task_name
            archived_record = registry_repo.get_by_content_id(normalized_content_id=CONTENT_ID)
            if archive_reply is None or archived_record is None or not archive_target.exists():
                raise RuntimeError("adult archive phase did not finish as expected")
            if archived_record.current_status != "archived_present":
                raise RuntimeError(f"adult archive status unexpected after archive: {archived_record.current_status}")

            cleanup_reply = await auto_import_service.run_for_record(
                _build_completed_record(
                    task_id=task_id,
                    task_hash=task_hash,
                    name=task_name,
                    completion_observed_at="2000-01-01 00:00:00",
                )
            )
            cleaned_record = registry_repo.get_by_content_id(normalized_content_id=CONTENT_ID)
            if cleanup_reply is None or cleaned_record is None:
                raise RuntimeError("adult archive cleanup phase did not finish as expected")
            if cleaned_record.current_status != "archived_deleted":
                raise RuntimeError(f"adult archive status unexpected after cleanup: {cleaned_record.current_status}")
            if auto_import_called:
                raise RuntimeError("adult archive smoke unexpectedly entered normal auto-import")
            if await client.get_torrent_status(task_hash) is not None:
                raise RuntimeError("transmission task still present after retention cleanup")

            events = event_repo.list_events_for_task_identity(task_id=task_id, task_hash=task_hash)
            evidence = {
                "status": "passed",
                "transmission_base_url": TR_BASE_URL,
                "dispatch_download_dir": DISPATCH_DOWNLOAD_DIR,
                "host_download_dir": str(HOST_DOWNLOAD_DIR),
                "session_snapshot": session_snapshot,
                "torrent_url": torrent_url,
                "webseed_urls": webseed_urls,
                "task_id": task_id,
                "task_hash": task_hash,
                "archive_reply": archive_reply,
                "cleanup_reply": cleanup_reply,
                "archive_target": str(archive_target),
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
        try:
            status = await TransmissionClient(TR_BASE_URL).get_torrent_status(info_hash)
            if status is not None:
                last_status_snapshot = {
                    "task_id": status.task_id,
                    "task_hash": status.task_hash,
                    "name": status.name,
                    "status_code": status.status_code,
                    "percent_done": status.percent_done,
                    "rate_download": status.rate_download,
                    "eta_seconds": status.eta_seconds,
                }
        except Exception as snapshot_error:
            last_status_snapshot = {"error": str(snapshot_error)}
        try:
            import_source = await TransmissionClient(TR_BASE_URL).get_torrent_import_source(info_hash)
            if import_source is not None:
                last_import_source_snapshot = {
                    "task_id": import_source.task_id,
                    "task_hash": import_source.task_hash,
                    "name": import_source.name,
                    "download_dir": import_source.download_dir,
                    "is_finished": import_source.is_finished,
                    "percent_done": import_source.percent_done,
                }
        except Exception as snapshot_error:
            last_import_source_snapshot = {"error": str(snapshot_error)}
        if session_snapshot is None:
            try:
                session_snapshot = await _capture_session_snapshot()
            except Exception as snapshot_error:
                session_snapshot = {"error": str(snapshot_error)}
        evidence = {
            "status": "failed",
            "error": str(error),
            "transmission_base_url": TR_BASE_URL,
            "dispatch_download_dir": DISPATCH_DOWNLOAD_DIR,
            "host_download_dir": str(HOST_DOWNLOAD_DIR),
            "session_snapshot": session_snapshot,
            "torrent_url": torrent_url,
            "webseed_urls": webseed_urls,
            "info_hash": info_hash,
            "source_path_exists": SOURCE_PATH.exists(),
            "download_dir_exists": HOST_DOWNLOAD_DIR.exists(),
            "last_status_snapshot": last_status_snapshot,
            "last_import_source_snapshot": last_import_source_snapshot,
        }
        EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(EVIDENCE_PATH)
        raise


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
