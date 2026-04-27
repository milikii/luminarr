from __future__ import annotations

import errno
import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.clients.transmission import TransmissionImportSource
from app.services.import_context_lookup import ConfirmExecutionContext
from app.services.import_post_processing import ImportPostProcessRequest, ImportPostProcessingService

IMPORT_EXECUTION_MODE_COPY = "copy"
IMPORT_EXECUTION_MODE_HARDLINK = "hardlink"
_EXTERNAL_SUBTITLE_SUFFIXES = (".srt", ".ass")

RecordImportEventFunc = Callable[..., None]


@dataclass(frozen=True, slots=True)
class PreparedImport:
    import_source: TransmissionImportSource
    source_path: Path
    target_path: Path


@dataclass(frozen=True, slots=True)
class ImportExecutionResult:
    reply: str
    imported: bool
    pending_copy_approval: bool = False


class ImportTransferExecutionService:
    def __init__(
        self,
        *,
        post_processing_service: ImportPostProcessingService,
        record_event_func: RecordImportEventFunc,
        import_source_type_unsupported_text: str,
        import_target_exists_text_template: str,
        import_copy_approval_pending_text_template: str,
        import_copy_failed_text_template: str,
        import_hardlink_failed_text_template: str,
    ) -> None:
        self._post_processing_service = post_processing_service
        self._record_event = record_event_func
        self._import_source_type_unsupported_text = import_source_type_unsupported_text
        self._import_target_exists_text_template = import_target_exists_text_template
        self._import_copy_approval_pending_text_template = import_copy_approval_pending_text_template
        self._import_copy_failed_text_template = import_copy_failed_text_template
        self._import_hardlink_failed_text_template = import_hardlink_failed_text_template
        self._pending_copy_fallback_identities: set[tuple[str, str]] = set()

    def pending_copy_fallback_payload_json(self) -> str:
        return json.dumps({"mode": IMPORT_EXECUTION_MODE_COPY}, ensure_ascii=False)

    def resolve_execution_mode(
        self,
        *,
        task_id: str,
        task_hash: str,
        confirm_context: ConfirmExecutionContext | None,
    ) -> str | None:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return IMPORT_EXECUTION_MODE_HARDLINK
        payload_corrupted = False
        if confirm_context is not None:
            copy_fallback_pending, payload_problem = _parse_copy_fallback_pending_payload(confirm_context.job.payload_json)
            if copy_fallback_pending is True:
                return IMPORT_EXECUTION_MODE_COPY
            if copy_fallback_pending is None:
                payload_corrupted = True
                self._log_copy_fallback_payload_corrupted(
                    task_id=task_id,
                    task_hash=task_hash,
                    payload_problem=payload_problem or "unknown",
                )
        if identity in self._pending_copy_fallback_identities:
            return IMPORT_EXECUTION_MODE_COPY
        if payload_corrupted:
            return None
        return IMPORT_EXECUTION_MODE_HARDLINK

    def record_copy_fallback_pending(self, *, task_id: str, task_hash: str) -> None:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return
        self._pending_copy_fallback_identities.add(identity)

    def clear_pending_copy_fallback(self, *, task_id: str, task_hash: str) -> None:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return
        self._pending_copy_fallback_identities.discard(identity)

    async def execute_import(
        self,
        *,
        task_ref: str,
        prepared_import: PreparedImport,
        execution_mode: str,
    ) -> ImportExecutionResult:
        import_source = prepared_import.import_source
        source_path = prepared_import.source_path
        target_path = prepared_import.target_path

        try:
            if execution_mode == IMPORT_EXECUTION_MODE_COPY:
                _copy_import(
                    source_path,
                    target_path,
                    import_source_type_unsupported_text=self._import_source_type_unsupported_text,
                )
            else:
                _hardlink_import(
                    source_path,
                    target_path,
                    import_source_type_unsupported_text=self._import_source_type_unsupported_text,
                )
        except FileExistsError:
            message = self._import_target_exists_text_template.format(target_path=str(target_path))
            print(
                f"\033[31m[导入目标已存在]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} target_path={target_path}\n\033[33m[处理建议]\033[0m 检查导入执行期间是否已有并发写入或历史文件落到相同目标；确认目标文件可复用或清理后再重试。",
                flush=True,
            )
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.target_exists",
                message=message,
            )
            return ImportExecutionResult(reply=message, imported=False)
        except OSError as exc:
            if execution_mode != IMPORT_EXECUTION_MODE_COPY and exc.errno == errno.EXDEV:
                prompt_text = self._import_copy_approval_pending_text_template.format(task_ref=task_ref)
                self._record_event(
                    task_ref=task_ref,
                    task_id=import_source.task_id,
                    task_hash=import_source.task_hash,
                    event_type="import.copy_fallback_pending",
                    message=prompt_text,
                )
                return ImportExecutionResult(
                    reply=prompt_text,
                    imported=False,
                    pending_copy_approval=True,
                )
            message = (
                self._import_copy_failed_text_template.format(reason=str(exc))
                if execution_mode == IMPORT_EXECUTION_MODE_COPY
                else self._import_hardlink_failed_text_template.format(reason=str(exc))
            )
            if execution_mode == IMPORT_EXECUTION_MODE_COPY:
                print(
                    f"\033[31m[导入复制失败]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} source_path={source_path} target_path={target_path} 错误={exc}\n\033[33m[处理建议]\033[0m 检查目标目录权限、磁盘空间和目标路径占用情况；如果是复制导入确认后的失败，修复后可重新执行 confirm {task_ref}。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[导入硬链接失败]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} source_path={source_path} target_path={target_path} 错误={exc}\n\033[33m[处理建议]\033[0m 检查下载目录与库目录权限、目标路径占用情况，以及跨文件系统场景是否应改走 copy fallback 后重试。",
                    flush=True,
                )
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type=(
                    "import.copy_failed"
                    if execution_mode == IMPORT_EXECUTION_MODE_COPY
                    else "import.hardlink_failed"
                ),
                message=message,
            )
            return ImportExecutionResult(reply=message, imported=False)

        import_success_text = (
            f"导入成功：{import_source.name}\n"
            f"任务 ID: {import_source.task_id}\n"
            f"任务 Hash: {import_source.task_hash}\n"
            f"目标路径: {target_path}"
        )
        if execution_mode == IMPORT_EXECUTION_MODE_COPY:
            import_success_text = f"{import_success_text}\n导入方式: 复制"
        self._record_event(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.succeeded",
            message=str(target_path),
            source_path=str(source_path),
            target_path=str(target_path),
        )
        post_process_result = await self._post_processing_service.run(
            ImportPostProcessRequest(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                target_path=target_path,
            )
        )
        return ImportExecutionResult(reply=f"{import_success_text}{post_process_result.reply_suffix}", imported=True)

    def _log_copy_fallback_payload_corrupted(self, *, task_id: str, task_hash: str, payload_problem: str) -> None:
        print(
            f"\033[31m[导入执行模式载荷损坏]\033[0m task_id={task_id} task_hash={task_hash} 载荷={payload_problem}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里的 payload_json 是否仍是完整 copy-fallback 待确认上下文；若当前进程里也没有 copy-fallback 待确认兜底，当前 confirm 会直接返回状态读取失败，避免把坏载荷误判成硬链接导入。",
            flush=True,
        )


