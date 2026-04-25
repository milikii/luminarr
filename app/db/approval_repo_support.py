from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApprovalIdentity:
    task_id: str
    task_hash: str


@dataclass(frozen=True, slots=True)
class ApprovalTransitionIdentity(ApprovalIdentity):
    expected_lease_version: int


@dataclass(frozen=True, slots=True)
class ApprovalMoveIdentity:
    current_task_id: str
    current_task_hash: str
    new_task_id: str
    new_task_hash: str


def normalize_approval_identity(
    *,
    task_id: str,
    task_hash: str,
    context: str,
    error_cls: type[Exception],
) -> ApprovalIdentity:
    cleaned_task_id = task_id.strip()
    cleaned_task_hash = task_hash.strip()
    if not cleaned_task_id or not cleaned_task_hash:
        raise error_cls(f"approval task identity missing for {context}")
    return ApprovalIdentity(task_id=cleaned_task_id, task_hash=cleaned_task_hash)


def normalize_transition_identity(
    *,
    task_id: str,
    task_hash: str,
    expected_lease_version: int,
    context: str,
    error_cls: type[Exception],
) -> ApprovalTransitionIdentity:
    identity = normalize_approval_identity(
        task_id=task_id,
        task_hash=task_hash,
        context=context,
        error_cls=error_cls,
    )
    if expected_lease_version <= 0:
        raise error_cls(f"approval expected lease version missing for {context}")
    return ApprovalTransitionIdentity(
        task_id=identity.task_id,
        task_hash=identity.task_hash,
        expected_lease_version=expected_lease_version,
    )


def normalize_move_identity(
    *,
    current_task_id: str,
    current_task_hash: str,
    new_task_id: str,
    new_task_hash: str,
    error_cls: type[Exception],
) -> ApprovalMoveIdentity:
    current_identity = normalize_approval_identity(
        task_id=current_task_id,
        task_hash=current_task_hash,
        context="identity move",
        error_cls=error_cls,
    )
    new_identity = normalize_approval_identity(
        task_id=new_task_id,
        task_hash=new_task_hash,
        context="identity move",
        error_cls=error_cls,
    )
    return ApprovalMoveIdentity(
        current_task_id=current_identity.task_id,
        current_task_hash=current_identity.task_hash,
        new_task_id=new_identity.task_id,
        new_task_hash=new_identity.task_hash,
    )
