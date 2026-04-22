from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.services.import_context_lookup import ConfirmExecutionContext
from app.services.import_transfer_execution import PreparedImport

BuildJobLeaseOwnerFunc = Callable[[str], str]
ClaimPendingJobFunc = Callable[..., bool | None]
FindVersionStaleRejectionTextFunc = Callable[..., str | None]
HandleExpiredPendingConfirmFunc = Callable[..., str | None]
PrepareImportFunc = Callable[..., Awaitable[tuple[PreparedImport | None, str]]]
RebuildConfirmContextFunc = Callable[..., tuple[ConfirmExecutionContext | None, bool]]
RecordEventFunc = Callable[..., None]
RecordImportApprovalFunc = Callable[..., bool | None]
ResolveExecutionModeFunc = Callable[..., str | None]
ResolvePendingLeaseVersionFunc = Callable[..., int]
RestorePendingJobFunc = Callable[..., None]


@dataclass(frozen=True, slots=True)
class ImportConfirmPreparationState:
    prepared_import: PreparedImport
    confirm_context: ConfirmExecutionContext | None
    execution_mode: str
    expected_lease_version: int
    claimed_job: bool
    claimed_job_id: str
    claimed_job_version: int
    lease_owner: str


class ImportConfirmPreparation:
    def __init__(
        self,
        *,
        import_confirm_not_pending_text: str,
        import_confirm_state_unavailable_text: str,
        pending_lease_lookup_failed: int,
    ) -> None:
        self._import_confirm_not_pending_text = import_confirm_not_pending_text
        self._import_confirm_state_unavailable_text = import_confirm_state_unavailable_text
        self._pending_lease_lookup_failed = pending_lease_lookup_failed

    async def prepare(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
        rebuild_confirm_context: RebuildConfirmContextFunc,
        find_version_stale_rejection_text: FindVersionStaleRejectionTextFunc,
        handle_expired_pending_confirm: HandleExpiredPendingConfirmFunc,
        build_job_lease_owner: BuildJobLeaseOwnerFunc,
        claim_pending_job: ClaimPendingJobFunc,
        restore_pending_job: RestorePendingJobFunc,
        prepare_import: PrepareImportFunc,
        resolve_execution_mode: ResolveExecutionModeFunc,
        resolve_pending_lease_version: ResolvePendingLeaseVersionFunc,
        record_import_approval: RecordImportApprovalFunc,
        record_event: RecordEventFunc,
    ) -> tuple[ImportConfirmPreparationState | None, str]:
        confirm_context, confirm_context_lookup_failed = rebuild_confirm_context(
            task_ref=task_ref,
            chat_id=chat_id,
        )
        if confirm_context_lookup_failed:
            return None, self._import_confirm_state_unavailable_text
        if confirm_context is not None and confirm_context.approval_lookup_failed:
            return None, self._import_confirm_state_unavailable_text
        if confirm_context is not None and confirm_context.job.state != "pending_approval":
            rejection_text = self._resolve_not_pending_rejection_text(
                task_id=confirm_context.job.task_id,
                task_hash=confirm_context.job.task_hash,
                find_version_stale_rejection_text=find_version_stale_rejection_text,
            )
            record_event(
                task_ref=task_ref,
                task_id=confirm_context.job.task_id,
                task_hash=confirm_context.job.task_hash,
                event_type="import.confirm_not_pending",
                message=rejection_text,
            )
            return None, rejection_text

        claimed_job = False
        claimed_job_version = 0
        claimed_job_id = ""
        lease_owner = ""
        prepared_task_ref = task_ref
        if confirm_context is not None:
            approval_record = confirm_context.approval_record
            if approval_record is None or approval_record.status != "pending":
                rejection_text = self._resolve_not_pending_rejection_text(
                    task_id=confirm_context.job.task_id,
                    task_hash=confirm_context.job.task_hash,
                    find_version_stale_rejection_text=find_version_stale_rejection_text,
                )
                record_event(
                    task_ref=task_ref,
                    task_id=confirm_context.job.task_id,
                    task_hash=confirm_context.job.task_hash,
                    event_type="import.confirm_not_pending",
                    message=rejection_text,
                )
                return None, rejection_text
            expired_text = handle_expired_pending_confirm(task_ref=task_ref, context=confirm_context)
            if expired_text is not None:
                return None, expired_text
            lease_owner = build_job_lease_owner(task_ref)
            claimed_job = claim_pending_job(
                job=confirm_context.job,
                lease_owner=lease_owner,
            )
            if claimed_job is None:
                return None, self._import_confirm_state_unavailable_text
            if not claimed_job:
                rejection_text = self._resolve_not_pending_rejection_text(
                    task_id=confirm_context.job.task_id,
                    task_hash=confirm_context.job.task_hash,
                    find_version_stale_rejection_text=find_version_stale_rejection_text,
                )
                record_event(
                    task_ref=task_ref,
                    task_id=confirm_context.job.task_id,
                    task_hash=confirm_context.job.task_hash,
                    event_type="import.confirm_not_pending",
                    message=rejection_text,
                )
                return None, rejection_text
            claimed_job_id = confirm_context.job.job_id
            claimed_job_version = confirm_context.job.version
            prepared_task_ref = confirm_context.lookup_task_ref

        prepared_import, error_text = await prepare_import(prepared_task_ref, chat_id=chat_id)
        if prepared_import is None:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
                restore_pending_job=restore_pending_job,
            )
            return None, error_text

        import_source = prepared_import.import_source
        stale_text = find_version_stale_rejection_text(
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
        )
        if stale_text is not None:
            record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.stale_rejected",
                message=stale_text,
            )
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
                restore_pending_job=restore_pending_job,
            )
            return None, stale_text

        execution_mode = resolve_execution_mode(
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            confirm_context=confirm_context,
        )
        if execution_mode is None:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
                restore_pending_job=restore_pending_job,
            )
            return None, self._import_confirm_state_unavailable_text

        expected_lease_version = 0
        if confirm_context is not None and confirm_context.approval_record is not None:
            expected_lease_version = max(0, confirm_context.approval_record.lease_version)
        if expected_lease_version <= 0:
            expected_lease_version = resolve_pending_lease_version(
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
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
            return None, self._import_confirm_state_unavailable_text
        if expected_lease_version <= 0:
            record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.confirm_not_pending",
                message=self._import_confirm_not_pending_text,
            )
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
                restore_pending_job=restore_pending_job,
            )
            return None, self._import_confirm_not_pending_text

        approved = record_import_approval(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
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
            return None, self._import_confirm_state_unavailable_text
        if not approved:
            rejection_text = self._resolve_not_pending_rejection_text(
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                find_version_stale_rejection_text=find_version_stale_rejection_text,
            )
            record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.stale_rejected",
                message=rejection_text,
            )
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
                restore_pending_job=restore_pending_job,
            )
            return None, rejection_text

        return (
            ImportConfirmPreparationState(
                prepared_import=prepared_import,
                confirm_context=confirm_context,
                execution_mode=execution_mode,
                expected_lease_version=expected_lease_version,
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
            ),
            "",
        )

    def _resolve_not_pending_rejection_text(
        self,
        *,
        task_id: str,
        task_hash: str,
        find_version_stale_rejection_text: FindVersionStaleRejectionTextFunc,
    ) -> str:
        stale_text = find_version_stale_rejection_text(task_id=task_id, task_hash=task_hash)
        return stale_text or self._import_confirm_not_pending_text

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
