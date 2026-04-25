from __future__ import annotations

from dataclasses import dataclass

from app.db.job_event_repo import JobEvent, JobEventRepo
from app.db.job_repo import JobRepo
from app.services.cleanup_correlation_event_support import fetch_cleanup_correlation_event
from app.services.cleanup_correlation_logging_support import (
    print_cleanup_correlation_lookup_failed_log,
    print_cleanup_correlation_path_missing_log,
    print_cleanup_correlation_result_missing_log,
    print_cleanup_correlation_row_corrupted_log,
    print_cleanup_job_lookup_failed_log,
)
from app.services.cleanup_correlation_result_support import build_cleanup_correlation_result
from app.services.cleanup_task_identity_support import resolve_cleanup_task_identity

CLEANUP_CORRELATION_LOOKUP_RESULT_MISSING_REASON = "job_event list result missing during correlation lookup"


@dataclass(frozen=True, slots=True)
class ImportCorrelation:
    task_ref: str
    task_id: str
    task_hash: str
    source_path: str
    target_path: str


@dataclass(frozen=True, slots=True)
class ResolvedCleanupTaskIdentity:
    lookup_task_ref: str
    lookup_task_id: str
    lookup_task_hash: str
    task_ref: str
    task_id: str
    task_hash: str


class CleanupCorrelationLookup:
    def __init__(
        self,
        *,
        job_event_repo: JobEventRepo,
        job_repo: JobRepo | None,
    ) -> None:
        self._job_event_repo = job_event_repo
        self._job_repo = job_repo

    def find_import_correlation(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> tuple[ResolvedCleanupTaskIdentity, ImportCorrelation | None]:
        resolved_identity = self.resolve_task_identity(task_ref=task_ref, chat_id=chat_id)
        event = fetch_cleanup_correlation_event(
            fetch_event=lambda: self._job_event_repo.find_latest_import_correlation(
                task_ref=resolved_identity.lookup_task_ref,
                task_id=resolved_identity.lookup_task_id,
                task_hash=resolved_identity.lookup_task_hash,
            ),
            on_result_missing=lambda reason: _print_cleanup_correlation_result_missing_log(
                task_ref=task_ref,
                resolved_identity=resolved_identity,
                reason=reason,
            ),
            on_row_corrupted=lambda reason: _print_cleanup_correlation_row_corrupted_log(
                task_ref=task_ref,
                resolved_identity=resolved_identity,
                reason=reason,
            ),
            on_failed=lambda reason: _print_cleanup_correlation_lookup_failed_log(
                task_ref=task_ref,
                resolved_identity=resolved_identity,
                reason=reason,
            ),
            result_missing_reason=CLEANUP_CORRELATION_LOOKUP_RESULT_MISSING_REASON,
            is_row_corrupted_reason=lambda reason: _is_cleanup_correlation_row_corrupted_reason(reason),
        )
        if event is None:
            return resolved_identity, None

        correlation = build_cleanup_correlation_result(
            event=event,
            fallback_task_ref=resolved_identity.task_ref,
            fallback_task_id=resolved_identity.task_id,
            fallback_task_hash=resolved_identity.task_hash,
            on_path_missing=lambda source_path_missing, target_path_missing: _print_cleanup_correlation_path_missing_log(
                task_ref=task_ref,
                resolved_identity=resolved_identity,
                event=event,
                source_path_missing=source_path_missing,
                target_path_missing=target_path_missing,
            ),
        )
        if correlation is None:
            return resolved_identity, None

        return resolved_identity, ImportCorrelation(
            task_ref=correlation.task_ref,
            task_id=correlation.task_id,
            task_hash=correlation.task_hash,
            source_path=correlation.source_path,
            target_path=correlation.target_path,
        )

    def resolve_task_identity(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> ResolvedCleanupTaskIdentity:
        resolution = resolve_cleanup_task_identity(
            task_ref=task_ref,
            chat_id=chat_id,
            job_lookup=(
                (lambda resolved_chat_id, resolved_task_ref: self._job_repo.get_job_for_chat_ref(
                    chat_id=resolved_chat_id,
                    task_ref=resolved_task_ref,
                ))
                if self._job_repo is not None
                else None
            ),
            on_job_lookup_failed=lambda error: _print_cleanup_job_lookup_failed_log(
                task_ref=task_ref,
                chat_id=chat_id or 0,
                error=error,
            ),
        )

        return ResolvedCleanupTaskIdentity(
            lookup_task_ref=resolution.lookup_task_ref,
            lookup_task_id=resolution.lookup_task_id,
            lookup_task_hash=resolution.lookup_task_hash,
            task_ref=resolution.task_ref,
            task_id=resolution.task_id,
            task_hash=resolution.task_hash,
        )


def _is_cleanup_correlation_row_corrupted_reason(reason: str) -> bool:
    return reason.endswith("corrupted after read")


def _print_cleanup_job_lookup_failed_log(*, task_ref: str, chat_id: int, error: Exception) -> None:
    print_cleanup_job_lookup_failed_log(
        task_ref=task_ref,
        chat_id=chat_id,
        error=error,
    )


def _print_cleanup_correlation_result_missing_log(
    *,
    task_ref: str,
    resolved_identity: ResolvedCleanupTaskIdentity,
    reason: str,
) -> None:
    print_cleanup_correlation_result_missing_log(
        task_ref=task_ref,
        lookup_task_ref=resolved_identity.lookup_task_ref,
        lookup_task_id=resolved_identity.lookup_task_id,
        lookup_task_hash=resolved_identity.lookup_task_hash,
        reason=reason,
    )


def _print_cleanup_correlation_row_corrupted_log(
    *,
    task_ref: str,
    resolved_identity: ResolvedCleanupTaskIdentity,
    reason: str,
) -> None:
    print_cleanup_correlation_row_corrupted_log(
        task_ref=task_ref,
        lookup_task_ref=resolved_identity.lookup_task_ref,
        lookup_task_id=resolved_identity.lookup_task_id,
        lookup_task_hash=resolved_identity.lookup_task_hash,
        reason=reason,
    )


def _print_cleanup_correlation_lookup_failed_log(
    *,
    task_ref: str,
    resolved_identity: ResolvedCleanupTaskIdentity,
    reason: str,
) -> None:
    print_cleanup_correlation_lookup_failed_log(
        task_ref=task_ref,
        lookup_task_ref=resolved_identity.lookup_task_ref,
        lookup_task_id=resolved_identity.lookup_task_id,
        lookup_task_hash=resolved_identity.lookup_task_hash,
        reason=reason,
    )


def _print_cleanup_correlation_path_missing_log(
    *,
    task_ref: str,
    resolved_identity: ResolvedCleanupTaskIdentity,
    event: JobEvent,
    source_path_missing: bool,
    target_path_missing: bool,
) -> None:
    print_cleanup_correlation_path_missing_log(
        task_ref=task_ref,
        lookup_task_ref=resolved_identity.lookup_task_ref,
        lookup_task_id=resolved_identity.lookup_task_id,
        lookup_task_hash=resolved_identity.lookup_task_hash,
        event_type=event.event_type,
        source_path_missing=source_path_missing,
        target_path_missing=target_path_missing,
    )
