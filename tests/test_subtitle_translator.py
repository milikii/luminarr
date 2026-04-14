from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

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
