from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import httpx

from app.operational_logging import emit_operational_log


@dataclass(frozen=True, slots=True)
class _SrtBlock:
    index: str
    timecode: str
    text: str


@dataclass(frozen=True, slots=True)
class _SubtitleFile:
    source_path: Path
    translated_path: Path
    kind: str


@dataclass(frozen=True, slots=True)
class _AssDialogueLine:
    line_index: int
    prefix: str
    text: str


@dataclass(frozen=True, slots=True)
class _EmbeddedSubtitleStream:
    stream_index: int
    codec_name: str
    language: str
    title: str


@dataclass(frozen=True, slots=True)
class _SubtitleCommandFailure:
    reason: str
    problem: str
    fix: str


@dataclass(frozen=True, slots=True)
class _SubtitleImportPreparationFailure:
    message: str
    skipped: bool
    fix: str = ""


@dataclass(frozen=True, slots=True)
class _SubtitleImportTranslationPlan:
    subtitle_files: list[_SubtitleFile]
    movie_title: str
    trusted_name_map: dict[str, str]


_VIDEO_FILE_SUFFIXES = frozenset({".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".ts", ".m2ts", ".webm"})
_SUBTITLE_FILE_SUFFIXES = (".srt", ".ass")
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_FFMPEG_DIR = _REPO_ROOT / ".tools" / "ffmpeg"
_BILINGUAL_ASS_OUTPUT_SUFFIX = ".dual.ass"
_BILINGUAL_ASS_FONT_FAMILY = "LXGW WenKai"
_BILINGUAL_ASS_CHINESE_FONT_SIZE = 44
_BILINGUAL_ASS_ENGLISH_FONT_SIZE = 24
_EMBEDDED_SUBTITLE_OUTPUT_SUFFIX = {
    "ass": ".ass",
    "mov_text": ".srt",
    "ssa": ".ass",
    "subrip": ".srt",
    "srt": ".srt",
    "webvtt": ".srt",
}
_CHINESE_SUBTITLE_TOKENS = frozenset(
    {
        "chi",
        "chinese",
        "chs",
        "cht",
        "cn",
        "sc",
        "tc",
        "zh",
        "zho",
        "中英",
        "中文",
        "中文字幕",
        "双语",
        "中字",
        "简中",
        "简体中文",
        "繁中",
        "繁体中文",
    }
)
_CHINESE_SUBTITLE_SUBSTRINGS = ("中英", "中文", "中文字幕", "双语", "简中", "繁中", "简体中文", "繁体中文")
_ENGLISH_SUBTITLE_TOKENS = frozenset({"en", "eng", "english", "英文", "英字"})
_ENGLISH_SUBTITLE_SUBSTRINGS = ("english", "英文", "英字")

_ChunkItem = TypeVar("_ChunkItem")
_TranslatedChunkItem = TypeVar("_TranslatedChunkItem")


def _find_all_subtitle_paths(target_path: Path) -> list[Path]:
    if target_path.is_file():
        return _find_adjacent_subtitle_paths(target_path)

    if not target_path.is_dir():
        return []

    return sorted(candidate for pattern in _SUBTITLE_FILE_SUFFIXES for candidate in target_path.rglob(f"*{pattern}"))


def _find_adjacent_subtitle_paths(target_path: Path) -> list[Path]:
    if not target_path.exists() or not target_path.is_file():
        return []
    subtitle_paths: list[Path] = []
    for candidate in sorted(target_path.parent.iterdir()):
        if candidate == target_path or not candidate.is_file():
            continue
        if _extract_adjacent_subtitle_suffix(target_path=target_path, subtitle_path=candidate) is None:
            continue
        subtitle_paths.append(candidate)
    return subtitle_paths


def _extract_adjacent_subtitle_suffix(*, target_path: Path, subtitle_path: Path) -> str | None:
    target_stem = target_path.stem
    candidate_name = subtitle_path.name
    lowered_name = candidate_name.lower()
    for suffix in _SUBTITLE_FILE_SUFFIXES:
        if not lowered_name.endswith(suffix):
            continue
        subtitle_stem = candidate_name[: -len(suffix)]
        if subtitle_stem == target_stem:
            return candidate_name[len(target_stem) :]
        if subtitle_stem.startswith(f"{target_stem}."):
            return candidate_name[len(target_stem) :]
    return None


def _build_subtitle_file(path: Path) -> _SubtitleFile | None:
    if not path.exists() or not path.is_file():
        return None
    if path.name.lower().endswith(_BILINGUAL_ASS_OUTPUT_SUFFIX):
        return None
    if _is_chinese_subtitle_path(path):
        return None
    suffix = path.suffix.lower()
    if suffix == ".srt":
        return _SubtitleFile(source_path=path, translated_path=path.with_suffix(".zh.srt"), kind="srt")
    if suffix == ".ass":
        return _SubtitleFile(source_path=path, translated_path=path.with_suffix(".zh.ass"), kind="ass")
    return None


def _resolve_external_subtitle_files(video_path: Path) -> tuple[list[_SubtitleFile], str]:
    external_subtitle_paths = _find_adjacent_subtitle_paths(video_path)
    external_subtitle_files = [
        subtitle_file
        for path in external_subtitle_paths
        if (subtitle_file := _build_subtitle_file(path)) is not None
    ]
    if external_subtitle_files:
        return external_subtitle_files, "external"
    if any(_is_chinese_subtitle_path(path) for path in external_subtitle_paths):
        return [], "chinese_external"
    return [], "none"


def _resolve_embedded_subtitle_output_path(
    *,
    video_path: Path,
    codec_name: str,
) -> Path | None:
    output_suffix = _EMBEDDED_SUBTITLE_OUTPUT_SUFFIX.get(codec_name.casefold())
    if not output_suffix:
        return None
    return video_path.with_suffix(output_suffix)


def _build_embedded_subtitle_extract_command(
    *,
    video_path: Path,
    stream_index: int,
    output_path: Path,
) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-map",
        f"0:{stream_index}",
        "-c:s",
        "ass" if output_path.suffix.lower() == ".ass" else "srt",
        str(output_path),
    ]


def _resolve_extracted_subtitle_file(output_path: Path) -> tuple[_SubtitleFile | None, _SubtitleCommandFailure | None]:
    subtitle_file = _build_subtitle_file(output_path)
    if subtitle_file is not None:
        return subtitle_file, None
    return None, _SubtitleCommandFailure(
        reason="invalid_output",
        problem=f"字幕翻译失败：提取后的字幕文件不可用：{output_path}",
        fix="检查提取结果是否仍是 `.srt/.ass`，并确认未被已有中文字幕命名规则过滤。",
    )


def _resolve_embedded_subtitle_extract_result(
    *,
    video_path: Path,
    output_path: Path,
    returncode: int,
    stdout: str,
    stderr: str,
) -> tuple[_SubtitleFile | None, _SubtitleCommandFailure | None]:
    if returncode != 0:
        output_path.unlink(missing_ok=True)
        problem = stderr.strip() or stdout.strip() or f"exit={returncode}"
        return None, _SubtitleCommandFailure(
            reason="extract_failed",
            problem=f"字幕翻译失败：提取英文内嵌字幕失败：{video_path}，原因：{problem}",
            fix="确认视频里确实有可提取的英文文本字幕流；若是图片字幕（PGS/VobSub），当前不会自动 OCR 翻译。",
    )
    return _resolve_extracted_subtitle_file(output_path)


def _extract_embedded_subtitle_file_for_video(
    *,
    video_path: Path,
    stream: _EmbeddedSubtitleStream,
    timeout_seconds: float,
) -> tuple[_SubtitleFile | None, _SubtitleCommandFailure | None]:
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
        timeout_seconds=timeout_seconds,
        missing_problem=f"字幕翻译失败：系统缺少 ffmpeg，无法提取英文内嵌字幕：{video_path}",
        missing_fix="安装 `ffmpeg` 并确保命令在 PATH；如果只依赖外挂字幕，先确认同名 `.srt/.ass` 已随导入进入库目录。",
        timeout_problem=f"字幕翻译失败：提取英文内嵌字幕超时：{video_path}",
        timeout_fix="检查视频文件是否可读、体积是否异常，以及 `ffmpeg` 是否可正常抽取字幕流。",
    )
    if failure is not None:
        return None, failure

    return _resolve_embedded_subtitle_extract_result(
        video_path=video_path,
        output_path=output_path,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def _read_subtitle_source_text(source_path: Path) -> tuple[str | None, _SubtitleCommandFailure | None]:
    try:
        return source_path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeError) as exc:
        return None, _SubtitleCommandFailure(
            reason="read_source",
            problem=f"读取字幕文件失败：{source_path}，原因：{exc}",
            fix="确认字幕是 UTF-8 编码，必要时先转码后再重试。",
        )


