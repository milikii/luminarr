from __future__ import annotations

from pathlib import Path

from app.services.adult_duplicate_memory import AdultDuplicateMemoryService


class _FakeSnapshotRepo:
    def __init__(self) -> None:
        self._rows: dict[str, object] = {}

    def get_snapshot(self, normalized_content_id: str):
        return self._rows.get(normalized_content_id)

    def upsert_snapshot(
        self,
        *,
        normalized_content_id: str,
        display_title: str,
        snapshot_status: str,
        evidence_summary_json: str,
        last_verified_at: str,
        last_scan_failed_at: str,
    ):
        row = type(
            "SnapshotRow",
            (),
            {
                "normalized_content_id": normalized_content_id,
                "display_title": display_title,
                "snapshot_status": snapshot_status,
                "evidence_summary_json": evidence_summary_json,
                "last_verified_at": last_verified_at,
                "last_scan_failed_at": last_scan_failed_at,
                "created_at": "",
                "updated_at": "",
            },
        )()
        self._rows[normalized_content_id] = row
        return row


class _FakeAdultRegistryRepo:
    def __init__(self, *, status: str, task_id: str = "123", task_hash: str = "hash-123") -> None:
        self._status = status
        self._task_id = task_id
        self._task_hash = task_hash

    def get_by_content_id(self, *, normalized_content_id: str):
        if normalized_content_id != "censored:ssis-123":
            return None
        return type(
            "RegistryRow",
            (),
            {
                "current_status": self._status,
                "current_task_id": self._task_id,
                "current_task_hash": self._task_hash,
            },
        )()


class _FakeJobEventRepo:
    def __init__(self, *, task_ref: str) -> None:
        self._task_ref = task_ref

    def list_events_for_task_identity(self, *, task_id: str, task_hash: str):
        assert task_id == "123"
        assert task_hash == "hash-123"
        return [
            type(
                "EventRow",
                (),
                {
                    "event_type": "downloader.succeeded",
                    "task_ref": self._task_ref,
                },
            )()
        ]


def test_adult_duplicate_memory_service_prefers_exact_id_evidence(tmp_path: Path) -> None:
    adult_dir = tmp_path / "adult"
    adult_dir.mkdir()
    (adult_dir / "SSIS-123 sample.mp4").write_text("video", encoding="utf-8")

    service = AdultDuplicateMemoryService(
        snapshot_repo=_FakeSnapshotRepo(),
        adult_content_registry_repo=_FakeAdultRegistryRepo(status="archived_present"),
        job_event_repo=_FakeJobEventRepo(task_ref="bt-1"),
        adult_scan_dirs=(adult_dir,),
    )

    decision = service.inspect(
        normalized_content_id="censored:ssis-123",
        display_title="SSIS-123",
    )

    assert decision.should_warn is True
    assert decision.snapshot_status == "fresh"
    assert decision.evidence[0].kind == "local_path"
    assert "SSIS-123 sample.mp4" in decision.evidence[0].summary
    assert any(item.kind == "registry" for item in decision.evidence)
    assert any(item.kind == "job_event" for item in decision.evidence)


def test_adult_duplicate_memory_service_reuses_fresh_snapshot_without_rescan(tmp_path: Path) -> None:
    adult_dir = tmp_path / "adult"
    adult_dir.mkdir()
    snapshot_repo = _FakeSnapshotRepo()
    snapshot_repo.upsert_snapshot(
        normalized_content_id="censored:ssis-123",
        display_title="SSIS-123",
        snapshot_status="fresh",
        evidence_summary_json=(
            '{"degraded": false, "warning_text": "检测到该番号已有本地或历史命中；如需继续，请显式确认继续下载。", '
            '"evidence": [{"kind": "local_path", "summary": "本地命中：/archive/SSIS-123.mp4", "raw_value": "/archive/SSIS-123.mp4"}]}'
        ),
        last_verified_at="CURRENT",
        last_scan_failed_at="",
    )

    service = AdultDuplicateMemoryService(
        snapshot_repo=snapshot_repo,
        adult_content_registry_repo=None,
        job_event_repo=None,
        adult_scan_dirs=(adult_dir / "missing",),
    )

    decision = service.inspect(
        normalized_content_id="censored:ssis-123",
        display_title="SSIS-123",
    )

    assert decision.should_warn is True
    assert decision.degraded is False
    assert decision.evidence == (
        type(decision.evidence[0])(
            kind="local_path",
            summary="本地命中：/archive/SSIS-123.mp4",
            raw_value="/archive/SSIS-123.mp4",
        ),
    )


def test_adult_duplicate_memory_service_ignores_title_only_non_exact_local_matches(tmp_path: Path) -> None:
    adult_dir = tmp_path / "adult"
    adult_dir.mkdir()
    (adult_dir / "Secret Mission Nurse complete edition.mp4").write_text("video", encoding="utf-8")

    service = AdultDuplicateMemoryService(
        snapshot_repo=_FakeSnapshotRepo(),
        adult_content_registry_repo=None,
        job_event_repo=None,
        adult_scan_dirs=(adult_dir,),
    )

    decision = service.inspect(
        normalized_content_id="censored:ssis-123",
        display_title="SSIS-123",
    )

    assert decision.should_warn is False
    assert decision.snapshot_status == "fresh"
    assert decision.evidence == ()


def test_adult_duplicate_memory_service_marks_decision_degraded_when_scan_dir_missing(tmp_path: Path) -> None:
    service = AdultDuplicateMemoryService(
        snapshot_repo=_FakeSnapshotRepo(),
        adult_content_registry_repo=None,
        job_event_repo=None,
        adult_scan_dirs=(tmp_path / "missing",),
    )

    decision = service.inspect(
        normalized_content_id="censored:ssis-123",
        display_title="SSIS-123",
    )

    assert decision.should_warn is True
    assert decision.degraded is True
    assert decision.snapshot_status == "scan_failed"
    assert decision.warning_text == "重复检查不完整；如需继续，请显式确认继续下载。"
