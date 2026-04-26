from __future__ import annotations

import asyncio
import base64
import re
from pathlib import Path
from typing import Any

import httpx

from app.clients.transmission import TransmissionImportSource, TransmissionTask, TransmissionTaskStatus


class QbittorrentError(RuntimeError):
    """Raised when qBittorrent Web API returns an error."""


class QbittorrentClient:
    def __init__(
        self,
        base_url: str,
        username: str = "",
        password: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        cleaned_base = base_url.rstrip("/")
        if cleaned_base.endswith("/api/v2"):
            self._api_base = cleaned_base
        else:
            self._api_base = f"{cleaned_base}/api/v2"
        self._username = username.strip()
        self._password = password
        self._timeout_seconds = timeout_seconds

    async def add_torrent(self, source: str, download_dir: str = "") -> TransmissionTask:
        cleaned_source = source.strip()
        if not cleaned_source:
            raise QbittorrentError("missing torrent source")

        async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=True) as client:
            await self._login(client)
            before_torrents = await self._list_torrents(client)
            before_hashes = {torrent_hash for torrent_hash, _ in before_torrents}
            await self._add_torrent_request(client, cleaned_source, download_dir=download_dir)

            resolved_hash = await self._resolve_added_hash(
                client,
                source=cleaned_source,
                before_hashes=before_hashes,
            )

        return TransmissionTask(task_id=resolved_hash, task_hash=resolved_hash)

    async def get_torrent_status(self, task_ref: str) -> TransmissionTaskStatus | None:
        cleaned_ref = task_ref.strip().lower()
        if not cleaned_ref:
            return None

        async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=True) as client:
            await self._login(client)
            torrent = await self._get_torrent_by_hash(client, cleaned_ref)
        if torrent is None:
            return None

        torrent_hash = str(torrent.get("hash", "")).strip().lower()
        if not torrent_hash:
            return None

        return TransmissionTaskStatus(
            task_id=torrent_hash,
            task_hash=torrent_hash,
            name=str(torrent.get("name", "")).strip() or "(no title)",
            status_code=_map_qb_state_to_status_code(str(torrent.get("state", "")).strip()),
            percent_done=_safe_float(torrent.get("progress")),
            rate_download=_safe_int(torrent.get("dlspeed")),
            eta_seconds=_safe_int(torrent.get("eta")),
        )

    async def get_torrent_import_source(self, task_ref: str) -> TransmissionImportSource | None:
        cleaned_ref = task_ref.strip().lower()
        if not cleaned_ref:
            return None

        async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=True) as client:
            await self._login(client)
            torrent = await self._get_torrent_by_hash(client, cleaned_ref)
        if torrent is None:
            return None

        torrent_hash = str(torrent.get("hash", "")).strip().lower()
        if not torrent_hash:
            return None

        resolved_name = str(torrent.get("name", "")).strip() or "(no title)"
        download_dir = _resolve_import_download_dir(
            save_path=str(torrent.get("save_path", "")).strip(),
            content_path=str(torrent.get("content_path", "")).strip(),
            torrent_name=resolved_name,
        )
        if not download_dir:
            raise QbittorrentError("missing download directory in qBittorrent response")

        progress = _safe_float(torrent.get("progress"))
        return TransmissionImportSource(
            task_id=torrent_hash,
            task_hash=torrent_hash,
            name=resolved_name,
            download_dir=download_dir,
            is_finished=_is_finished_state(str(torrent.get("state", "")).strip(), progress=progress),
            percent_done=progress,
        )

    async def remove_torrent(self, task_ref: str, *, delete_local_data: bool = True) -> None:
        cleaned_ref = task_ref.strip().lower()
        if not cleaned_ref:
            raise QbittorrentError("missing task ref for remove")
        async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=True) as client:
            await self._login(client)
            response = await client.post(
                f"{self._api_base}/torrents/delete",
                data={
                    "hashes": cleaned_ref,
                    "deleteFiles": "true" if delete_local_data else "false",
                },
            )
        response.raise_for_status()

    async def _login(self, client: httpx.AsyncClient) -> None:
        if not self._username:
            return
        response = await client.post(
            f"{self._api_base}/auth/login",
            data={
                "username": self._username,
                "password": self._password,
            },
        )
        response.raise_for_status()
        if response.text.strip() != "Ok.":
            raise QbittorrentError("qBittorrent login failed")

    async def _add_torrent_request(
        self,
        client: httpx.AsyncClient,
        source: str,
        *,
        download_dir: str,
    ) -> None:
        payload: dict[str, Any] = {}
        if source.lower().startswith("magnet:?") or re.match(r"^https?://", source, flags=re.IGNORECASE):
            payload["urls"] = source
        else:
            raise QbittorrentError("qBittorrent add currently supports only magnet or URL source")
        cleaned_download_dir = download_dir.strip()
        if cleaned_download_dir:
            payload["savepath"] = cleaned_download_dir

        response = await client.post(f"{self._api_base}/torrents/add", data=payload)
        response.raise_for_status()
        if response.text.strip() not in {"Ok.", "Fails."}:
            raise QbittorrentError("unexpected qBittorrent add response")
        if response.text.strip() == "Fails.":
            raise QbittorrentError("qBittorrent add failed")

    async def _resolve_added_hash(
        self,
        client: httpx.AsyncClient,
        *,
        source: str,
        before_hashes: set[str],
    ) -> str:
        parsed_hash = _parse_info_hash_from_source(source)
        if parsed_hash:
            parsed_hash = parsed_hash.lower()

        for _ in range(5):
            after_torrents = await self._list_torrents(client)
            if parsed_hash and any(torrent_hash == parsed_hash for torrent_hash, _ in after_torrents):
                return parsed_hash
            new_hashes = [torrent_hash for torrent_hash, _ in after_torrents if torrent_hash not in before_hashes]
            if new_hashes:
                return new_hashes[0]
            await asyncio.sleep(0.2)

        if parsed_hash:
            return parsed_hash
        raise QbittorrentError("unable to resolve qBittorrent task hash after add")

    async def _get_torrent_by_hash(
        self,
        client: httpx.AsyncClient,
        torrent_hash: str,
    ) -> dict[str, Any] | None:
        response = await client.get(
            f"{self._api_base}/torrents/info",
            params={"hashes": torrent_hash},
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or not data:
            return None
        torrent = data[0]
        if not isinstance(torrent, dict):
            raise QbittorrentError("invalid qBittorrent torrent info response")
        return torrent

    async def _list_torrents(self, client: httpx.AsyncClient) -> list[tuple[str, int]]:
        response = await client.get(f"{self._api_base}/torrents/info")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise QbittorrentError("invalid qBittorrent torrent list response")

        resolved: list[tuple[str, int]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            torrent_hash = str(item.get("hash", "")).strip().lower()
            if not torrent_hash:
                continue
            added_on = _safe_int(item.get("added_on"))
            resolved.append((torrent_hash, added_on))
        resolved.sort(key=lambda item: item[1], reverse=True)
        return resolved


def _parse_info_hash_from_source(source: str) -> str:
    matched = re.search(r"btih:([A-Za-z2-7]{32}|[A-Fa-f0-9]{40})", source)
    if matched is None:
        return ""
    raw_hash = matched.group(1).strip()
    if len(raw_hash) == 32:
        try:
            decoded = base64.b32decode(raw_hash.upper())
        except (ValueError, base64.binascii.Error):
            return ""
        return decoded.hex()
    return raw_hash.lower()


def _resolve_import_download_dir(*, save_path: str, content_path: str, torrent_name: str) -> str:
    cleaned_content_path = content_path.strip()
    if cleaned_content_path:
        content_candidate = Path(cleaned_content_path)
        if content_candidate.name == torrent_name.strip():
            return str(content_candidate.parent)
        return str(content_candidate)
    return save_path.strip()


def _map_qb_state_to_status_code(state: str) -> int:
    normalized = state.strip().lower()
    if normalized in {"checkingup", "checkingdl", "checkingresumedata"}:
        return 2
    if normalized in {"queueddl", "metadl", "forcedmetadl"}:
        return 3
    if normalized in {"downloading", "forceddl", "stalleddl"}:
        return 4
    if normalized in {"queuedup"}:
        return 5
    if normalized in {"uploading", "forcedup", "stalledup"}:
        return 6
    return 0


def _is_finished_state(state: str, *, progress: float) -> bool:
    if progress >= 1.0:
        return True
    normalized = state.strip().lower()
    return normalized in {"uploading", "forcedup", "stalledup", "pausedup", "queuedup"}


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