def _write_translated_subtitle_file(
    *,
    output_path: Path,
    rendered_output: str,
) -> _SubtitleCommandFailure | None:
    try:
        output_path.write_text(rendered_output, encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return _SubtitleCommandFailure(
            reason="write_output",
            problem=f"写入字幕文件失败：{output_path}，原因：{exc}",
            fix="检查导入目录写权限和磁盘空间，再重试 confirm 导入。",
        )
    return None


def _translate_single_subtitle_file(
    *,
    subtitle_file: _SubtitleFile,
    movie_title: str,
    translate_srt: Callable[[str, str, Path], tuple[str | None, str | None]],
    translate_ass: Callable[[str, str, Path], tuple[str | None, str | None]],
) -> tuple[bool, str | None, _SubtitleCommandFailure | None]:
    source_text, read_failure = _read_subtitle_source_text(subtitle_file.source_path)
    if read_failure is not None:
        return False, None, read_failure

    rendered_output, error_message, translate_failure = _resolve_translated_subtitle_content(
        subtitle_file=subtitle_file,
        source_text=source_text,
        movie_title=movie_title,
        translate_srt=translate_srt,
        translate_ass=translate_ass,
    )
    if translate_failure is not None:
        return False, None, translate_failure
    if rendered_output is None:
        return False, error_message or "字幕翻译失败。", None

    write_failure = _write_translated_subtitle_file(
        output_path=subtitle_file.translated_path,
        rendered_output=rendered_output,
    )
    if write_failure is not None:
        return False, None, write_failure
    return True, None, None


def _build_professional_subtitle_translation_request(
    *,
    movie_title: str,
    source_lines: list[str],
    trusted_name_map: dict[str, str],
) -> tuple[str, dict[str, object]]:
    system_prompt = (
        "你是专业影视字幕译者。任务：把英文字幕逐行翻译为简体中文。"
        "必须保留每行语气、语境、人物关系，不要删减信息，不要总结。"
        "脏话、双关、俚语要自然等价翻译。"
        "译文必须像能直接观看的中文字幕：简洁、口语化、少书面腔，不要解释性扩写。"
        "如果 `trusted_name_map` 给出了人名/角色名的可信中文写法，必须严格使用并保持一致。"
        "如果遇到影视人名而 `trusted_name_map` 没给出可靠中文名，优先保留原文，不要擅自音译或编造常用译名。"
        "必须保持一行源文对应一行译文，返回严格 JSON。"
    )
    user_payload: dict[str, object] = {
        "movie_title": movie_title,
        "source_lines": source_lines,
        "trusted_name_map": trusted_name_map,
        "rules": {
            "target_language": "zh-CN",
            "style": "专业影视字幕",
            "dialogue_tone": "自然口语、适合直接观看的中文字幕",
            "proper_noun_policy": "trusted-name-map-first, otherwise keep unresolved film-tv names in original form",
            "return_json_only": True,
            "json_schema": {"translations": ["与 source_lines 等长的中文字符串数组"]},
        },
    }
    return system_prompt, user_payload


def _translate_subtitle_lines_professionally(
    *,
    source_lines: list[str],
    movie_title: str,
    trusted_name_map: dict[str, str],
    request_chat_completion: Callable[[str, dict[str, object]], str],
) -> list[str]:
    system_prompt, user_payload = _build_professional_subtitle_translation_request(
        movie_title=movie_title,
        source_lines=source_lines,
        trusted_name_map=trusted_name_map,
    )
    response_text = request_chat_completion(system_prompt, user_payload)
    translations = _extract_translations_from_response(response_text)
    if len(translations) != len(source_lines):
        raise RuntimeError(
            f"翻译行数不一致（source={len(source_lines)}, translated={len(translations)}）"
        )
    return [line.strip() for line in translations]


def _build_subtitle_skip_result(*, skip_reason: str) -> tuple[str, bool]:
    if skip_reason == "chinese_external":
        return "字幕翻译已跳过：已检测到中文字幕外挂字幕。", True
    if skip_reason == "chinese_embedded":
        return "字幕翻译已跳过：视频内已检测到中文字幕轨。", True
    return "字幕翻译已跳过：未找到可翻译的外挂字幕或英文内嵌字幕。", True


def _resolve_directory_skip_reason(skip_reasons: list[str]) -> str:
    if skip_reasons and all(reason == "chinese_external" for reason in skip_reasons):
        return "chinese_external"
    if skip_reasons and all(reason == "chinese_embedded" for reason in skip_reasons):
        return "chinese_embedded"
    return "none"


def _build_subtitle_translation_summary(
    *,
    movie_title: str,
    translated_count: int,
) -> tuple[str, bool]:
    if translated_count <= 0:
        return "字幕翻译已跳过：目标中文字幕文件已存在。", True
    if movie_title:
        return f"字幕翻译成功：{movie_title}，已生成 {translated_count} 个字幕文件。", False
    return f"字幕翻译成功：已生成 {translated_count} 个字幕文件。", False


def _extract_chat_completion_response_text(body: dict[str, object]) -> str:
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"响应缺少 content 字段：{exc}") from exc
    text = str(content).strip()
    if not text:
        raise RuntimeError("模型返回空内容。")
    return text


