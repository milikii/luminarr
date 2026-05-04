from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from app.operational_logging import emit_operational_log
from app.services.metadata_scraper import MetadataScrapeInput, MetadataScrapeResult
from app.services.subtitle_translator import SubtitleTranslateInput, SubtitleTranslateResult

RefreshMediaServerFunc = Callable[[], Awaitable[str]]
MetadataScrapeFunc = Callable[[MetadataScrapeInput], Awaitable[MetadataScrapeResult]]
SubtitleTranslateFunc = Callable[[SubtitleTranslateInput], SubtitleTranslateResult]
ResolveMetadataTitleYearFunc = Callable[[str, str, Path], tuple[str, str]]
ResolveMetadataTmdbIdFunc = Callable[[str, str], str]
RecordImportEventFunc = Callable[..., None]

IMPORT_REFRESH_FAILED_TEXT = "媒体库刷新失败：未知错误"
IMPORT_REFRESH_SUCCESS_TEXT = "媒体库刷新成功。"


@dataclass(frozen=True, slots=True)
class ImportPostProcessRequest:
    task_ref: str
    task_id: str
    task_hash: str
    target_path: Path


@dataclass(frozen=True, slots=True)
class ImportPostProcessResult:
    reply_suffix: str = ""
    metadata_message: str = ""
    subtitle_message: str = ""
    refresh_message: str = ""
    metadata_status: str = ""
    subtitle_status: str = ""
    refresh_status: str = ""


class ImportPostProcessingService:
    def __init__(
        self,
        *,
        refresh_media_server_func: RefreshMediaServerFunc | None,
        scrape_metadata_func: MetadataScrapeFunc | None,
        translate_subtitle_func: SubtitleTranslateFunc | None,
        resolve_metadata_title_year_func: ResolveMetadataTitleYearFunc,
        resolve_metadata_tmdb_id_func: ResolveMetadataTmdbIdFunc,
        record_event_func: RecordImportEventFunc,
    ) -> None:
        self._refresh_media_server_func = refresh_media_server_func
        self._scrape_metadata_func = scrape_metadata_func
        self._translate_subtitle_func = translate_subtitle_func
        self._resolve_metadata_title_year = resolve_metadata_title_year_func
        self._resolve_metadata_tmdb_id = resolve_metadata_tmdb_id_func
        self._record_event = record_event_func

    async def run(self, request: ImportPostProcessRequest) -> ImportPostProcessResult:
        metadata_result = await self._try_scrape_metadata(request=request)
        subtitle_result = self._try_translate_subtitle(request=request, metadata_result=metadata_result)
        refresh_result = await self._try_refresh(request=request)
        return build_import_post_process_result(
            metadata_result=metadata_result,
            subtitle_result=subtitle_result,
            refresh_result=refresh_result,
        )

    async def _try_scrape_metadata(
        self,
        *,
        request: ImportPostProcessRequest,
    ) -> MetadataScrapeResult | None:
        if self._scrape_metadata_func is None:
            return None

        title, year = self._resolve_metadata_title_year(
            task_id=request.task_id,
            task_hash=request.task_hash,
            target_path=request.target_path,
        )
        tmdb_id = self._resolve_metadata_tmdb_id(
            request.task_id,
            request.task_hash,
        )
        scrape_input = MetadataScrapeInput(
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            title=title,
            year=year,
            target_path=str(request.target_path),
            tmdb_id=tmdb_id,
        )
        try:
            result = await self._scrape_metadata_func(scrape_input)
        except RuntimeError as exc:
            message = f"metadata 刮削执行异常：{exc}"
            self._record_event(
                task_ref=request.task_ref,
                task_id=request.task_id,
                task_hash=request.task_hash,
                event_type="metadata.failed",
                message=message,
            )
            _log_import_metadata_scrape_failed(message=message)
            return None

        event_type = "metadata.succeeded" if result.success else "metadata.failed"
        self._record_event(
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            event_type=event_type,
            message=result.message,
        )
        return result

    def _try_translate_subtitle(
        self,
        *,
        request: ImportPostProcessRequest,
        metadata_result: MetadataScrapeResult | None,
    ) -> SubtitleTranslateResult | None:
        if self._translate_subtitle_func is None:
            return None
        if metadata_result is not None and metadata_result.metadata_path.strip():
            metadata_path = metadata_result.metadata_path.strip()
        else:
            metadata_path = str(_resolve_metadata_sidecar_path(request.target_path))
        translate_input = SubtitleTranslateInput(
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            target_path=str(request.target_path),
            metadata_path=metadata_path,
        )
        try:
            result = self._translate_subtitle_func(translate_input)
        except RuntimeError as exc:
            message = f"subtitle 翻译执行异常：{exc}"
            self._record_event(
                task_ref=request.task_ref,
                task_id=request.task_id,
                task_hash=request.task_hash,
                event_type="subtitle.failed",
                message=message,
            )
            _log_import_subtitle_translate_failed(
                message=message,
                fix_hint="检查字幕文件编码和目录写权限，再重试 confirm 导入。",
            )
            return SubtitleTranslateResult(success=False, message=message)

        if result.skipped:
            event_type = "subtitle.skipped"
        elif result.success:
            event_type = "subtitle.succeeded"
        else:
            event_type = "subtitle.failed"
        self._record_event(
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            event_type=event_type,
            message=result.message,
        )
        if event_type == "subtitle.failed":
            _log_import_subtitle_translate_failed(
                message=result.message,
                fix_hint="检查字幕文件内容、编码和目录写权限，再重试 confirm 导入。",
            )
        return result

    async def _try_refresh(self, *, request: ImportPostProcessRequest) -> str:
        if self._refresh_media_server_func is None:
            return ""

        try:
            refresh_text = await self._refresh_media_server_func()
        except RuntimeError as error:
            _log_import_refresh_failed(
                request=request,
                reason=str(error),
            )
            refresh_text = IMPORT_REFRESH_FAILED_TEXT
            self._record_event(
                task_ref=request.task_ref,
                task_id=request.task_id,
                task_hash=request.task_hash,
                event_type="refresh.failed",
                message=refresh_text,
            )
            return f"\n{refresh_text}"

        event_type = "refresh.succeeded" if refresh_text == IMPORT_REFRESH_SUCCESS_TEXT else "refresh.failed"
        self._record_event(
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            event_type=event_type,
            message=refresh_text,
        )
        return f"\n{refresh_text}"


