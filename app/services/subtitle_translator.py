from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx


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

        subtitle_files = _find_source_subtitle_files(target_path)
        if not subtitle_files:
            message = "字幕翻译已跳过：未找到可翻译的 .srt / .ass 字幕文件。"
            return SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=True)

        if not self._api_key:
            message = "字幕翻译失败：缺少 SUBTITLE_TRANSLATION_API_KEY，无法进行专业级翻译。"
            _print_colored_error(
                problem=message,
                fix="在环境变量里配置 `SUBTITLE_TRANSLATION_API_KEY`，并确认网络可访问翻译接口。",
            )
            return SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=False)

        movie_title = _read_metadata_title(Path(translate_input.metadata_path))
        translated_count = 0
        for subtitle_file in subtitle_files:
            if subtitle_file.translated_path.exists():
                continue
            result = self._translate_single_file(
                subtitle_file=subtitle_file,
                movie_title=movie_title,
            )
            if not result.success:
                return result
            translated_count += 1

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

    def _translate_single_file(
        self,
        *,
        subtitle_file: _SubtitleFile,
        movie_title: str,
    ) -> SubtitleTranslateResult:
        try:
            source_text = subtitle_file.source_path.read_text(encoding="utf-8")
        except Exception as exc:
            message = f"读取字幕文件失败：{subtitle_file.source_path}，原因：{exc}"
            _print_colored_error(
                problem=message,
                fix="确认字幕是 UTF-8 编码，必要时先转码后再重试。",
            )
            return SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=False)

        if subtitle_file.kind == "srt":
            rendered_output, error_message = self._translate_srt_text(
                source_text=source_text,
                movie_title=movie_title,
                subtitle_path=subtitle_file.source_path,
            )
        elif subtitle_file.kind == "ass":
            rendered_output, error_message = self._translate_ass_text(
                source_text=source_text,
                movie_title=movie_title,
                subtitle_path=subtitle_file.source_path,
            )
        else:
            message = f"字幕翻译失败：暂不支持的字幕格式：{subtitle_file.source_path}"
            _print_colored_error(
                problem=message,
                fix="确认字幕是 `.srt` 或 `.ass` 文件，再重试导入。",
            )
            return SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=False)

        if rendered_output is None:
            return SubtitleTranslateResult(
                success=False,
                message=error_message or "字幕翻译失败。",
                translated_count=0,
                skipped=False,
            )

        try:
            subtitle_file.translated_path.write_text(rendered_output, encoding="utf-8")
        except Exception as exc:
            message = f"写入字幕文件失败：{subtitle_file.translated_path}，原因：{exc}"
            _print_colored_error(
                problem=message,
                fix="检查导入目录写权限和磁盘空间，再重试 confirm 导入。",
            )
            return SubtitleTranslateResult(success=False, message=message, translated_count=0, skipped=False)
        return SubtitleTranslateResult(success=True, message="ok", translated_count=1, skipped=False)

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

        translated_blocks: list[_SrtBlock] = []
        for chunk in _chunk_blocks(blocks, size=60):
            translated_lines, error_message = self._translate_chunk_lines(
                source_lines=[block.text for block in chunk],
                movie_title=movie_title,
                subtitle_path=subtitle_path,
            )
            if translated_lines is None:
                return None, error_message
            for block, translated_text in zip(chunk, translated_lines):
                translated_blocks.append(
                    _SrtBlock(
                        index=block.index,
                        timecode=block.timecode,
                        text=translated_text.strip(),
                    )
                )
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

        for chunk in _chunk_blocks(dialogue_lines, size=60):
            translated_lines, error_message = self._translate_chunk_lines(
                source_lines=[line.text for line in chunk],
                movie_title=movie_title,
                subtitle_path=subtitle_path,
            )
            if translated_lines is None:
                return None, error_message
            for dialogue_line, translated_text in zip(chunk, translated_lines):
                lines[dialogue_line.line_index] = dialogue_line.prefix + translated_text.strip()
        return _render_ass_lines(lines, had_trailing_newline=source_text.endswith(("\n", "\r"))), None

    def _translate_chunk_lines(
        self,
        *,
        source_lines: list[str],
        movie_title: str,
        subtitle_path: Path,
    ) -> tuple[list[str] | None, str | None]:
        try:
            translated_lines = self._translate_lines_professional(
                source_lines=source_lines,
                movie_title=movie_title,
            )
        except Exception as exc:
            message = f"模型翻译失败：{subtitle_path}，原因：{exc}"
            _print_colored_error(
                problem=message,
                fix="检查 API Key、模型名、网络和余额；必要时稍后重试。",
            )
            return None, message

        if len(translated_lines) != len(source_lines):
            message = (
                f"模型返回行数不一致：源={len(source_lines)}，译文={len(translated_lines)}，文件={subtitle_path}"
            )
            _print_colored_error(
                problem=message,
                fix="检查模型输出格式约束，确保返回严格 JSON translations 数组。",
            )
            return None, message
        return translated_lines, None

    def _translate_lines_professional(self, *, source_lines: list[str], movie_title: str) -> list[str]:
        system_prompt = (
            "你是专业影视字幕译者。任务：把英文字幕逐行翻译为简体中文。"
            "必须保留每行语气、语境、人物关系，不要删减信息，不要总结。"
            "脏话、双关、俚语要自然等价翻译。"
        )
        user_payload = {
            "movie_title": movie_title,
            "source_lines": source_lines,
            "rules": {
                "target_language": "zh-CN",
                "style": "专业影视字幕",
                "return_json_only": True,
                "json_schema": {"translations": ["与 source_lines 等长的中文字符串数组"]},
            },
        }

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


def _find_source_subtitle_files(target_path: Path) -> list[_SubtitleFile]:
    if target_path.is_file():
        return [candidate for suffix in (".srt", ".ass") if (candidate := _build_subtitle_file(target_path.with_suffix(suffix)))]

    if not target_path.is_dir():
        return []

    candidates = sorted(candidate for pattern in ("*.srt", "*.ass") for candidate in target_path.rglob(pattern))
    files: list[_SubtitleFile] = []
    for candidate in candidates:
        subtitle_file = _build_subtitle_file(candidate)
        if subtitle_file is not None:
            files.append(subtitle_file)
    return files


def _build_subtitle_file(path: Path) -> _SubtitleFile | None:
    if not path.exists() or not path.is_file():
        return None
    suffix = path.suffix.lower()
    if suffix == ".srt":
        if path.name.endswith(".zh.srt"):
            return None
        return _SubtitleFile(source_path=path, translated_path=path.with_suffix(".zh.srt"), kind="srt")
    if suffix == ".ass":
        if path.name.endswith(".zh.ass"):
            return None
        return _SubtitleFile(source_path=path, translated_path=path.with_suffix(".zh.ass"), kind="ass")
    return None


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


def _chunk_blocks(blocks: list[_SrtBlock], *, size: int) -> list[list[_SrtBlock]]:
    result: list[list[_SrtBlock]] = []
    for i in range(0, len(blocks), size):
        result.append(blocks[i : i + size])
    return result


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