def _request_subtitle_chat_completion(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout_seconds: float,
    proxy_url: str,
    system_prompt: str,
    user_payload: dict[str, object],
) -> str:
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=timeout_seconds, proxy=proxy_url or None) as client:
            response = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"请求超时：{exc}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"请求失败：{exc}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(f"响应不是 JSON：{exc}") from exc
    return _extract_chat_completion_response_text(body)


def _resolve_translated_subtitle_content(
    *,
    subtitle_file: _SubtitleFile,
    source_text: str,
    movie_title: str,
    translate_srt: Callable[[str, str, Path], tuple[str | None, str | None]],
    translate_ass: Callable[[str, str, Path], tuple[str | None, str | None]],
) -> tuple[str | None, str | None, _SubtitleCommandFailure | None]:
    if subtitle_file.kind == "srt":
        rendered_output, error_message = translate_srt(
            source_text=source_text,
            movie_title=movie_title,
            subtitle_path=subtitle_file.source_path,
        )
        return rendered_output, error_message, None
    if subtitle_file.kind == "ass":
        rendered_output, error_message = translate_ass(
            source_text=source_text,
            movie_title=movie_title,
            subtitle_path=subtitle_file.source_path,
        )
        return rendered_output, error_message, None
    return None, None, _SubtitleCommandFailure(
        reason="unsupported_kind",
        problem=f"字幕翻译失败：暂不支持的字幕格式：{subtitle_file.source_path}",
        fix="确认字幕是 `.srt` 或 `.ass` 文件，再重试导入。",
    )


def _find_video_files(target_path: Path) -> list[Path]:
    if target_path.is_file():
        return [target_path] if target_path.suffix.lower() in _VIDEO_FILE_SUFFIXES else []
    if not target_path.is_dir():
        return []
    return sorted(candidate for candidate in target_path.rglob("*") if candidate.is_file() and candidate.suffix.lower() in _VIDEO_FILE_SUFFIXES)


def _resolve_target_subtitle_files(
    *,
    target_path: Path,
    resolve_video_subtitle_files: Callable[[Path], tuple[list[_SubtitleFile], _SubtitleCommandFailure | None, str]],
) -> tuple[list[_SubtitleFile] | None, _SubtitleCommandFailure | None, str | None]:
    if target_path.is_file():
        subtitle_files, failure, skip_reason = resolve_video_subtitle_files(target_path)
        if failure is not None:
            return None, failure, None
        if subtitle_files:
            return subtitle_files, None, None
        return None, None, skip_reason

    video_files = _find_video_files(target_path)
    if not video_files:
        return None, None, "none"

    subtitle_files: list[_SubtitleFile] = []
    skip_reasons: list[str] = []
    for video_path in video_files:
        video_subtitle_files, failure, skip_reason = resolve_video_subtitle_files(video_path)
        if failure is not None:
            return None, failure, None
        subtitle_files.extend(video_subtitle_files)
        skip_reasons.append(skip_reason)

    if subtitle_files:
        return subtitle_files, None, None
    return None, None, _resolve_directory_skip_reason(skip_reasons)


