from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar


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


_VIDEO_FILE_SUFFIXES = frozenset({".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".ts", ".m2ts", ".webm"})
_SUBTITLE_FILE_SUFFIXES = (".srt", ".ass")
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
    if _is_chinese_subtitle_path(path):
        return None
    suffix = path.suffix.lower()
    if suffix == ".srt":
        return _SubtitleFile(source_path=path, translated_path=path.with_suffix(".zh.srt"), kind="srt")
    if suffix == ".ass":
        return _SubtitleFile(source_path=path, translated_path=path.with_suffix(".zh.ass"), kind="ass")
    return None


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


def _find_video_files(target_path: Path) -> list[Path]:
    if target_path.is_file():
        return [target_path] if target_path.suffix.lower() in _VIDEO_FILE_SUFFIXES else []
    if not target_path.is_dir():
        return []
    return sorted(candidate for candidate in target_path.rglob("*") if candidate.is_file() and candidate.suffix.lower() in _VIDEO_FILE_SUFFIXES)


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


def _translate_chunk_lines(
    *,
    source_lines: list[str],
    translate_lines: Callable[[list[str]], list[str]],
    subtitle_path: Path,
) -> tuple[list[str] | None, str | None]:
    try:
        translated_lines = translate_lines(source_lines)
    except Exception as exc:
        message = f"模型翻译失败：{subtitle_path}，原因：{exc}"
        _print_colored_error(
            problem=message,
            fix="检查 API Key、模型名、网络和余额；必要时稍后重试。",
        )
        return None, message

    if len(translated_lines) != len(source_lines):
        message = f"模型返回行数不一致：源={len(source_lines)}，译文={len(translated_lines)}，文件={subtitle_path}"
        _print_colored_error(
            problem=message,
            fix="检查模型输出格式约束，确保返回严格 JSON translations 数组。",
        )
        return None, message
    return translated_lines, None


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
    if not str(metadata_path).strip():
        return ""
    if not metadata_path.exists() or not metadata_path.is_file():
        return ""
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as error:
        _print_colored_error(
            problem=f"读取字幕元数据失败：{metadata_path}，原因={error}",
            fix="检查 metadata JSON 文件是否仍可读、编码是否为 UTF-8，以及 tmdb 字段结构是否完整。",
        )
        return ""
    if not isinstance(payload, dict):
        _print_colored_error(
            problem=f"读取字幕元数据失败：{metadata_path}，原因=metadata JSON 根不是对象",
            fix="检查 metadata JSON 文件是否仍是对象结构，并确认 tmdb 字段保持对象。",
        )
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


def _print_colored_error(*, problem: str, fix: str) -> None:
    print(f"\033[31m[字幕翻译失败]\033[0m {problem}", flush=True)
    print(f"\033[33m[处理建议]\033[0m {fix}", flush=True)
