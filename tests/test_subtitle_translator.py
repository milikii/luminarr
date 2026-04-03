from __future__ import annotations

import json
from pathlib import Path

from app.services.subtitle_translator import SubtitleTranslateInput, SubtitleTranslatorService


def test_translate_for_import_creates_zh_subtitle_for_file_target(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")
    subtitle_file = library_dir / "Interstellar (2014).srt"
    subtitle_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nhello movie\n",
        encoding="utf-8",
    )

    def fake_request(_: str, user_payload: dict[str, object]) -> str:
        source_lines = user_payload.get("source_lines")
        assert isinstance(source_lines, list)
        translations = [f"专业译文：{line}" for line in source_lines]
        return json.dumps({"translations": translations}, ensure_ascii=False)

    service = SubtitleTranslatorService(
        api_key="demo-key",
        request_chat_completion_func=fake_request,
    )
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-87",
            task_id="87",
            task_hash="hash-87",
            target_path=str(target_file),
        )
    )

    translated_file = library_dir / "Interstellar (2014).zh.srt"
    assert result.success is True
    assert result.skipped is False
    assert translated_file.exists()
    payload = translated_file.read_text(encoding="utf-8")
    assert "专业译文：hello movie" in payload


def test_translate_for_import_skips_when_no_subtitle_file(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")

    service = SubtitleTranslatorService()
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-87",
            task_id="87",
            task_hash="hash-87",
            target_path=str(target_file),
        )
    )

    assert result.success is False
    assert result.skipped is True
    assert "已跳过" in result.message


def test_translate_for_import_fails_when_missing_api_key(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")
    subtitle_file = library_dir / "Interstellar (2014).srt"
    subtitle_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nhello movie\n",
        encoding="utf-8",
    )

    service = SubtitleTranslatorService()
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-87",
            task_id="87",
            task_hash="hash-87",
            target_path=str(target_file),
        )
    )

    assert result.success is False
    assert result.skipped is False
    assert "缺少 SUBTITLE_TRANSLATION_API_KEY" in result.message


def test_translate_for_import_fails_when_subtitle_not_utf8(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")
    subtitle_file = library_dir / "Interstellar (2014).srt"
    subtitle_file.write_bytes(b"\xff\xfe\x00\x00")

    def fake_request(_: str, user_payload: dict[str, object]) -> str:
        source_lines = user_payload.get("source_lines")
        assert isinstance(source_lines, list)
        translations = [str(line) for line in source_lines]
        return json.dumps({"translations": translations}, ensure_ascii=False)

    service = SubtitleTranslatorService(
        api_key="demo-key",
        request_chat_completion_func=fake_request,
    )
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-87",
            task_id="87",
            task_hash="hash-87",
            target_path=str(target_file),
        )
    )

    assert result.success is False
    assert result.skipped is False
    assert "读取字幕文件失败" in result.message
