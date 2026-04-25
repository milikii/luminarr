from __future__ import annotations

from pathlib import Path


def validate_cleanup_paths(
    *,
    source_path: Path,
    target_path: Path,
    source_type_unsupported_text: str,
    guard_rejected_text: str,
) -> str | None:
    if not source_path.is_file() and not source_path.is_dir():
        return source_type_unsupported_text

    source_resolved = source_path.resolve(strict=True)
    target_resolved = target_path.resolve(strict=True)
    if (
        source_resolved == target_resolved
        or source_resolved in target_resolved.parents
        or target_resolved in source_resolved.parents
    ):
        return guard_rejected_text.format(
            source_path=str(source_path),
            target_path=str(target_path),
        )
    return None
