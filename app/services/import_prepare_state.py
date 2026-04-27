from __future__ import annotations

import re
import sqlite3
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.clients.transmission import TransmissionImportSource
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.services.import_transfer_execution import PreparedImport
from app.services.media_name_parser import parse_media_name

GetImportSourceFunc = Callable[..., Awaitable[TransmissionImportSource | None]]
RecordImportEventFunc = Callable[..., None]


class ImportPrepareState:
    def __init__(
        self,
        *,
        get_import_source_func: GetImportSourceFunc,
        library_target_dir: Path,
        job_event_repo: JobEventRepo | None,
        record_event_func: RecordImportEventFunc,
        import_query_failed_text: str,
        import_not_found_text: str,
        import_not_completed_text_template: str,
        import_source_missing_text: str,
        import_prepare_target_failed_text_template: str,
        import_target_exists_text_template: str,
    ) -> None:
        self._get_import_source_func = get_import_source_func
        self._library_target_dir = library_target_dir
        self._job_event_repo = job_event_repo
        self._record_event = record_event_func
        self._import_query_failed_text = import_query_failed_text
        self._import_not_found_text = import_not_found_text
        self._import_not_completed_text_template = import_not_completed_text_template
        self._import_source_missing_text = import_source_missing_text
        self._import_prepare_target_failed_text_template = import_prepare_target_failed_text_template
        self._import_target_exists_text_template = import_target_exists_text_template

    async def prepare_import(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
    ) -> tuple[PreparedImport | None, str]:
        try:
            import_source = await self._get_import_source(task_ref, chat_id=chat_id)
        except Exception as error:
            print(
                f"\033[31m[导入源查询失败]\033[0m task_ref={task_ref} chat_id={chat_id or 0} 错误={error}\n\033[33m[处理建议]\033[0m 检查下载器状态查询、下载器路由和网络连通性；当前请求会返回查询失败文本，并记录 `import.query_failed` 事件。",
                flush=True,
            )
            self._record_event(
                task_ref=task_ref,
                event_type="import.query_failed",
                message=self._import_query_failed_text,
            )
            return None, self._import_query_failed_text

        if import_source is None:
            self._record_event(
                task_ref=task_ref,
                event_type="import.not_found",
                message=self._import_not_found_text,
            )
            return None, self._import_not_found_text

        progress = clamp_progress(import_source.percent_done)
        if not is_download_completed(import_source):
            message = self._import_not_completed_text_template.format(progress=progress)
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.not_completed",
                message=message,
            )
            return None, message

        source_path = Path(import_source.download_dir) / import_source.name
        if not source_path.exists():
            print(
                f"\033[31m[导入源文件缺失]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} source_path={source_path}\n\033[33m[处理建议]\033[0m 检查下载目录是否已被清理、移动或手工删除；确认下载源仍在后再重新执行导入。",
                flush=True,
            )
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.source_missing",
                message=self._import_source_missing_text,
            )
            return None, self._import_source_missing_text

        target_root = self._library_target_dir
        try:
            target_root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            message = self._import_prepare_target_failed_text_template.format(target_path=str(target_root))
            print(
                f"\033[31m[导入目标目录创建失败]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} target_path={target_root} 错误={error}\n\033[33m[处理建议]\033[0m 检查 LIBRARY_TARGET_DIR 是否存在、是否可写，以及当前进程对目标目录是否有创建权限；当前请求会直接失败返回。",
                flush=True,
            )
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.prepare_target_failed",
                message=message,
            )
            return None, message

        naming_truth = self.resolve_normalized_naming_truth(
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            fallback_name=import_source.name,
        )
        normalized_target_name = build_normalized_target_name(
            source_path=source_path,
            naming_truth=naming_truth,
        )
        target_path = target_root / normalized_target_name
        if target_path.exists():
            message = self._import_target_exists_text_template.format(target_path=str(target_path))
            print(
                f"\033[31m[导入目标已存在]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} target_path={target_path}\n\033[33m[处理建议]\033[0m 检查库目录里是否已有同名文件或目录；若这是历史残留，请先确认是否可复用或手动清理后再重试导入。",
                flush=True,
            )
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.target_exists",
                message=message,
            )
            return None, message

        return PreparedImport(import_source=import_source, source_path=source_path, target_path=target_path), ""

    def resolve_normalized_naming_truth(
        self,
        *,
        task_id: str,
        task_hash: str,
        fallback_name: str,
    ) -> str:
        fallback = fallback_name.strip()
        if self._job_event_repo is None:
            return fallback
        try:
            events = self._job_event_repo.list_events_for_task_identity(task_id=task_id, task_hash=task_hash)
            if events is None:
                raise JobEventPersistenceError("import naming truth result missing")
        except (JobEventPersistenceError, sqlite3.Error) as error:
            if str(error) == "import naming truth result missing":
                _log_import_naming_truth_result_missing(task_id=task_id, task_hash=task_hash, reason=str(error))
            elif _is_import_naming_truth_row_corrupted_error(error):
                _log_import_naming_truth_row_corrupted(task_id=task_id, task_hash=task_hash, reason=str(error))
            else:
                _log_import_naming_truth_query_failed(task_id=task_id, task_hash=task_hash, reason=str(error))
            return fallback
        for event in reversed(events):
            if event.event_type != "downloader.succeeded":
                continue
            title = event.message.strip()
            if title:
                return title
        return fallback

    async def _get_import_source(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
    ) -> TransmissionImportSource | None:
        if chat_id is None:
            return await self._get_import_source_func(task_ref)
        try:
            return await self._get_import_source_func(task_ref, chat_id)
        except TypeError:
            return await self._get_import_source_func(task_ref)