def _hardlink_import(
    source_path: Path,
    target_path: Path,
    *,
    import_source_type_unsupported_text: str,
) -> None:
    if source_path.is_file():
        transfer_pairs = _build_file_transfer_pairs(source_path=source_path, target_path=target_path)
        _ensure_transfer_targets_do_not_exist(transfer_pairs)
        _hardlink_file_pairs(transfer_pairs)
        return
    if source_path.is_dir():
        _hardlink_directory(source_path, target_path)
        return
    raise OSError(errno.EINVAL, import_source_type_unsupported_text)


def _copy_import(
    source_path: Path,
    target_path: Path,
    *,
    import_source_type_unsupported_text: str,
) -> None:
    if source_path.is_file():
        transfer_pairs = _build_file_transfer_pairs(source_path=source_path, target_path=target_path)
        _ensure_transfer_targets_do_not_exist(transfer_pairs)
        _copy_file_pairs(transfer_pairs)
        return
    if source_path.is_dir():
        try:
            shutil.copytree(source_path, target_path, copy_function=shutil.copy2)
        except (OSError, shutil.Error):
            _cleanup_partial_target(target_path)
            raise
        return
    raise OSError(errno.EINVAL, import_source_type_unsupported_text)


def _hardlink_directory(source_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=False)
    for current_dir, _, file_names in os.walk(source_dir):
        current_source = Path(current_dir)
        relative = current_source.relative_to(source_dir)
        current_target = target_dir / relative
        current_target.mkdir(parents=True, exist_ok=True)
        for file_name in file_names:
            src_file = current_source / file_name
            dst_file = current_target / file_name
            if dst_file.exists():
                raise FileExistsError(str(dst_file))
            os.link(src_file, dst_file)