def _prepare_subtitle_translation_for_import(
    *,
    target_path: Path,
    metadata_path: Path,
    api_key: str,
    resolve_video_subtitle_files: Callable[[Path], tuple[list[_SubtitleFile], _SubtitleCommandFailure | None, str]],
    read_metadata_title: Callable[[Path], str],
) -> tuple[_SubtitleImportTranslationPlan | None, _SubtitleImportPreparationFailure | None]:
    if not target_path.exists():
        return None, _SubtitleImportPreparationFailure(
            message=f"字幕翻译已跳过：导入目标不存在：{target_path}",
            skipped=True,
        )

    subtitle_files, resolve_failure, skip_reason = _resolve_target_subtitle_files(
        target_path=target_path,
        resolve_video_subtitle_files=resolve_video_subtitle_files,
    )
    if resolve_failure is not None:
        return None, _SubtitleImportPreparationFailure(
            message=resolve_failure.problem,
            skipped=False,
            fix=resolve_failure.fix,
        )
    if subtitle_files is None:
        message, skipped = _build_subtitle_skip_result(skip_reason=skip_reason or "none")
        return None, _SubtitleImportPreparationFailure(message=message, skipped=skipped)

    if not api_key:
        return None, _SubtitleImportPreparationFailure(
            message="字幕翻译失败：缺少 SUBTITLE_TRANSLATION_API_KEY，无法进行专业级翻译。",
            skipped=False,
            fix="在环境变量里配置 `SUBTITLE_TRANSLATION_API_KEY`，并确认网络可访问翻译接口。",
        )

    return _SubtitleImportTranslationPlan(
        subtitle_files=subtitle_files,
        movie_title=read_metadata_title(metadata_path),
        trusted_name_map=_read_metadata_trusted_name_map(metadata_path),
    ), None


def _resolve_video_subtitle_files_for_import(
    *,
    video_path: Path,
    probe_embedded_subtitle_streams: Callable[[Path], tuple[list[_EmbeddedSubtitleStream], _SubtitleCommandFailure | None]],
    extract_embedded_subtitle_file: Callable[
        [_EmbeddedSubtitleStream, Path],
        tuple[_SubtitleFile | None, _SubtitleCommandFailure | None],
    ],
) -> tuple[list[_SubtitleFile], _SubtitleCommandFailure | None, str]:
    external_subtitle_files, skip_reason = _resolve_external_subtitle_files(video_path)
    if external_subtitle_files or skip_reason == "chinese_external":
        return external_subtitle_files, None, skip_reason

    streams, failure = probe_embedded_subtitle_streams(video_path)
    if failure is not None:
        return [], failure, "error"
    english_stream, skip_reason = _resolve_embedded_subtitle_stream_selection(streams)
    if english_stream is None:
        return [], None, skip_reason

    subtitle_file, failure = extract_embedded_subtitle_file(english_stream, video_path)
    if failure is not None:
        return [], failure, "error"
    if subtitle_file is None:
        return [], None, "none"
    return [subtitle_file], None, skip_reason


def _is_chinese_subtitle_path(path: Path) -> bool:
    return _looks_like_chinese_subtitle_label(path.name)


def _is_chinese_embedded_subtitle(stream: _EmbeddedSubtitleStream) -> bool:
    return _looks_like_chinese_subtitle_label(f"{stream.language} {stream.title}")


def _is_english_embedded_subtitle(stream: _EmbeddedSubtitleStream) -> bool:
    return _looks_like_english_subtitle_label(f"{stream.language} {stream.title}")


def _pick_extractable_english_embedded_subtitle(
    streams: list[_EmbeddedSubtitleStream],
) -> _EmbeddedSubtitleStream | None:
    return next(
        (
            stream
            for stream in streams
            if _is_english_embedded_subtitle(stream)
            and stream.codec_name.casefold() in _EMBEDDED_SUBTITLE_OUTPUT_SUFFIX
        ),
        None,
    )


def _resolve_embedded_subtitle_stream_selection(
    streams: list[_EmbeddedSubtitleStream],
) -> tuple[_EmbeddedSubtitleStream | None, str]:
    if any(_is_chinese_embedded_subtitle(stream) for stream in streams):
        return None, "chinese_embedded"
    english_stream = _pick_extractable_english_embedded_subtitle(streams)
    if english_stream is None:
        return None, "none"
    return english_stream, "embedded"


def _looks_like_chinese_subtitle_label(value: str) -> bool:
    normalized = _normalize_subtitle_label(value)
    if not normalized:
        return False
    if any(marker in normalized for marker in _CHINESE_SUBTITLE_SUBSTRINGS):
        return True
    return bool(set(normalized.split()) & _CHINESE_SUBTITLE_TOKENS)


def _looks_like_english_subtitle_label(value: str) -> bool:
    normalized = _normalize_subtitle_label(value)
    if not normalized or _looks_like_chinese_subtitle_label(value):
        return False
    if any(marker in normalized for marker in _ENGLISH_SUBTITLE_SUBSTRINGS):
        return True
    return bool(set(normalized.split()) & _ENGLISH_SUBTITLE_TOKENS)


