from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.services.subtitle_translation_support import (
    _EmbeddedSubtitleStream,
    _SubtitleFile,
    _SubtitleCommandFailure,
    _SubtitleImportPreparationFailure,
    _build_subtitle_translation_summary,
    _extract_embedded_subtitle_file_for_video,
    _prepare_subtitle_translation_for_import,
    _probe_embedded_subtitle_streams_for_video,
    _print_colored_error,
    _read_metadata_title,
    _request_subtitle_chat_completion,
    _resolve_video_subtitle_files_for_import,
    _translate_single_subtitle_file,
    _translate_ass_subtitle_content,
    _translate_subtitle_lines_professionally,
    _translate_srt_subtitle_content,
)


@dataclass(frozen=True, slots=True)
class SubtitleTranslateInput:
    task_ref: str
    task_id: str
    task_hash: str
    target_path: str
    metadata_path: str = ""


@dataclass(frozen=True, slots=True)
class SubtitleTranslateResult:
    success: bool
    message: str
    translated_count: int = 0
    skipped: bool = False


class SubtitleTranslatorService:
    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        timeout_seconds: float = 60.0,
        proxy_url: str = "",
        request_chat_completion_func: Callable[[str, dict[str, object]], str] | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = (base_url.strip() or "https://api.openai.com/v1").rstrip("/")
        self._model = model.strip() or "gpt-5.4"
        self._timeout_seconds = max(10.0, timeout_seconds)
        self._proxy_url = proxy_url.strip()
        self._request_chat_completion_func = request_chat_completion_func

    def translate_for_import(self, translate_input: SubtitleTranslateInput) -> SubtitleTranslateResult:
        plan, preparation_failure = _prepare_subtitle_translation_for_import(
            target_path=Path(translate_input.target_path).expanduser(),
            metadata_path=Path(translate_input.metadata_path),
            api_key=self._api_key,
            resolve_video_subtitle_files=self._resolve_video_subtitle_files,
            read_metadata_title=_read_metadata_title,
        )
        if preparation_failure is not None:
            return self._build_preparation_result(failure=preparation_failure)

        translated_count, error_result = self._translate_pending_subtitle_files(
            subtitle_files=plan.subtitle_files,
            movie_title=plan.movie_title,
        )
        if error_result is not None:
            return error_result
        return self._build_translation_summary_result(
            movie_title=plan.movie_title,
            translated_count=translated_count,
        )

    def _resolve_video_subtitle_files(
        self,
        video_path: Path,
    ) -> tuple[list[_SubtitleFile], _SubtitleCommandFailure | None, str]:
        return _resolve_video_subtitle_files_for_import(
            video_path=video_path,
            probe_embedded_subtitle_streams=self._probe_embedded_subtitle_streams,
            extract_embedded_subtitle_file=lambda stream, resolved_video_path: self._extract_embedded_subtitle_file(
                video_path=resolved_video_path,
                stream=stream,
            ),
        )

    def _probe_embedded_subtitle_streams(
        self,
        video_path: Path,
    ) -> tuple[list[_EmbeddedSubtitleStream], _SubtitleCommandFailure | None]:
        return _probe_embedded_subtitle_streams_for_video(
            video_path=video_path,
            timeout_seconds=self._timeout_seconds,
        )

    def _probe_embedded_subtitles(
        self,
        video_path: Path,
    ) -> tuple[list[_EmbeddedSubtitleStream], SubtitleTranslateResult | None]:
        streams, failure = self._probe_embedded_subtitle_streams(video_path)
        if failure is None:
            return streams, None
        return [], self._build_failed_result(problem=failure.problem, fix=failure.fix)

    def _extract_embedded_subtitle_file(
        self,
        *,
        video_path: Path,
        stream: _EmbeddedSubtitleStream,
    ) -> tuple[_SubtitleFile | None, _SubtitleCommandFailure | None]:
        return _extract_embedded_subtitle_file_for_video(
            video_path=video_path,
            stream=stream,
            timeout_seconds=self._timeout_seconds,
        )

    def _translate_single_file(
        self,
        *,
        subtitle_file: _SubtitleFile,
        movie_title: str,
    ) -> SubtitleTranslateResult:
        success, error_message, failure = _translate_single_subtitle_file(
            subtitle_file=subtitle_file,
            movie_title=movie_title,
            translate_srt=self._translate_srt_text,
            translate_ass=self._translate_ass_text,
        )
        if failure is not None:
            return self._build_failed_result(
                problem=failure.problem,
                fix=failure.fix,
            )
        if not success:
            return self._build_result(
                success=False,
                message=error_message or "字幕翻译失败。",
            )
        return self._build_result(success=True, message="ok", translated_count=1)

    def _build_failed_result(self, *, problem: str, fix: str) -> SubtitleTranslateResult:
        _print_colored_error(problem=problem, fix=fix)
        return self._build_result(success=False, message=problem)

    def _build_preparation_result(
        self,
        *,
        failure: _SubtitleImportPreparationFailure,
    ) -> SubtitleTranslateResult:
        if failure.fix:
            _print_colored_error(problem=failure.message, fix=failure.fix)
        return self._build_result(
            success=False,
            message=failure.message,
            skipped=failure.skipped,
        )

    def _translate_pending_subtitle_files(
        self,
        *,
        subtitle_files: list[_SubtitleFile],
        movie_title: str,
    ) -> tuple[int, SubtitleTranslateResult | None]:
        translated_count = 0
        for subtitle_file in subtitle_files:
            if subtitle_file.translated_path.exists():
                continue
            result = self._translate_single_file(
                subtitle_file=subtitle_file,
                movie_title=movie_title,
            )
            if not result.success:
                return 0, result
            translated_count += 1
        return translated_count, None

    def _build_translation_summary_result(
        self,
        *,
        movie_title: str,
        translated_count: int,
    ) -> SubtitleTranslateResult:
        message, skipped = _build_subtitle_translation_summary(
            movie_title=movie_title,
            translated_count=translated_count,
        )
        return self._build_result(
            success=not skipped,
            message=message,
            translated_count=translated_count,
            skipped=skipped,
        )

    def _build_result(
        self,
        *,
        success: bool,
        message: str,
        translated_count: int = 0,
        skipped: bool = False,
    ) -> SubtitleTranslateResult:
        return SubtitleTranslateResult(
            success=success,
            message=message,
            translated_count=translated_count,
            skipped=skipped,
        )

    def _translate_srt_text(
        self,
        *,
        source_text: str,
        movie_title: str,
        subtitle_path: Path,
    ) -> tuple[str | None, str | None]:
        return _translate_srt_subtitle_content(
            source_text=source_text,
            movie_title=movie_title,
            subtitle_path=subtitle_path,
            translate_lines=lambda source_lines, resolved_movie_title: self._translate_lines_professional(
                source_lines=source_lines,
                movie_title=resolved_movie_title,
            ),
        )

    def _translate_ass_text(
        self,
        *,
        source_text: str,
        movie_title: str,
        subtitle_path: Path,
    ) -> tuple[str | None, str | None]:
        return _translate_ass_subtitle_content(
            source_text=source_text,
            movie_title=movie_title,
            subtitle_path=subtitle_path,
            translate_lines=lambda source_lines, resolved_movie_title: self._translate_lines_professional(
                source_lines=source_lines,
                movie_title=resolved_movie_title,
            ),
        )

    def _translate_lines_professional(self, *, source_lines: list[str], movie_title: str) -> list[str]:
        return _translate_subtitle_lines_professionally(
            source_lines=source_lines,
            movie_title=movie_title,
            request_chat_completion=lambda system_prompt, user_payload: self._request_chat_completion(
                system_prompt=system_prompt,
                user_payload=user_payload,
            ),
        )

    def _request_chat_completion(self, *, system_prompt: str, user_payload: dict[str, object]) -> str:
        if self._request_chat_completion_func is not None:
            return self._request_chat_completion_func(system_prompt, user_payload)
        return _request_subtitle_chat_completion(
            api_key=self._api_key,
            base_url=self._base_url,
            model=self._model,
            timeout_seconds=self._timeout_seconds,
            proxy_url=self._proxy_url,
            system_prompt=system_prompt,
            user_payload=user_payload,
        )
