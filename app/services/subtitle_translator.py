from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.services.subtitle_translation_support import (
    _EmbeddedSubtitleStream,
    _SubtitleFile,
    _SubtitleCommandFailure,
    _build_professional_subtitle_translation_request,
    _build_subtitle_skip_result,
    _build_subtitle_translation_summary,
    _extract_embedded_subtitle_file_for_video,
    _extract_translations_from_response,
    _probe_embedded_subtitle_streams_for_video,
    _print_colored_error,
    _read_metadata_title,
    _request_subtitle_chat_completion,
    _translate_ass_subtitle_content,
    _resolve_embedded_subtitle_stream_selection,
    _resolve_external_subtitle_files,
    _resolve_target_subtitle_files,
    _read_subtitle_source_text,
    _resolve_translated_subtitle_content,
    _translate_srt_subtitle_content,
    _write_translated_subtitle_file,
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
        target_path = Path(translate_input.target_path).expanduser()
        if not target_path.exists():
            message = f"字幕翻译已跳过：导入目标不存在：{target_path}"
            return SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=True)

        subtitle_files, resolve_failure, skip_reason = _resolve_target_subtitle_files(
            target_path=target_path,
            resolve_video_subtitle_files=self._resolve_video_subtitle_files,
        )
        if resolve_failure is not None:
            return self._build_failed_result(
                problem=resolve_failure.problem,
                fix=resolve_failure.fix,
            )
        if subtitle_files is None:
            return self._build_skip_result(skip_reason=skip_reason or "none")

        if not self._api_key:
            message = "字幕翻译失败：缺少 SUBTITLE_TRANSLATION_API_KEY，无法进行专业级翻译。"
            _print_colored_error(
                problem=message,
                fix="在环境变量里配置 `SUBTITLE_TRANSLATION_API_KEY`，并确认网络可访问翻译接口。",
            )
            return SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=False)

        movie_title = _read_metadata_title(Path(translate_input.metadata_path))
        translated_count, error_result = self._translate_pending_subtitle_files(
            subtitle_files=subtitle_files,
            movie_title=movie_title,
        )
        if error_result is not None:
            return error_result
        return self._build_translation_summary_result(
            movie_title=movie_title,
            translated_count=translated_count,
        )

    def _resolve_video_subtitle_files(
        self,
        video_path: Path,
    ) -> tuple[list[_SubtitleFile], _SubtitleCommandFailure | None, str]:
        external_subtitle_files, skip_reason = _resolve_external_subtitle_files(video_path)
        if external_subtitle_files or skip_reason == "chinese_external":
            return external_subtitle_files, None, skip_reason

        streams, failure = self._probe_embedded_subtitle_streams(video_path)
        if failure is not None:
            return [], failure, "error"
        english_stream, skip_reason = _resolve_embedded_subtitle_stream_selection(streams)
        if english_stream is None:
            return [], None, skip_reason

        subtitle_file, failure = self._extract_embedded_subtitle_file(video_path=video_path, stream=english_stream)
        if failure is not None:
            return [], failure, "error"
        if subtitle_file is None:
            return [], None, "none"
        return [subtitle_file], None, skip_reason

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
        source_text, read_failure = _read_subtitle_source_text(subtitle_file.source_path)
        if read_failure is not None:
            return self._build_failed_result(
                problem=read_failure.problem,
                fix=read_failure.fix,
            )

        rendered_output, error_result = self._resolve_single_file_rendered_output(
            subtitle_file=subtitle_file,
            source_text=source_text,
            movie_title=movie_title,
        )
        if error_result is not None:
            return error_result

        write_failure = _write_translated_subtitle_file(
            output_path=subtitle_file.translated_path,
            rendered_output=rendered_output,
        )
        if write_failure is not None:
            return self._build_failed_result(
                problem=write_failure.problem,
                fix=write_failure.fix,
            )
        return SubtitleTranslateResult(success=True, message="ok", translated_count=1, skipped=False)

    def _resolve_single_file_rendered_output(
        self,
        *,
        subtitle_file: _SubtitleFile,
        source_text: str,
        movie_title: str,
    ) -> tuple[str | None, SubtitleTranslateResult | None]:
        rendered_output, error_message, translate_failure = _resolve_translated_subtitle_content(
            subtitle_file=subtitle_file,
            source_text=source_text,
            movie_title=movie_title,
            translate_srt=self._translate_srt_text,
            translate_ass=self._translate_ass_text,
        )
        if translate_failure is not None:
            return None, self._build_failed_result(
                problem=translate_failure.problem,
                fix=translate_failure.fix,
            )
        if rendered_output is None:
            return None, SubtitleTranslateResult(
                success=False,
                message=error_message or "字幕翻译失败。",
                translated_count=0,
                skipped=False,
            )
        return rendered_output, None

    def _build_failed_result(self, *, problem: str, fix: str) -> SubtitleTranslateResult:
        _print_colored_error(problem=problem, fix=fix)
        return SubtitleTranslateResult(
            success=False,
            message=problem,
            translated_count=0,
            skipped=False,
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

    def _build_skip_result(self, *, skip_reason: str) -> SubtitleTranslateResult:
        message, skipped = _build_subtitle_skip_result(skip_reason=skip_reason)
        return SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=skipped)

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
        return SubtitleTranslateResult(
            success=not skipped,
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
        system_prompt, user_payload = _build_professional_subtitle_translation_request(
            movie_title=movie_title,
            source_lines=source_lines,
        )

        response_text = self._request_chat_completion(
            system_prompt=system_prompt,
            user_payload=user_payload,
        )
        translations = _extract_translations_from_response(response_text)
        if len(translations) != len(source_lines):
            raise RuntimeError(
                f"翻译行数不一致（source={len(source_lines)}, translated={len(translations)}）"
            )
        return [line.strip() for line in translations]

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
