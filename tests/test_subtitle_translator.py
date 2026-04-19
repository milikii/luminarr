from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import app.services.subtitle_translator as subtitle_module
import httpx

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


def test_translate_for_import_creates_zh_ass_subtitle_for_file_target(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Frieren - 01.mkv"
    target_file.write_bytes(b"video")
    subtitle_file = library_dir / "Frieren - 01.ass"
    subtitle_file.write_text(
        "[Script Info]\n"
        "Title: Frieren\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,hello mage\n",
        encoding="utf-8",
    )

    def fake_request(_: str, user_payload: dict[str, object]) -> str:
        source_lines = user_payload.get("source_lines")
        assert isinstance(source_lines, list)
        return json.dumps({"translations": [f"专业译文：{line}" for line in source_lines]}, ensure_ascii=False)

    service = SubtitleTranslatorService(
        api_key="demo-key",
        request_chat_completion_func=fake_request,
    )
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-88",
            task_id="88",
            task_hash="hash-88",
            target_path=str(target_file),
        )
    )

    translated_file = library_dir / "Frieren - 01.zh.ass"
    assert result.success is True
    assert result.skipped is False
    assert translated_file.exists()
    payload = translated_file.read_text(encoding="utf-8")
    assert "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,专业译文：hello mage" in payload
    assert "[Script Info]" in payload


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


def test_translate_for_import_fails_when_ass_file_is_invalid(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Frieren - 01.mkv"
    target_file.write_bytes(b"video")
    subtitle_file = library_dir / "Frieren - 01.ass"
    subtitle_file.write_text("Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,hello\n", encoding="utf-8")

    def fake_request(_: str, user_payload: dict[str, object]) -> str:
        source_lines = user_payload.get("source_lines")
        assert isinstance(source_lines, list)
        return json.dumps({"translations": [str(line) for line in source_lines]}, ensure_ascii=False)

    service = SubtitleTranslatorService(
        api_key="demo-key",
        request_chat_completion_func=fake_request,
    )
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-89",
            task_id="89",
            task_hash="hash-89",
            target_path=str(target_file),
        )
    )

    assert result.success is False
    assert result.skipped is False
    assert "不是有效 ASS" in result.message


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


def test_read_metadata_title_logs_metadata_read_failure(
    tmp_path: Path,
    capsys,
) -> None:
    metadata_path = tmp_path / "movie.metadata.json"
    metadata_path.write_text("{", encoding="utf-8")

    assert subtitle_module._read_metadata_title(metadata_path) == ""

    output = capsys.readouterr().out
    assert "[字幕翻译失败]" in output
    assert "读取字幕元数据失败" in output
    assert str(metadata_path) in output
    assert "[处理建议]" in output


def test_read_metadata_title_logs_non_object_root_payload(tmp_path: Path, capsys) -> None:
    metadata_path = tmp_path / "movie.metadata.json"
    metadata_path.write_text('["not-an-object"]', encoding="utf-8")

    assert subtitle_module._read_metadata_title(metadata_path) == ""

    output = capsys.readouterr().out
    assert "[字幕翻译失败]" in output
    assert "metadata JSON 根不是对象" in output
    assert str(metadata_path) in output
    assert "[处理建议]" in output


def test_read_metadata_title_logs_non_object_tmdb_block(tmp_path: Path, capsys) -> None:
    metadata_path = tmp_path / "movie.metadata.json"
    metadata_path.write_text('{"tmdb": ["not-an-object"]}', encoding="utf-8")

    assert subtitle_module._read_metadata_title(metadata_path) == ""

    output = capsys.readouterr().out
    assert "[字幕翻译失败]" in output
    assert "tmdb 字段不是对象" in output
    assert str(metadata_path) in output
    assert "[处理建议]" in output


def test_subtitle_translator_passes_proxy_to_httpx(monkeypatch) -> None:
    client_ctor = Mock()
    post = Mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"translations\": [\"ok\"]}"}}]},
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )
    )
    client_instance = Mock(__enter__=Mock(return_value=Mock(post=post)), __exit__=Mock(return_value=None))
    client_ctor.return_value = client_instance
    monkeypatch.setattr(httpx, "Client", client_ctor)

    service = SubtitleTranslatorService(
        api_key="demo-key",
        proxy_url="http://192.168.2.110:7890",
    )
    result = service._request_chat_completion(system_prompt="system", user_payload={"source_lines": ["hello"]})

    assert result == "{\"translations\": [\"ok\"]}"
    client_ctor.assert_called_once_with(timeout=60.0, proxy="http://192.168.2.110:7890")
