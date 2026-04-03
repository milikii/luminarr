from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class TransmissionError(RuntimeError):
    """Raised when Transmission RPC returns an error."""


@dataclass(frozen=True, slots=True)
class TransmissionTask:
    task_id: str
    task_hash: str


@dataclass(frozen=True, slots=True)
class TransmissionTaskStatus:
    task_id: str
    task_hash: str
    name: str
    status_code: int
    percent_done: float
    rate_download: int
    eta_seconds: int


@dataclass(frozen=True, slots=True)
class TransmissionImportSource:
    task_id: str
    task_hash: str
    name: str
    download_dir: str
    is_finished: bool
    percent_done: float


class TransmissionClient:
    def __init__(
        self,
        base_url: str,
        username: str = "",
        password: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        cleaned_base = base_url.rstrip("/")
        if cleaned_base.endswith("/transmission/rpc"):
            self._rpc_url = cleaned_base
        else:
            self._rpc_url = f"{cleaned_base}/transmission/rpc"
        self._timeout_seconds = timeout_seconds
        self._session_id = ""
        self._auth = (username, password) if username else None

    async def add_torrent(self, source: str, download_dir: str = "") -> TransmissionTask:
        arguments: dict[str, Any] = {"filename": source}
        cleaned_download_dir = download_dir.strip()
        if cleaned_download_dir:
            arguments["download-dir"] = cleaned_download_dir
        payload = await self._rpc("torrent-add", arguments)
        arguments = payload.get("arguments")
        if not isinstance(arguments, dict):
            raise TransmissionError("missing arguments in response")

        task_data = arguments.get("torrent-added")
        if not isinstance(task_data, dict):
            task_data = arguments.get("torrent-duplicate")
        if not isinstance(task_data, dict):
            raise TransmissionError("missing torrent task in response")

        task_id = str(task_data.get("id", "")).strip()
        task_hash = str(task_data.get("hashString", "")).strip()
        if not task_id or not task_hash:
            raise TransmissionError("missing task id/hash in response")
        return TransmissionTask(task_id=task_id, task_hash=task_hash)

    async def get_torrent_status(self, task_ref: str) -> TransmissionTaskStatus | None:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return None

        lookup_id: str | int
        if cleaned_ref.isdigit():
            lookup_id = int(cleaned_ref)
        else:
            lookup_id = cleaned_ref

        payload = await self._rpc(
            "torrent-get",
            {
                "fields": [
                    "id",
                    "hashString",
                    "name",
                    "status",
                    "percentDone",
                    "rateDownload",
                    "eta",
                ],
                "ids": [lookup_id],
            },
        )
        arguments = payload.get("arguments")
        if not isinstance(arguments, dict):
            raise TransmissionError("missing arguments in response")

        torrents = arguments.get("torrents")
        if not isinstance(torrents, list):
            raise TransmissionError("missing torrents in response")
        if not torrents:
            return None

        task_data = torrents[0]
        if not isinstance(task_data, dict):
            raise TransmissionError("invalid torrent data in response")

        task_id = str(task_data.get("id", "")).strip()
        task_hash = str(task_data.get("hashString", "")).strip()
        if not task_id or not task_hash:
            raise TransmissionError("missing task id/hash in status response")

        return TransmissionTaskStatus(
            task_id=task_id,
            task_hash=task_hash,
            name=str(task_data.get("name", "")).strip() or "(no title)",
            status_code=_safe_int(task_data.get("status")),
            percent_done=_safe_float(task_data.get("percentDone")),
            rate_download=_safe_int(task_data.get("rateDownload")),
            eta_seconds=_safe_int(task_data.get("eta")),
        )

    async def get_torrent_import_source(self, task_ref: str) -> TransmissionImportSource | None:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return None

        lookup_id: str | int
        if cleaned_ref.isdigit():
            lookup_id = int(cleaned_ref)
        else:
            lookup_id = cleaned_ref

        payload = await self._rpc(
            "torrent-get",
            {
                "fields": [
                    "id",
                    "hashString",
                    "name",
                    "downloadDir",
                    "isFinished",
                    "percentDone",
                ],
                "ids": [lookup_id],
            },
        )
        arguments = payload.get("arguments")
        if not isinstance(arguments, dict):
            raise TransmissionError("missing arguments in response")

        torrents = arguments.get("torrents")
        if not isinstance(torrents, list):
            raise TransmissionError("missing torrents in response")
        if not torrents:
            return None

        task_data = torrents[0]
        if not isinstance(task_data, dict):
            raise TransmissionError("invalid torrent data in response")

        task_id = str(task_data.get("id", "")).strip()
        task_hash = str(task_data.get("hashString", "")).strip()
        if not task_id or not task_hash:
            raise TransmissionError("missing task id/hash in status response")

        download_dir = str(task_data.get("downloadDir", "")).strip()
        if not download_dir:
            raise TransmissionError("missing download directory in status response")

        is_finished = bool(task_data.get("isFinished"))
        percent_done = _safe_float(task_data.get("percentDone"))
        return TransmissionImportSource(
            task_id=task_id,
            task_hash=task_hash,
            name=str(task_data.get("name", "")).strip() or "(no title)",
            download_dir=download_dir,
            is_finished=is_finished,
            percent_done=percent_done,
        )

    async def _rpc(self, method: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {"method": method, "arguments": arguments}
        for _ in range(2):
            headers: dict[str, str] = {}
            if self._session_id:
                headers["X-Transmission-Session-Id"] = self._session_id

            async with httpx.AsyncClient(timeout=self._timeout_seconds, auth=self._auth) as client:
                response = await client.post(self._rpc_url, json=payload, headers=headers)

            if response.status_code == 409:
                self._session_id = response.headers.get("X-Transmission-Session-Id", "").strip()
                if self._session_id:
                    continue
                raise TransmissionError("failed to get transmission session id")

            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise TransmissionError("invalid rpc response")

            result = data.get("result")
            if result != "success":
                raise TransmissionError(f"rpc failed: {result}")
            return data

        raise TransmissionError("rpc failed after session retry")


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