def _normalize_subtitle_label(value: str) -> str:
    cleaned = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", value.casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_ffmpeg_subtitle_streams(output_text: str) -> list[_EmbeddedSubtitleStream]:
    streams: list[_EmbeddedSubtitleStream] = []
    pattern = re.compile(
        r"Stream #\d+:(?P<index>\d+)(?:\((?P<language>[^)]+)\))?: Subtitle: (?P<codec>[A-Za-z0-9_]+)",
        re.IGNORECASE,
    )
    for line in output_text.splitlines():
        match = pattern.search(line)
        if match is None:
            continue
        try:
            stream_index = int(match.group("index"))
        except (TypeError, ValueError):
            continue
        streams.append(
            _EmbeddedSubtitleStream(
                stream_index=stream_index,
                codec_name=str(match.group("codec") or "").strip(),
                language=str(match.group("language") or "").strip(),
                title="",
            )
        )
    return streams


def _resolve_ffmpeg_subtitle_streams(
    *,
    output_text: str,
) -> list[_EmbeddedSubtitleStream]:
    return _parse_ffmpeg_subtitle_streams(output_text)


def _parse_ffprobe_subtitle_streams(payload_text: str) -> list[_EmbeddedSubtitleStream]:
    payload = json.loads(payload_text or "{}")
    streams = payload.get("streams", [])
    if not isinstance(streams, list):
        return []

    result: list[_EmbeddedSubtitleStream] = []
    for item in streams:
        if not isinstance(item, dict):
            continue
        tags = item.get("tags", {})
        if not isinstance(tags, dict):
            tags = {}
        try:
            stream_index = int(item.get("index", -1))
        except (TypeError, ValueError):
            stream_index = -1
        if stream_index < 0:
            continue
        result.append(
            _EmbeddedSubtitleStream(
                stream_index=stream_index,
                codec_name=str(item.get("codec_name", "")).strip(),
                language=str(tags.get("language", "")).strip(),
                title=str(tags.get("title", "")).strip(),
            )
        )
    return result


def _resolve_ffprobe_subtitle_streams(
    *,
    video_path: Path,
    returncode: int,
    stdout: str,
    stderr: str,
) -> tuple[list[_EmbeddedSubtitleStream] | None, _SubtitleCommandFailure | None]:
    if returncode != 0:
        problem = stderr.strip() or stdout.strip() or f"exit={returncode}"
        return None, _SubtitleCommandFailure(
            reason="ffprobe_failed",
            problem=f"字幕翻译失败：检查内嵌字幕失败：{video_path}，原因：{problem}",
            fix="确认视频文件未损坏，并检查 `ffprobe` 是否能读取该视频的字幕流信息。",
        )
    try:
        return _parse_ffprobe_subtitle_streams(stdout or "{}"), None
    except json.JSONDecodeError as exc:
        return None, _SubtitleCommandFailure(
            reason="ffprobe_invalid_json",
            problem=f"字幕翻译失败：ffprobe 输出不是有效 JSON：{video_path}，原因：{exc}",
            fix="检查 `ffprobe` 输出是否被外部 wrapper 改写，确保它返回标准 JSON。",
        )