def _build_file_transfer_pairs(*, source_path: Path, target_path: Path) -> list[tuple[Path, Path]]:
    transfer_pairs: list[tuple[Path, Path]] = [(source_path, target_path)]
    target_stem = target_path.stem
    for sidecar_path in _find_external_subtitle_sidecars(source_path):
        suffix = _extract_sidecar_suffix(source_path=source_path, sidecar_path=sidecar_path)
        if suffix is None:
            continue
        transfer_pairs.append((sidecar_path, target_path.with_name(f"{target_stem}{suffix}")))
    return transfer_pairs


def _find_external_subtitle_sidecars(source_path: Path) -> list[Path]:
    if not source_path.exists() or not source_path.is_file():
        return []
    sidecars: list[Path] = []
    for candidate in sorted(source_path.parent.iterdir()):
        if candidate == source_path or not candidate.is_file():
            continue
        if _extract_sidecar_suffix(source_path=source_path, sidecar_path=candidate) is None:
            continue
        sidecars.append(candidate)
    return sidecars


def _extract_sidecar_suffix(*, source_path: Path, sidecar_path: Path) -> str | None:
    source_stem = source_path.stem
    candidate_name = sidecar_path.name
    lowered_name = candidate_name.lower()
    for suffix in _EXTERNAL_SUBTITLE_SUFFIXES:
        if not lowered_name.endswith(suffix):
            continue
        subtitle_stem = candidate_name[: -len(suffix)]
        if subtitle_stem == source_stem:
            return candidate_name[len(source_stem) :]
        if subtitle_stem.startswith(f"{source_stem}."):
            return candidate_name[len(source_stem) :]
    return None


def _ensure_transfer_targets_do_not_exist(transfer_pairs: list[tuple[Path, Path]]) -> None:
    for _, target_path in transfer_pairs:
        if target_path.exists():
            raise FileExistsError(str(target_path))


def _hardlink_file_pairs(transfer_pairs: list[tuple[Path, Path]]) -> None:
    created_targets: list[Path] = []
    try:
        for source_path, target_path in transfer_pairs:
            os.link(source_path, target_path)
            created_targets.append(target_path)
    except (OSError, shutil.Error):
        _cleanup_partial_targets(created_targets)
        raise


def _copy_file_pairs(transfer_pairs: list[tuple[Path, Path]]) -> None:
    created_targets: list[Path] = []
    current_target: Path | None = None
    try:
        for source_path, target_path in transfer_pairs:
            current_target = target_path
            shutil.copy2(source_path, target_path)
            created_targets.append(target_path)
            current_target = None
    except (OSError, shutil.Error):
        cleanup_targets = list(created_targets)
        if current_target is not None:
            cleanup_targets.append(current_target)
        _cleanup_partial_targets(cleanup_targets)
        raise


def _cleanup_partial_targets(target_paths: list[Path]) -> None:
    for target_path in reversed(target_paths):
        _cleanup_partial_target(target_path)


def _cleanup_partial_target(target_path: Path) -> None:
    try:
        if target_path.is_dir():
            shutil.rmtree(target_path)
        elif target_path.exists() or target_path.is_symlink():
            target_path.unlink()
    except OSError as error:
        print(
            f"\033[31m[导入残留清理失败]\033[0m target={target_path} 错误={error}\n"
            "\033[33m[处理建议]\033[0m 检查目标路径是否被占用、是否仍有写权限，"
            "并手动清理这次失败导入留下的半成品文件或目录。",
            flush=True,
        )


def _parse_copy_fallback_pending_payload(payload_json: str) -> tuple[bool | None, str | None]:
    cleaned_payload = payload_json.strip()
    if not cleaned_payload:
        return False, None
    try:
        payload = json.loads(cleaned_payload)
    except json.JSONDecodeError:
        return None, "payload_json invalid json"
    if not isinstance(payload, dict):
        return None, "payload_json not object"
    return str(payload.get("mode", "")).strip() == IMPORT_EXECUTION_MODE_COPY, None
