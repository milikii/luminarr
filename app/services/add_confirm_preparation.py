from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.services.add_confirm_context_state import ConfirmExecutionContext
from app.services.add_pending_context import PendingAddContext

BuildJobLeaseOwnerFunc = Callable[[str], str]
ClaimPendingJobFunc = Callable[..., bool | None]
FindVersionStaleRejectionTextFunc = Callable[..., str | None]
RecordDownloaderApprovalFunc = Callable[..., bool | None]
ResolvePendingLeaseVersionFunc = Callable[..., int]
RestorePendingJobFunc = Callable[..., None]


@dataclass(frozen=True, slots=True)
class ConfirmPreparationState:
    pending_add: PendingAddContext
    expected_lease_version: int
    claimed_job: bool
    claimed_job_id: str
    claimed_job_version: int
    lease_owner: str


class AddConfirmPreparation:
    def __init__(
        self,
        *,
        pending_lease_lookup_failed: int,
        add_confirm_not_pending_text: str,
        add_confirm_state_unavailable_text: str,
    ) -> None:
        self._pending_lease_lookup_failed = pending_lease_lookup_failed
        self._add_confirm_not_pending_text = add_confirm_not_pending_text
        self._add_confirm_state_unavailable_text = add_confirm_state_unavailable_text

    def prepare(
        self,
        *,
        task_ref: str,
        confirm_context: ConfirmExecutionContext | None,
        in_memory_pending: PendingAddContext | None,
        build_job_lease_owner: BuildJobLeaseOwnerFunc,
        claim_pending_job: ClaimPendingJobFunc,
        restore_pending_job: RestorePendingJobFunc,
        find_version_stale_rejection_text: FindVersionStaleRejectionTextFunc,
        resolve_pending_lease_version: ResolvePendingLeaseVersionFunc,
        record_downloader_approval: RecordDownloaderApprovalFunc,
    ) -> tuple[ConfirmPreparationState | None, str | None]:
        claimed_job = False
        claimed_job_id = ""
        claimed_job_version = 0
        lease_owner = ""
        pending_add = confirm_context.pending_add if confirm_context is not None else in_memory_pending
        assert pending_add is not None

        if confirm_context is not None:
            lease_owner = build_job_lease_owner(task_ref)
            claimed_job = claim_pending_job(job=confirm_context.job, lease_owner=lease_owner)
            if claimed_job is None:
                return None, self._add_confirm_state_unavailable_text
            if not claimed_job:
                stale_text = find_version_stale_rejection_text(
                    task_id=pending_add.task_id,
                    task_hash=pending_add.task_hash,
                )
                return None, stale_text or self._add_confirm_not_pending_text
            claimed_job_id = confirm_context.job.job_id
            claimed_job_version = confirm_context.job.version

        stale_text = find_version_stale_rejection_text(
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
        )
        if stale_text is not None:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
                restore_pending_job=restore_pending_job,
            )
            return None, stale_text

        expected_lease_version = 0
        if confirm_context is not None and confirm_context.approval_record is not None:
            expected_lease_version = max(0, confirm_context.approval_record.lease_version)
        if expected_lease_version <= 0:
            expected_lease_version = resolve_pending_lease_version(
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                allow_in_memory_fallback_on_error=False,
            )
        if expected_lease_version == self._pending_lease_lookup_failed:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
                restore_pending_job=restore_pending_job,
            )
            return None, self._add_confirm_state_unavailable_text
        if expected_lease_version <= 0:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
                restore_pending_job=restore_pending_job,
            )
            return None, self._add_confirm_not_pending_text

        approved = record_downloader_approval(
            task_ref=task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            expected_lease_version=expected_lease_version,
        )
        if approved is None:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
                restore_pending_job=restore_pending_job,
            )
            return None, self._add_confirm_state_unavailable_text
        if not approved:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
                restore_pending_job=restore_pending_job,
            )
            stale_text = find_version_stale_rejection_text(
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
            )
            return None, stale_text or self._add_confirm_not_pending_text

        return (
            ConfirmPreparationState(
                pending_add=pending_add,
                expected_lease_version=expected_lease_version,
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
            ),
            None,
        )

    def _restore_claim_if_needed(
        self,
        *,
        claimed_job: bool,
        claimed_job_id: str,
        claimed_job_version: int,
        lease_owner: str,
        restore_pending_job: RestorePendingJobFunc,
    ) -> None:
        if not claimed_job:
            return
        restore_pending_job(
            job_id=claimed_job_id,
            expected_version=claimed_job_version,
            lease_owner=lease_owner,
        )