def _probe_embedded_subtitle_streams_for_video(
    *,
    video_path: Path,
    timeout_seconds: float,
) -> tuple[list[_EmbeddedSubtitleStream], _SubtitleCommandFailure | None]:
    command = [
        _resolve_local_ffmpeg_command("ffprobe"),
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
        timeout_seconds=timeout_seconds,
        missing_problem=f"字幕翻译失败：系统缺少 ffprobe，无法检查内嵌字幕：{video_path}",
        missing_fix="安装 `ffprobe`（通常随 `ffmpeg` 一起提供）并确保命令在 PATH；如果只依赖外挂字幕，先确认同名 `.srt/.ass` 已随导入进入库目录。",
        timeout_problem=f"字幕翻译失败：检查内嵌字幕超时：{video_path}",
        timeout_fix="检查视频文件是否可读、体积是否异常，以及 `ffprobe` 是否可正常执行。",
    )
    if failure is not None:
        if failure.reason == "missing":
            return _probe_embedded_subtitle_streams_with_ffmpeg(video_path=video_path, timeout_seconds=timeout_seconds)
        return [], failure

    streams, parse_failure = _resolve_ffprobe_subtitle_streams(
        video_path=video_path,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
    if parse_failure is not None:
        return [], parse_failure
    return streams or [], None


def _probe_embedded_subtitle_streams_with_ffmpeg(
    *,
    video_path: Path,
    timeout_seconds: float,
) -> tuple[list[_EmbeddedSubtitleStream], _SubtitleCommandFailure | None]:
    command = [
        _resolve_local_ffmpeg_command("ffmpeg"),
        "-hide_banner",
        "-i",
        str(video_path),
    ]
    completed, failure = _run_subprocess_command(
        command=command,
        timeout_seconds=timeout_seconds,
        missing_problem=f"字幕翻译失败：系统缺少 ffprobe/ffmpeg，无法检查内嵌字幕：{video_path}",
        missing_fix="安装 `ffmpeg`（如能一并安装 `ffprobe` 更好）并确保命令在 PATH；如果只依赖外挂字幕，先确认同名 `.srt/.ass` 已随导入进入库目录。",
        timeout_problem=f"字幕翻译失败：检查内嵌字幕超时：{video_path}",
        timeout_fix="检查视频文件是否可读、体积是否异常，以及 `ffmpeg` 是否可正常执行。",
    )
    if failure is not None:
        return [], failure

    parsed_streams = _resolve_ffmpeg_subtitle_streams(
        output_text=completed.stderr or completed.stdout or "",
    )
    return parsed_streams, None


def _resolve_local_ffmpeg_command(command_name: str) -> str:
    local_binary = _LOCAL_FFMPEG_DIR / command_name
    if local_binary.is_file() and os.access(local_binary, os.X_OK):
        return str(local_binary)
    return command_name


def _parse_srt_blocks(content: str) -> list[_SrtBlock]:
    blocks: list[_SrtBlock] = []
    chunks = re.split(r"\n\s*\n", content.strip())
    for chunk in chunks:
        lines = [line.rstrip("\r") for line in chunk.splitlines() if line.strip() != ""]
        if len(lines) < 3:
            continue
        index = lines[0].strip()
        timecode = lines[1].strip()
        if not re.match(r"^\d+$", index):
            continue
        if not _is_timecode_line(timecode):
            continue
        text = "\n".join(lines[2:]).strip()
        if not text:
            continue
        blocks.append(_SrtBlock(index=index, timecode=timecode, text=text))
    return blocks


def _chunk_blocks(blocks: list[_ChunkItem], *, size: int) -> list[list[_ChunkItem]]:
    result: list[list[_ChunkItem]] = []
    for i in range(0, len(blocks), size):
        result.append(blocks[i : i + size])
    return result


def _translate_blocks_in_chunks(
    *,
    blocks: list[_ChunkItem],
    size: int,
    get_source_text: Callable[[_ChunkItem], str],
    translate_chunk: Callable[[list[str]], tuple[list[str] | None, str | None]],
    build_output_block: Callable[[_ChunkItem, str], _TranslatedChunkItem],
) -> tuple[list[_TranslatedChunkItem] | None, str | None]:
    translated_blocks: list[_TranslatedChunkItem] = []
    for chunk in _chunk_blocks(blocks, size=size):
        translated_lines, error_message = translate_chunk([get_source_text(block) for block in chunk])
        if translated_lines is None:
            return None, error_message
        for block, translated_text in zip(chunk, translated_lines):
            translated_blocks.append(build_output_block(block, translated_text.strip()))
    return translated_blocks, None


def _is_line_count_mismatch_runtime_error(error_message: str) -> bool:
    return error_message.startswith("翻译行数不一致（source=")


def _translate_chunk_lines_by_splitting(
    *,
    source_lines: list[str],
    translate_lines: Callable[[list[str]], list[str]],
    subtitle_path: Path,
) -> tuple[list[str] | None, str | None]:
    midpoint = len(source_lines) // 2
    left_lines, left_error = _translate_chunk_lines(
        source_lines=source_lines[:midpoint],
        translate_lines=translate_lines,
        subtitle_path=subtitle_path,
    )
    if left_lines is None:
        return None, left_error

    right_lines, right_error = _translate_chunk_lines(
        source_lines=source_lines[midpoint:],
        translate_lines=translate_lines,
        subtitle_path=subtitle_path,
    )
    if right_lines is None:
        return None, right_error
    return left_lines + right_lines, None


def _retry_or_split_line_count_mismatch(
    *,
    source_lines: list[str],
    translate_lines: Callable[[list[str]], list[str]],
    subtitle_path: Path,
    remaining_same_chunk_retries: int,
    mismatch_message: str,
) -> tuple[list[str] | None, str | None]:
    if remaining_same_chunk_retries > 0:
        return _translate_chunk_lines(
            source_lines=source_lines,
            translate_lines=translate_lines,
            subtitle_path=subtitle_path,
            remaining_same_chunk_retries=remaining_same_chunk_retries - 1,
        )
    if len(source_lines) > 1:
        return _translate_chunk_lines_by_splitting(
            source_lines=source_lines,
                translate_lines=translate_lines,
                subtitle_path=subtitle_path,
            )
    message = f"模型翻译失败：{subtitle_path}，原因：{mismatch_message}"
    _print_colored_error(
        problem=message,
        fix="检查模型输出格式约束，确保返回严格 JSON translations 数组；必要时更换更稳的模型。",
    )
    return None, message


def _translate_chunk_lines(
    *,
    source_lines: list[str],
    translate_lines: Callable[[list[str]], list[str]],
    subtitle_path: Path,
    remaining_same_chunk_retries: int = 1,
) -> tuple[list[str] | None, str | None]:
    try:
        translated_lines = translate_lines(source_lines)
    except RuntimeError as exc:
        if _is_line_count_mismatch_runtime_error(str(exc)):
            return _retry_or_split_line_count_mismatch(
                source_lines=source_lines,
                translate_lines=translate_lines,
                subtitle_path=subtitle_path,
                remaining_same_chunk_retries=remaining_same_chunk_retries,
                mismatch_message=str(exc),
            )
        message = f"模型翻译失败：{subtitle_path}，原因：{exc}"
        _print_colored_error(
            problem=message,
            fix="检查 API Key、模型名、网络和余额；必要时稍后重试。",
        )
        return None, message

    if len(translated_lines) != len(source_lines):
        if remaining_same_chunk_retries > 0:
            return _translate_chunk_lines(
                source_lines=source_lines,
                translate_lines=translate_lines,
                subtitle_path=subtitle_path,
                remaining_same_chunk_retries=remaining_same_chunk_retries - 1,
            )
        if len(source_lines) > 1:
            return _translate_chunk_lines_by_splitting(
                source_lines=source_lines,
                translate_lines=translate_lines,
                subtitle_path=subtitle_path,
            )
        mismatch_message = f"翻译行数不一致（source={len(source_lines)}, translated={len(translated_lines)}）"
        return _retry_or_split_line_count_mismatch(
            source_lines=source_lines,
            translate_lines=translate_lines,
            subtitle_path=subtitle_path,
            remaining_same_chunk_retries=0,
            mismatch_message=mismatch_message,
        )
    return translated_lines, None


def _translate_srt_subtitle_content(
    *,
    source_text: str,
    movie_title: str,
    subtitle_path: Path,
    translate_lines: Callable[[list[str], str], list[str]],
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
            translate_lines=lambda lines: translate_lines(lines, movie_title),
        ),
        build_output_block=lambda block, translated_text: _SrtBlock(
            index=block.index,
            timecode=block.timecode,
            text=translated_text,
        ),
    )
    if translated_blocks is None:
        return None, error_message
    bilingual_ass_output = _render_bilingual_ass_from_srt_blocks(
        blocks=blocks,
        translated_blocks=translated_blocks,
    )
    _write_bilingual_ass_sidecar(
        source_path=subtitle_path,
        bilingual_output=bilingual_ass_output,
    )
    return _render_srt(translated_blocks), None


