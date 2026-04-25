from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from app.services.subtitle_translation_support import (
    _EmbeddedSubtitleStream,
    _SubtitleFile,
    _SrtBlock,
    _build_embedded_subtitle_extract_command,
    _build_professional_subtitle_translation_request,
    _build_subtitle_file,
    _extract_translations_from_response,
    _find_adjacent_subtitle_paths,
    _find_video_files,
    _is_chinese_embedded_subtitle,
    _is_chinese_subtitle_path,
    _parse_ass_dialogue_lines,
    _parse_ffmpeg_subtitle_streams,
    _parse_ffprobe_subtitle_streams,
    _pick_extractable_english_embedded_subtitle,
    _parse_srt_blocks,
    _print_colored_error,
    _read_metadata_title,
    _render_ass_lines,
    _render_srt,
    _resolve_embedded_subtitle_output_path,
    _resolve_extracted_subtitle_file,
    _read_subtitle_source_text,
    _resolve_translated_subtitle_content,
    _run_subprocess_command,
    _translate_blocks_in_chunks,
    _translate_chunk_lines,
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

        subtitle_files, resolved_result = self._resolve_subtitle_files_for_translation(target_path)
        if resolved_result is not None:
            return resolved_result

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

    def _resolve_subtitle_files_for_translation(
        self,
        target_path: Path,
    ) -> tuple[list[_SubtitleFile], SubtitleTranslateResult | None]:
        if target_path.is_file():
            return self._resolve_single_video_subtitle_files(target_path)
        return self._resolve_directory_subtitle_files(target_path)

    def _resolve_single_video_subtitle_files(
        self,
        video_path: Path,
    ) -> tuple[list[_SubtitleFile], SubtitleTranslateResult | None]:
        subtitle_files, error_result, skip_reason = self._resolve_video_subtitle_files(video_path)
        if error_result is not None:
            return [], error_result
        if subtitle_files:
            return subtitle_files, None
        if skip_reason == "chinese_external":
            message = "字幕翻译已跳过：已检测到中文字幕外挂字幕。"
        elif skip_reason == "chinese_embedded":
            message = "字幕翻译已跳过：视频内已检测到中文字幕轨。"
        else:
            message = "字幕翻译已跳过：未找到可翻译的外挂字幕或英文内嵌字幕。"
        return [], SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=True)

    def _resolve_directory_subtitle_files(
        self,
        target_path: Path,
    ) -> tuple[list[_SubtitleFile], SubtitleTranslateResult | None]:
        video_files = _find_video_files(target_path)
        if not video_files:
            message = "字幕翻译已跳过：未找到可翻译的外挂字幕或英文内嵌字幕。"
            return [], SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=True)

        subtitle_files: list[_SubtitleFile] = []
        for video_path in video_files:
            video_subtitle_files, error_result, _ = self._resolve_video_subtitle_files(video_path)
            if error_result is not None:
                return [], error_result
            subtitle_files.extend(video_subtitle_files)

        if subtitle_files:
            return subtitle_files, None

        message = "字幕翻译已跳过：未找到可翻译的外挂字幕或英文内嵌字幕。"
        return [], SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=True)

    def _resolve_video_subtitle_files(
        self,
        video_path: Path,
    ) -> tuple[list[_SubtitleFile], SubtitleTranslateResult | None, str]:
        external_subtitle_paths = _find_adjacent_subtitle_paths(video_path)
        external_subtitle_files = [
            subtitle_file
            for path in external_subtitle_paths
            if (subtitle_file := _build_subtitle_file(path)) is not None
        ]
        if external_subtitle_files:
            return external_subtitle_files, None, "external"
        if any(_is_chinese_subtitle_path(path) for path in external_subtitle_paths):
            return [], None, "chinese_external"

        streams, error_result = self._probe_embedded_subtitles(video_path)
        if error_result is not None:
            return [], error_result, "error"
        if any(_is_chinese_embedded_subtitle(stream) for stream in streams):
            return [], None, "chinese_embedded"

        english_stream = _pick_extractable_english_embedded_subtitle(streams)
        if english_stream is None:
            return [], None, "none"

        subtitle_file, error_result = self._extract_embedded_subtitle_file(video_path=video_path, stream=english_stream)
        if error_result is not None:
            return [], error_result, "error"
        if subtitle_file is None:
            return [], None, "none"
        return [subtitle_file], None, "embedded"

    def _probe_embedded_subtitles(
        self,
        video_path: Path,
    ) -> tuple[list[_EmbeddedSubtitleStream], SubtitleTranslateResult | None]:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "s",
            "-show_entries",
            "stream=index,codec_name:stream_tags=language,title",
            "-of",
            "json",
            str(video_path),
        ]
        completed, failure = _run_subprocess_command(
            command=command,
            timeout_seconds=self._timeout_seconds,
            missing_problem=f"字幕翻译失败：系统缺少 ffprobe，无法检查内嵌字幕：{video_path}",
            missing_fix="安装 `ffprobe`（通常随 `ffmpeg` 一起提供）并确保命令在 PATH；如果只依赖外挂字幕，先确认同名 `.srt/.ass` 已随导入进入库目录。",
            timeout_problem=f"字幕翻译失败：检查内嵌字幕超时：{video_path}",
            timeout_fix="检查视频文件是否可读、体积是否异常，以及 `ffprobe` 是否可正常执行。",
        )
        if failure is not None:
            if failure.reason == "missing":
                return self._probe_embedded_subtitles_with_ffmpeg(video_path)
            _print_colored_error(problem=failure.problem, fix=failure.fix)
            return [], SubtitleTranslateResult(success=False, message=failure.problem, translated_count=0, skipped=False)

        if completed.returncode != 0:
            problem = completed.stderr.strip() or completed.stdout.strip() or f"exit={completed.returncode}"
            message = f"字幕翻译失败：检查内嵌字幕失败：{video_path}，原因：{problem}"
            _print_colored_error(
                problem=message,
                fix="确认视频文件未损坏，并检查 `ffprobe` 是否能读取该视频的字幕流信息。",
            )
            return [], SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=False)

        try:
            streams = _parse_ffprobe_subtitle_streams(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            message = f"字幕翻译失败：ffprobe 输出不是有效 JSON：{video_path}，原因：{exc}"
            _print_colored_error(
                problem=message,
                fix="检查 `ffprobe` 输出是否被外部 wrapper 改写，确保它返回标准 JSON。",
            )
            return [], SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=False)
        return streams, None

    def _probe_embedded_subtitles_with_ffmpeg(
        self,
        video_path: Path,
    ) -> tuple[list[_EmbeddedSubtitleStream], SubtitleTranslateResult | None]:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(video_path),
        ]
        completed, failure = _run_subprocess_command(
            command=command,
            timeout_seconds=self._timeout_seconds,
            missing_problem=f"字幕翻译失败：系统缺少 ffprobe/ffmpeg，无法检查内嵌字幕：{video_path}",
            missing_fix="安装 `ffmpeg`（如能一并安装 `ffprobe` 更好）并确保命令在 PATH；如果只依赖外挂字幕，先确认同名 `.srt/.ass` 已随导入进入库目录。",
            timeout_problem=f"字幕翻译失败：检查内嵌字幕超时：{video_path}",
            timeout_fix="检查视频文件是否可读、体积是否异常，以及 `ffmpeg` 是否可正常执行。",
        )
        if failure is not None:
            _print_colored_error(problem=failure.problem, fix=failure.fix)
            return [], SubtitleTranslateResult(success=False, message=failure.problem, translated_count=0, skipped=False)

        parsed_streams = _parse_ffmpeg_subtitle_streams(completed.stderr or completed.stdout or "")
        return parsed_streams, None

    def _extract_embedded_subtitle_file(
        self,
        *,
        video_path: Path,
        stream: _EmbeddedSubtitleStream,
    ) -> tuple[_SubtitleFile | None, SubtitleTranslateResult | None]:
        output_path = _resolve_embedded_subtitle_output_path(
            video_path=video_path,
            codec_name=stream.codec_name,
        )
        if output_path is None:
            return None, None
        command = _build_embedded_subtitle_extract_command(
            video_path=video_path,
            stream_index=stream.stream_index,
            output_path=output_path,
        )
        completed, failure = _run_subprocess_command(
            command=command,
            timeout_seconds=self._timeout_seconds,
            missing_problem=f"字幕翻译失败：系统缺少 ffmpeg，无法提取英文内嵌字幕：{video_path}",
            missing_fix="安装 `ffmpeg` 并确保命令在 PATH；如果只依赖外挂字幕，先确认同名 `.srt/.ass` 已随导入进入库目录。",
            timeout_problem=f"字幕翻译失败：提取英文内嵌字幕超时：{video_path}",
            timeout_fix="检查视频文件是否可读、体积是否异常，以及 `ffmpeg` 是否可正常抽取字幕流。",
        )
        if failure is not None:
            _print_colored_error(problem=failure.problem, fix=failure.fix)
            return None, SubtitleTranslateResult(success=False, message=failure.problem, translated_count=0, skipped=False)

        if completed.returncode != 0:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            problem = completed.stderr.strip() or completed.stdout.strip() or f"exit={completed.returncode}"
            message = f"字幕翻译失败：提取英文内嵌字幕失败：{video_path}，原因：{problem}"
            _print_colored_error(
                problem=message,
                fix="确认视频里确实有可提取的英文文本字幕流；若是图片字幕（PGS/VobSub），当前不会自动 OCR 翻译。",
            )
            return None, SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=False)

        subtitle_file, output_failure = _resolve_extracted_subtitle_file(output_path)
        if output_failure is not None:
            _print_colored_error(problem=output_failure.problem, fix=output_failure.fix)
            return None, SubtitleTranslateResult(
                success=False,
                message=output_failure.problem,
                translated_count=0,
                skipped=False,
            )
        return subtitle_file, None

    def _translate_single_file(
        self,
        *,
        subtitle_file: _SubtitleFile,
        movie_title: str,
    ) -> SubtitleTranslateResult:
        source_text, read_failure = _read_subtitle_source_text(subtitle_file.source_path)
        if read_failure is not None:
            _print_colored_error(problem=read_failure.problem, fix=read_failure.fix)
            return SubtitleTranslateResult(
                success=False,
                message=read_failure.problem,
                translated_count=0,
                skipped=False,
            )

        rendered_output, error_message, translate_failure = _resolve_translated_subtitle_content(
            subtitle_file=subtitle_file,
            source_text=source_text,
            movie_title=movie_title,
            translate_srt=self._translate_srt_text,
            translate_ass=self._translate_ass_text,
        )
        if translate_failure is not None:
            _print_colored_error(
                problem=translate_failure.problem,
                fix=translate_failure.fix,
            )
            return SubtitleTranslateResult(
                success=False,
                message=translate_failure.problem,
                translated_count=0,
                skipped=False,
            )

        if rendered_output is None:
            return SubtitleTranslateResult(
                success=False,
                message=error_message or "字幕翻译失败。",
                translated_count=0,
                skipped=False,
            )

        write_failure = _write_translated_subtitle_file(
            output_path=subtitle_file.translated_path,
            rendered_output=rendered_output,
        )
        if write_failure is not None:
            _print_colored_error(problem=write_failure.problem, fix=write_failure.fix)
            return SubtitleTranslateResult(
                success=False,
                message=write_failure.problem,
                translated_count=0,
                skipped=False,
            )
        return SubtitleTranslateResult(success=True, message="ok", translated_count=1, skipped=False)

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
        if translated_count <= 0:
            message = "字幕翻译已跳过：目标中文字幕文件已存在。"
            return SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=True)

        if movie_title:
            message = f"字幕翻译成功：{movie_title}，已生成 {translated_count} 个字幕文件。"
        else:
            message = f"字幕翻译成功：已生成 {translated_count} 个字幕文件。"
        return SubtitleTranslateResult(
            success=True,
            message=message,
            translated_count=translated_count,
            skipped=False,
        )

    def _translate_srt_text(
        self,
        *,
        source_text: str,
        movie_title: str,
        subtitle_path: Path,
    ) -> tuple[str | None, str | None]:
        blocks = _parse_srt_blocks(source_text)
        if not blocks:
            message = f"字幕翻译失败：{subtitle_path} 不是有效 SRT 或内容为空。"
            _print_colored_error(
                problem=message,
                fix="确认字幕是标准 SubRip(.srt) 格式，包含序号、时间轴和文本。",
            )
            return None, message

        translated_blocks, error_message = _translate_blocks_in_chunks(
            blocks=blocks,
            size=60,
            get_source_text=lambda block: block.text,
            translate_chunk=lambda source_lines: _translate_chunk_lines(
                source_lines=source_lines,
                subtitle_path=subtitle_path,
                translate_lines=lambda lines: self._translate_lines_professional(
                    source_lines=lines,
                    movie_title=movie_title,
                ),
            ),
            build_output_block=lambda block, translated_text: _SrtBlock(
                index=block.index,
                timecode=block.timecode,
                text=translated_text,
            ),
        )
        if translated_blocks is None:
            return None, error_message
        return _render_srt(translated_blocks), None

    def _translate_ass_text(
        self,
        *,
        source_text: str,
        movie_title: str,
        subtitle_path: Path,
    ) -> tuple[str | None, str | None]:
        lines, dialogue_lines = _parse_ass_dialogue_lines(source_text)
        if not dialogue_lines:
            message = f"字幕翻译失败：{subtitle_path} 不是有效 ASS 或没有可翻译对话。"
            _print_colored_error(
                problem=message,
                fix="确认字幕是标准 Advanced SubStation Alpha(.ass) 文件，包含 `[Script Info]` 和 `Dialogue:` 行。",
            )
            return None, message

        translated_lines, error_message = _translate_blocks_in_chunks(
            blocks=dialogue_lines,
            size=60,
            get_source_text=lambda line: line.text,
            translate_chunk=lambda source_lines: _translate_chunk_lines(
                source_lines=source_lines,
                subtitle_path=subtitle_path,
                translate_lines=lambda lines: self._translate_lines_professional(
                    source_lines=lines,
                    movie_title=movie_title,
                ),
            ),
            build_output_block=lambda _, translated_text: translated_text,
        )
        if translated_lines is None:
            return None, error_message
        for dialogue_line, translated_text in zip(dialogue_lines, translated_lines):
            lines[dialogue_line.line_index] = dialogue_line.prefix + translated_text
        return _render_ass_lines(lines, had_trailing_newline=source_text.endswith(("\n", "\r"))), None

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
        payload = {
            "model": self._model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._timeout_seconds, proxy=self._proxy_url or None) as client:
            response = client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError(f"响应不是 JSON：{exc}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError(f"响应缺少 content 字段：{exc}") from exc
        text = str(content).strip()
        if not text:
            raise RuntimeError("模型返回空内容。")
        return text
