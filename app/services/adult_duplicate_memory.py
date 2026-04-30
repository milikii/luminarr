from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.db.adult_content_registry_repo import AdultContentRegistryPersistenceError, AdultContentRegistryRepo
from app.db.adult_duplicate_memory_snapshot_repo import (
    AdultDuplicateMemorySnapshotPersistenceError,
    AdultDuplicateMemorySnapshotRecord,
    AdultDuplicateMemorySnapshotRepo,
)
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.services.adult_content import extract_exact_adult_content_match

_DUPLICATE_WARNING_TEXT = "检测到该番号已有本地或历史命中；如需继续，请显式确认继续下载。"
_DUPLICATE_DEGRADED_WARNING_TEXT = "重复检查不完整；如需继续，请显式确认继续下载。"


@dataclass(frozen=True, slots=True)
class DuplicateEvidence:
    kind: str
    summary: str
    raw_value: str


@dataclass(frozen=True, slots=True)
class AdultDuplicateDecision:
    normalized_content_id: str
    display_title: str
    snapshot_status: str
    should_warn: bool
    degraded: bool
    warning_text: str
    evidence: tuple[DuplicateEvidence, ...]


class AdultDuplicateMemoryService:
    def __init__(
        self,
        *,
        snapshot_repo: AdultDuplicateMemorySnapshotRepo,
        adult_content_registry_repo: AdultContentRegistryRepo | None,
        job_event_repo: JobEventRepo | None,
        adult_scan_dirs: Sequence[Path],
    ) -> None:
        self._snapshot_repo = snapshot_repo
        self._adult_content_registry_repo = adult_content_registry_repo
        self._job_event_repo = job_event_repo
        self._adult_scan_dirs = tuple(Path(path).expanduser() for path in adult_scan_dirs)

    def inspect(self, *, normalized_content_id: str, display_title: str) -> AdultDuplicateDecision:
        cleaned_content_id = normalized_content_id.strip().lower()
        cleaned_display_title = display_title.strip()
        snapshot = self._snapshot_repo.get_snapshot(cleaned_content_id)
        if snapshot is not None and snapshot.snapshot_status == "fresh":
            restored_decision = _restore_decision_from_snapshot(snapshot)
            if restored_decision is not None:
                return restored_decision

        evidence: list[DuplicateEvidence] = []
        degraded = False

        try:
            evidence.extend(self._scan_local_paths(normalized_content_id=cleaned_content_id))
        except OSError:
            degraded = True

        registry_record = None
        if self._adult_content_registry_repo is not None:
            try:
                registry_record = self._adult_content_registry_repo.get_by_content_id(
                    normalized_content_id=cleaned_content_id
                )
            except (AdultContentRegistryPersistenceError, sqlite3.Error):
                degraded = True
            else:
                if registry_record is not None:
                    evidence.append(
                        DuplicateEvidence(
                            kind="registry",
                            summary=f"历史状态：{registry_record.current_status}",
                            raw_value=registry_record.current_status,
                        )
                    )

        if self._job_event_repo is not None and registry_record is not None:
            try:
                events = self._job_event_repo.list_events_for_task_identity(
                    task_id=registry_record.current_task_id,
                    task_hash=registry_record.current_task_hash,
                )
            except (JobEventPersistenceError, sqlite3.Error):
                degraded = True
            else:
                for event in events:
                    evidence.append(
                        DuplicateEvidence(
                            kind="job_event",
                            summary=f"历史事件：{event.event_type} ({event.task_ref})",
                            raw_value=event.event_type,
                        )
                    )

        snapshot_status = "scan_failed" if degraded else "fresh"
        should_warn = bool(evidence) or degraded
        warning_text = ""
        if degraded:
            warning_text = _DUPLICATE_DEGRADED_WARNING_TEXT
        elif evidence:
            warning_text = _DUPLICATE_WARNING_TEXT

        decision = AdultDuplicateDecision(
            normalized_content_id=cleaned_content_id,
            display_title=cleaned_display_title or cleaned_content_id,
            snapshot_status=snapshot_status,
            should_warn=should_warn,
            degraded=degraded,
            warning_text=warning_text,
            evidence=tuple(evidence),
        )
        self._persist_snapshot(decision)
        return decision

    def _scan_local_paths(self, *, normalized_content_id: str) -> list[DuplicateEvidence]:
        evidence: list[DuplicateEvidence] = []
        seen_paths: set[str] = set()
        for scan_dir in self._adult_scan_dirs:
            if not scan_dir.exists():
                raise FileNotFoundError(str(scan_dir))
            for path in scan_dir.rglob("*"):
                if not path.is_file() and not path.is_dir():
                    continue
                match = extract_exact_adult_content_match(path.name)
                if match is None or match.normalized_content_id != normalized_content_id:
                    continue
                resolved = str(path)
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                evidence.append(
                    DuplicateEvidence(
                        kind="local_path",
                        summary=f"本地命中：{resolved}",
                        raw_value=resolved,
                    )
                )
        return evidence

    def _persist_snapshot(self, decision: AdultDuplicateDecision) -> None:
        evidence_summary_json = json.dumps(
            {
                "normalized_content_id": decision.normalized_content_id,
                "display_title": decision.display_title,
                "degraded": decision.degraded,
                "warning_text": decision.warning_text,
                "evidence": [
                    {
                        "kind": item.kind,
                        "summary": item.summary,
                        "raw_value": item.raw_value,
                    }
                    for item in decision.evidence
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        try:
            self._snapshot_repo.upsert_snapshot(
                normalized_content_id=decision.normalized_content_id,
                display_title=decision.display_title,
                snapshot_status=decision.snapshot_status,
                evidence_summary_json=evidence_summary_json,
                last_verified_at="CURRENT",
                last_scan_failed_at="CURRENT" if decision.degraded else "",
            )
        except AdultDuplicateMemorySnapshotPersistenceError:
            return


def _restore_decision_from_snapshot(
    snapshot: AdultDuplicateMemorySnapshotRecord,
) -> AdultDuplicateDecision | None:
    try:
        payload = json.loads(snapshot.evidence_summary_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    evidence_payload = payload.get("evidence")
    evidence: list[DuplicateEvidence] = []
    if isinstance(evidence_payload, list):
        for item in evidence_payload:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind", "")).strip()
            summary = str(item.get("summary", "")).strip()
            raw_value = str(item.get("raw_value", "")).strip()
            if not kind or not summary:
                continue
            evidence.append(DuplicateEvidence(kind=kind, summary=summary, raw_value=raw_value))

    degraded = bool(payload.get("degraded"))
    warning_text = str(payload.get("warning_text", "")).strip()
    should_warn = bool(evidence) or degraded
    return AdultDuplicateDecision(
        normalized_content_id=snapshot.normalized_content_id,
        display_title=snapshot.display_title,
        snapshot_status=snapshot.snapshot_status,
        should_warn=should_warn,
        degraded=degraded,
        warning_text=warning_text,
        evidence=tuple(evidence),
    )