def _translate_ass_subtitle_content(
    *,
    source_text: str,
    movie_title: str,
    subtitle_path: Path,
    translate_lines: Callable[[list[str], str], list[str]],
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
            translate_lines=lambda lines: translate_lines(lines, movie_title),
        ),
        build_output_block=lambda _, translated_text: translated_text,
    )
    if translated_lines is None:
        return None, error_message
    for dialogue_line, translated_text in zip(dialogue_lines, translated_lines):
        lines[dialogue_line.line_index] = dialogue_line.prefix + translated_text
    _write_bilingual_ass_sidecar(
        source_path=subtitle_path,
        bilingual_output=_render_bilingual_ass_from_ass_lines(
            lines=lines,
            dialogue_lines=dialogue_lines,
            translated_lines=translated_lines,
        ),
    )
    return _render_ass_lines(lines, had_trailing_newline=source_text.endswith(("\n", "\r"))), None


def _run_subprocess_command(
    *,
    command: list[str],
    timeout_seconds: float,
    missing_problem: str,
    missing_fix: str,
    timeout_problem: str,
    timeout_fix: str,
) -> tuple[subprocess.CompletedProcess[str] | None, _SubtitleCommandFailure | None]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return None, _SubtitleCommandFailure(reason="missing", problem=missing_problem, fix=missing_fix)
    except subprocess.TimeoutExpired:
        return None, _SubtitleCommandFailure(reason="timeout", problem=timeout_problem, fix=timeout_fix)
    return completed, None


def _render_srt(blocks: list[_SrtBlock]) -> str:
    rendered_chunks: list[str] = []
    for block in blocks:
        rendered_chunks.append(f"{block.index}\n{block.timecode}\n{block.text.strip()}")
    return "\n\n".join(rendered_chunks).strip() + "\n"


def _parse_ass_dialogue_lines(content: str) -> tuple[list[str], list[_AssDialogueLine]]:
    lines = [line.rstrip("\r") for line in content.splitlines()]
    if not any(line.strip() == "[Script Info]" for line in lines):
        return lines, []

    dialogue_lines: list[_AssDialogueLine] = []
    for index, line in enumerate(lines):
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) != 10:
            continue
        text = parts[9].strip()
        if not text:
            continue
        dialogue_lines.append(
            _AssDialogueLine(
                line_index=index,
                prefix=",".join(parts[:9]) + ",",
                text=text,
            )
        )
    return lines, dialogue_lines


def _render_ass_lines(lines: list[str], *, had_trailing_newline: bool) -> str:
    rendered = "\n".join(lines)
    if had_trailing_newline:
        return rendered + "\n"
    return rendered


def _render_bilingual_ass_from_srt_blocks(
    *,
    blocks: list[_SrtBlock],
    translated_blocks: list[_SrtBlock],
) -> str:
    header = _build_bilingual_ass_header()
    dialogue_lines: list[str] = []
    for source_block, translated_block in zip(blocks, translated_blocks):
        start_time, end_time = _convert_srt_timecode_to_ass(source_block.timecode)
        bilingual_text = _build_bilingual_ass_dialogue_text(
            chinese_text=translated_block.text,
            english_text=source_block.text,
        )
        dialogue_lines.append(
            f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{bilingual_text}"
        )
    return header + "\n".join(dialogue_lines) + "\n"


def _render_bilingual_ass_from_ass_lines(
    *,
    lines: list[str],
    dialogue_lines: list[_AssDialogueLine],
    translated_lines: list[str],
) -> str:
    bilingual_lines = list(lines)
    for dialogue_line, translated_text in zip(dialogue_lines, translated_lines):
        bilingual_lines[dialogue_line.line_index] = (
            dialogue_line.prefix
            + _build_bilingual_ass_dialogue_text(
                chinese_text=translated_text,
                english_text=dialogue_line.text,
            )
        )
    return _render_ass_lines(bilingual_lines, had_trailing_newline=bool(lines and lines[-1] == ""))


def _build_bilingual_ass_header() -> str:
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n"
        "PlayResX: 1920\n"
        "PlayResY: 1080\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{_BILINGUAL_ASS_FONT_FAMILY},{_BILINGUAL_ASS_CHINESE_FONT_SIZE},"
        "&H00FFFFFF,&H00FFFFFF,&H00111111,&H64000000,0,0,0,0,100,100,0,0,1,1,0,2,30,30,20,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _convert_srt_timecode_to_ass(timecode: str) -> tuple[str, str]:
    start_raw, end_raw = [part.strip() for part in timecode.split("-->")]
    return _normalize_srt_timestamp_for_ass(start_raw), _normalize_srt_timestamp_for_ass(end_raw)