def is_download_completed(import_source: TransmissionImportSource) -> bool:
    if import_source.is_finished:
        return True
    return import_source.percent_done >= 1.0


def clamp_progress(raw_progress: float) -> float:
    progress = raw_progress * 100
    if progress < 0:
        return 0.0
    if progress > 100:
        return 100.0
    return progress


def extract_title_year_for_scrape(target_path: Path) -> tuple[str, str]:
    if target_path.is_file():
        base_name = target_path.stem
    else:
        base_name = target_path.name
    normalized = _normalize_name_tokens(base_name)
    parsed_name = parse_media_name(base_name)
    year = str(parsed_name.year) if parsed_name.year is not None else _extract_movie_year(normalized)
    if parsed_name.season is not None or parsed_name.episode is not None:
        title = _normalize_name_tokens(parsed_name.title) or normalized
    elif year:
        title = _normalize_name_tokens(parsed_name.title) or _trim_title_before_year(normalized, year)
    else:
        title = _normalize_name_tokens(parsed_name.title) or normalized
    title = _sanitize_target_component(title)
    if not title:
        title = _sanitize_target_component(base_name)
    return title, year


def extract_title_year_from_text(value: str) -> tuple[str, str]:
    normalized = _normalize_name_tokens(value)
    legacy_year = _extract_movie_year(normalized)
    parsed_name = parse_media_name(value)
    if parsed_name.season is not None or parsed_name.episode is not None:
        title = _normalize_name_tokens(parsed_name.title) or normalized
    elif legacy_year:
        title = _trim_title_before_year(normalized, legacy_year)
    else:
        title = normalized
    year = str(parsed_name.year) if parsed_name.year is not None else legacy_year
    title = title.strip()
    return title, year