def _resolve_metadata_sidecar_path(target_path: Path) -> Path:
    if target_path.is_dir():
        return target_path / ".luminarr.metadata.json"
    return target_path.with_suffix(".metadata.json")


def build_import_post_process_result(
    *,
    metadata_result: MetadataScrapeResult | None,
    subtitle_result: SubtitleTranslateResult | None,
    refresh_result: str,
) -> ImportPostProcessResult:
    metadata_message = metadata_result.message.strip() if metadata_result is not None else ""
    subtitle_message = subtitle_result.message.strip() if subtitle_result is not None else ""
    refresh_message = refresh_result.strip()
    metadata_status = _resolve_metadata_status(metadata_result)
    subtitle_status = _resolve_subtitle_status(subtitle_result)
    refresh_status = _resolve_refresh_status(refresh_message)

    summary_lines = [
        _format_summary_line("metadata", metadata_status, metadata_message),
        _format_summary_line("字幕", subtitle_status, subtitle_message),
        _format_summary_line("刷新", refresh_status, refresh_message),
    ]
    summary_lines = [line for line in summary_lines if line]

    if not summary_lines:
        return ImportPostProcessResult()

    reply_suffix = "\n\n后处理总结\n" + "\n".join(f"- {line}" for line in summary_lines)
    return ImportPostProcessResult(
        reply_suffix=reply_suffix,
        metadata_message=metadata_message,
        subtitle_message=subtitle_message,
        refresh_message=refresh_message,
        metadata_status=metadata_status,
        subtitle_status=subtitle_status,
        refresh_status=refresh_status,
    )


def _resolve_metadata_status(result: MetadataScrapeResult | None) -> str:
    if result is None:
        return "skipped"
    return "success" if result.success else "failed"


def _resolve_subtitle_status(result: SubtitleTranslateResult | None) -> str:
    if result is None:
        return "skipped"
    if result.skipped:
        return "skipped"
    return "success" if result.success else "failed"


def _resolve_refresh_status(message: str) -> str:
    if not message:
        return "skipped"
    return "success" if message == IMPORT_REFRESH_SUCCESS_TEXT else "failed"


def _format_summary_line(label: str, status: str, message: str) -> str:
    if status == "skipped" and not message:
        return f"{label}：跳过"
    status_text = {
        "success": "成功",
        "failed": "失败",
        "skipped": "跳过",
    }.get(status, status)
    if not message:
        return f"{label}：{status_text}"
    return f"{label}：{status_text}；{message}"


def _log_import_metadata_scrape_failed(*, message: str) -> None:
    emit_operational_log(
        title="元数据刮削失败",
        detail=message,
        fix_hint="检查 TMDB/Fanart 配置和网络，再重试 confirm 导入。",
    )


def _log_import_subtitle_translate_failed(*, message: str, fix_hint: str) -> None:
    emit_operational_log(
        title="字幕翻译失败",
        detail=message,
        fix_hint=fix_hint,
    )


def _log_import_refresh_failed(*, request: ImportPostProcessRequest, reason: str) -> None:
    emit_operational_log(
        title="媒体库刷新失败",
        detail=f"task_ref={request.task_ref} task_id={request.task_id} task_hash={request.task_hash} 错误={reason}",
        fix_hint="检查媒体服务器地址、API Key 和网络连通性；当前导入成功不会回滚，但刷新结果会按失败文本返回。",
    )