def _normalize_srt_timestamp_for_ass(timestamp: str) -> str:
    hours_text, minutes_text, rest_text = timestamp.split(":")
    seconds_text, milliseconds_text = rest_text.split(",")
    hours = int(hours_text)
    milliseconds = int(milliseconds_text)
    centiseconds = round(milliseconds / 10)
    if centiseconds >= 100:
        seconds = int(seconds_text) + 1
        centiseconds = 0
    else:
        seconds = int(seconds_text)
    return f"{hours}:{int(minutes_text):02d}:{seconds:02d}.{centiseconds:02d}"


def _build_bilingual_ass_dialogue_text(*, chinese_text: str, english_text: str) -> str:
    chinese = _escape_ass_text(chinese_text.strip())
    english = _escape_ass_text(english_text.strip())
    if chinese and english:
        return (
            f"{{\\fn{_BILINGUAL_ASS_FONT_FAMILY}\\fs{_BILINGUAL_ASS_CHINESE_FONT_SIZE}\\an2}}"
            f"{chinese}"
            f"\\N{{\\fn{_BILINGUAL_ASS_FONT_FAMILY}\\fs{_BILINGUAL_ASS_ENGLISH_FONT_SIZE}}}{english}"
        )
    if chinese:
        return (
            f"{{\\fn{_BILINGUAL_ASS_FONT_FAMILY}\\fs{_BILINGUAL_ASS_CHINESE_FONT_SIZE}\\an2}}"
            f"{chinese}"
        )
    if english:
        return (
            f"{{\\fn{_BILINGUAL_ASS_FONT_FAMILY}\\fs{_BILINGUAL_ASS_ENGLISH_FONT_SIZE}\\an2}}"
            f"{english}"
        )
    return ""


def _escape_ass_text(value: str) -> str:
    return (
        value.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\r\n", r"\N")
        .replace("\n", r"\N")
        .replace("\r", r"\N")
    )


def _write_bilingual_ass_sidecar(*, source_path: Path, bilingual_output: str) -> None:
    bilingual_path = source_path.with_suffix(_BILINGUAL_ASS_OUTPUT_SUFFIX)
    try:
        bilingual_path.write_text(bilingual_output, encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        emit_operational_log(
            title="双排字幕写入失败",
            detail=f"source={source_path} target={bilingual_path} 错误={exc}",
            fix_hint="检查字幕目录写权限和磁盘空间；当前 plain 字幕仍会保留。",
        )


def _is_timecode_line(line: str) -> bool:
    return bool(
        re.match(
            r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}",
            line.strip(),
        )
    )


def _extract_translations_from_response(response_text: str) -> list[str]:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    payload = _load_json_object(cleaned)
    translations = payload.get("translations")
    if not isinstance(translations, list):
        raise RuntimeError("响应 JSON 缺少 translations 数组。")

    result: list[str] = []
    for item in translations:
        if not isinstance(item, str):
            raise RuntimeError("translations 数组中存在非字符串项。")
        result.append(item)
    return result


def _load_json_object(content: str) -> dict[str, object]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end < 0 or end <= start:
            raise RuntimeError("模型返回内容不是有效 JSON。")
        payload = json.loads(content[start : end + 1])

    if not isinstance(payload, dict):
        raise RuntimeError("模型返回 JSON 不是对象。")
    return payload


def _read_metadata_title(metadata_path: Path) -> str:
    payload = _read_metadata_payload(metadata_path)
    if payload is None:
        return ""
    tmdb_block = payload.get("tmdb")
    if not isinstance(tmdb_block, dict):
        _print_colored_error(
            problem=f"读取字幕元数据失败：{metadata_path}，原因=tmdb 字段不是对象",
            fix="检查 metadata JSON 里的 tmdb 字段是否仍保留对象结构，并确认 title/original_title 仍在该对象下。",
        )
        return ""
    title = str(tmdb_block.get("title", "")).strip()
    if title:
        return title
    return str(tmdb_block.get("original_title", "")).strip()


def _read_metadata_trusted_name_map(metadata_path: Path) -> dict[str, str]:
    payload = _read_metadata_payload(metadata_path)
    if payload is None:
        return {}
    translation_block = payload.get("subtitle_translation")
    if not isinstance(translation_block, dict):
        return {}
    raw_name_map = translation_block.get("trusted_name_map")
    if not isinstance(raw_name_map, dict):
        return {}
    trusted_name_map: dict[str, str] = {}
    for raw_key, raw_value in raw_name_map.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            continue
        key = raw_key.strip()
        value = raw_value.strip()
        if not key or not value:
            continue
        trusted_name_map[key] = value
    return trusted_name_map


def _read_metadata_payload(metadata_path: Path) -> dict[str, object] | None:
    if not str(metadata_path).strip():
        return None
    if not metadata_path.exists() or not metadata_path.is_file():
        return None
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        _print_colored_error(
            problem=f"读取字幕元数据失败：{metadata_path}，原因={error}",
            fix="检查 metadata JSON 文件是否仍可读、编码是否为 UTF-8，以及 tmdb 字段结构是否完整。",
        )
        return None
    if not isinstance(payload, dict):
        _print_colored_error(
            problem=f"读取字幕元数据失败：{metadata_path}，原因=metadata JSON 根不是对象",
            fix="检查 metadata JSON 文件是否仍是对象结构，并确认 tmdb 字段保持对象。",
        )
        return None
    return payload


def _print_colored_error(*, problem: str, fix: str) -> None:
    emit_operational_log(title="字幕翻译失败", detail=problem, fix_hint=fix)