def build_normalized_target_name(*, source_path: Path, naming_truth: str) -> str:
    if source_path.is_file():
        source_base_name = source_path.stem
        suffix = source_path.suffix
    else:
        source_base_name = source_path.name
        suffix = ""

    raw_truth = naming_truth.strip() or source_base_name
    if suffix and raw_truth.lower().endswith(suffix.lower()):
        raw_truth = raw_truth[: -len(suffix)]

    parsed_truth = parse_media_name(raw_truth)
    if parsed_truth.season is not None or parsed_truth.episode is not None:
        parsed_truth_base = _build_target_base_from_parsed_name(parsed_truth)
        if parsed_truth_base:
            sanitized_base = _sanitize_target_component(parsed_truth_base)
            if sanitized_base:
                return f"{sanitized_base}{suffix}" if suffix else sanitized_base

    normalized_truth = _normalize_name_tokens(raw_truth)
    normalized_source = _normalize_name_tokens(source_base_name)
    year = _extract_movie_year(normalized_truth) or _extract_movie_year(normalized_source)

    title_base = normalized_truth or normalized_source
    if year:
        title_base = _trim_title_before_year(title_base, year)
    if not title_base:
        title_base = normalized_source or source_base_name.strip()

    if year:
        final_base = f"{title_base} ({year})"
    else:
        final_base = title_base

    sanitized_base = _sanitize_target_component(final_base)
    if not sanitized_base:
        sanitized_base = _sanitize_target_component(normalized_source or source_base_name.strip())
    if not sanitized_base:
        sanitized_base = "unknown"

    if suffix:
        return f"{sanitized_base}{suffix}"
    return sanitized_base


def _build_target_base_from_parsed_name(parsed_name) -> str:
    title = _normalize_name_tokens(parsed_name.title)
    if not title:
        return ""
    episode_marker = _build_episode_marker(
        season=parsed_name.season,
        episode=parsed_name.episode,
        episode_end=parsed_name.episode_end,
    )
    if episode_marker:
        return f"{title} {episode_marker}".strip()
    if parsed_name.year is not None:
        return f"{title} ({parsed_name.year})"
    return title


def _build_episode_marker(*, season: int | None, episode: int | None, episode_end: int | None) -> str:
    if season is None and episode is None:
        return ""
    if season is not None and episode is not None:
        start = f"S{season:02d}E{episode:02d}" if episode < 100 else f"S{season:02d}E{episode}"
        if episode_end is None:
            return start
        end = f"{episode_end:02d}" if episode_end < 100 else str(episode_end)
        return f"{start}-{end}"
    if season is not None:
        return f"S{season:02d}"
    start = f"E{episode:02d}" if episode is not None and episode < 100 else f"E{episode}"
    if episode_end is None:
        return start
    end = f"{episode_end:02d}" if episode_end < 100 else str(episode_end)
    return f"{start}-{end}"


def _normalize_name_tokens(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"[._]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _extract_movie_year(value: str) -> str:
    matched = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", value)
    if matched is None:
        return ""
    return matched.group(1)


def _trim_title_before_year(value: str, year: str) -> str:
    if not value or not year:
        return value.strip()
    matched = re.search(rf"(?<!\d){re.escape(year)}(?!\d)", value)
    if matched is None:
        return value.strip()
    prefix = value[: matched.start()].strip()
    if prefix:
        return prefix
    without_year = re.sub(rf"(?<!\d){re.escape(year)}(?!\d)", " ", value)
    return without_year.strip()


def _sanitize_target_component(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-_")
    cleaned = re.sub(r"[\(\[\{]+$", "", cleaned).strip(" .-_")
    return cleaned


def _log_import_naming_truth_query_failed(*, task_id: str, task_hash: str, reason: str) -> None:
    print(
        f"\033[31m[导入命名真相查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表读取是否正常；"
        "当前导入会退回下载源名称做命名，文件名可能缺少 downloader 已确认的标题真相。",
        flush=True,
    )


def _log_import_naming_truth_result_missing(*, task_id: str, task_hash: str, reason: str) -> None:
    print(
        f"\033[31m[导入命名真相结果缺失]\033[0m task_id={task_id} task_hash={task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 job_event 查询返回是否仍带有完整结果；"
        "当前导入会退回下载源名称做命名，避免把缺失真相误判成“没有 downloader 标题”。",
        flush=True,
    )


def _log_import_naming_truth_row_corrupted(*, task_id: str, task_hash: str, reason: str) -> None:
    print(
        f"\033[31m[导入命名真相记录损坏]\033[0m task_id={task_id} task_hash={task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 job_event 里的 task_ref / event_type / message 等命名真相字段是否仍是完整记录；"
        "当前导入会退回下载源名称做命名，避免把坏记录混成普通查询失败。",
        flush=True,
    )


def _is_import_naming_truth_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")
