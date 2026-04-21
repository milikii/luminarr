from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from app.services.metadata_scraper import MetadataScrapeInput, MetadataScrapeResult
from app.services.subtitle_translator import SubtitleTranslateInput, SubtitleTranslateResult

RefreshMediaServerFunc = Callable[[], Awaitable[str]]
MetadataScrapeFunc = Callable[[MetadataScrapeInput], Awaitable[MetadataScrapeResult]]
SubtitleTranslateFunc = Callable[[SubtitleTranslateInput], SubtitleTranslateResult]
ResolveMetadataTitleYearFunc = Callable[[str, str, Path], tuple[str, str]]
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


class ImportPostProcessingService:
    def __init__(
        self,
        *,
        refresh_media_server_func: RefreshMediaServerFunc | None,
        scrape_metadata_func: MetadataScrapeFunc | None,
        translate_subtitle_func: SubtitleTranslateFunc | None,
        resolve_metadata_title_year_func: ResolveMetadataTitleYearFunc,
        record_event_func: RecordImportEventFunc,
    ) -> None:
        self._refresh_media_server_func = refresh_media_server_func
        self._scrape_metadata_func = scrape_metadata_func
        self._translate_subtitle_func = translate_subtitle_func
        self._resolve_metadata_title_year = resolve_metadata_title_year_func
        self._record_event = record_event_func

    async def run(self, request: ImportPostProcessRequest) -> ImportPostProcessResult:
        metadata_result = await self._try_scrape_metadata(request=request)
        self._try_translate_subtitle(request=request, metadata_result=metadata_result)
        refresh_suffix = await self._try_refresh(request=request)
        return ImportPostProcessResult(reply_suffix=refresh_suffix)

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
        scrape_input = MetadataScrapeInput(
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            title=title,
            year=year,
            target_path=str(request.target_path),
        )
        try:
            result = await self._scrape_metadata_func(scrape_input)
        except Exception as exc:
            message = f"metadata 刮削执行异常：{exc}"
            self._record_event(
                task_ref=request.task_ref,
                task_id=request.task_id,
                task_hash=request.task_hash,
                event_type="metadata.failed",
                message=message,
            )
            print(f"\033[31m[元数据刮削失败]\033[0m {message}", flush=True)
            print(
                "\033[33m[处理建议]\033[0m 检查 TMDB/Fanart 配置和网络，再重试 confirm 导入。",
                flush=True,
            )
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
    ) -> None:
        if self._translate_subtitle_func is None:
            return
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
        except Exception as exc:
            message = f"subtitle 翻译执行异常：{exc}"
            self._record_event(
                task_ref=request.task_ref,
                task_id=request.task_id,
                task_hash=request.task_hash,
                event_type="subtitle.failed",
                message=message,
            )
            print(f"\033[31m[字幕翻译失败]\033[0m {message}", flush=True)
            print(
                "\033[33m[处理建议]\033[0m 检查字幕文件编码和目录写权限，再重试 confirm 导入。",
                flush=True,
            )
            return

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
            print(f"\033[31m[字幕翻译失败]\033[0m {result.message}", flush=True)
            print(
                "\033[33m[处理建议]\033[0m 检查字幕文件内容、编码和目录写权限，再重试 confirm 导入。",
                flush=True,
            )

    async def _try_refresh(self, *, request: ImportPostProcessRequest) -> str:
        if self._refresh_media_server_func is None:
            return ""

        try:
            refresh_text = await self._refresh_media_server_func()
        except Exception as error:
            print(
                f"\033[31m[媒体库刷新失败]\033[0m task_ref={request.task_ref} task_id={request.task_id} task_hash={request.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查媒体服务器地址、API Key 和网络连通性；当前导入成功不会回滚，但刷新结果会按失败文本返回。",
                flush=True,
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
