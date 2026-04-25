from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import app.services.subtitle_translation_support as subtitle_support
import app.services.subtitle_translator as subtitle_module
import httpx
import pytest

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


def test_translate_for_import_success_message_prefers_metadata_title(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")
    subtitle_file = library_dir / "Interstellar (2014).srt"
    subtitle_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nhello movie\n",
        encoding="utf-8",
    )
    metadata_path = library_dir / "Interstellar (2014).metadata.json"
    metadata_path.write_text(
        json.dumps({"tmdb": {"title": "星际穿越", "original_title": "Interstellar"}}, ensure_ascii=False),
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
            task_ref="hash-msg-1",
            task_id="msg-1",
            task_hash="hash-msg-1",
            target_path=str(target_file),
            metadata_path=str(metadata_path),
        )
    )

    assert result.success is True
    assert result.message == "字幕翻译成功：星际穿越，已生成 1 个字幕文件。"


def test_translate_for_import_translates_large_srt_in_chunks(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")
    subtitle_file = library_dir / "Interstellar (2014).srt"
    subtitle_file.write_text(
        "\n\n".join(
            f"{index}\n00:00:{index:02d},000 --> 00:00:{index + 1:02d},000\nline {index}"
            for index in range(1, 63)
        )
        + "\n",
        encoding="utf-8",
    )

    seen_chunk_sizes: list[int] = []

    def fake_request(_: str, user_payload: dict[str, object]) -> str:
        source_lines = user_payload.get("source_lines")
        assert isinstance(source_lines, list)
        seen_chunk_sizes.append(len(source_lines))
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
    assert seen_chunk_sizes == [60, 2]
    payload = translated_file.read_text(encoding="utf-8")
    assert "专业译文：line 1" in payload
    assert "专业译文：line 62" in payload


def test_translate_for_import_skips_when_translated_subtitle_already_exists(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")
    subtitle_file = library_dir / "Interstellar (2014).srt"
    subtitle_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nhello movie\n",
        encoding="utf-8",
    )
    translated_file = library_dir / "Interstellar (2014).zh.srt"
    translated_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\n你好，电影\n",
        encoding="utf-8",
    )

    service = SubtitleTranslatorService(api_key="demo-key")
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-skip-1",
            task_id="skip-1",
            task_hash="hash-skip-1",
            target_path=str(target_file),
        )
    )

    assert result.success is False
    assert result.skipped is True
    assert result.translated_count == 0
    assert result.message == "字幕翻译已跳过：目标中文字幕文件已存在。"


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


def test_translate_for_import_directory_translates_each_episode_without_global_chinese_skip(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    season_dir = library_dir / "Show.S01"
    season_dir.mkdir(parents=True)

    episode1 = season_dir / "Show.S01E01.mkv"
    episode2 = season_dir / "Show.S01E02.mkv"
    episode1.write_bytes(b"video-1")
    episode2.write_bytes(b"video-2")

    (season_dir / "Show.S01E01.chs.srt").write_text(
        "1\n00:00:01,000 --> 00:00:03,000\n你好\n",
        encoding="utf-8",
    )
    (season_dir / "Show.S01E02.srt").write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nhello episode two\n",
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
            task_ref="hash-dir-1",
            task_id="dir-1",
            task_hash="hash-dir-1",
            target_path=str(season_dir),
        )
    )

    assert result.success is True
    assert result.translated_count == 1
    assert not (season_dir / "Show.S01E01.zh.srt").exists()
    assert (season_dir / "Show.S01E02.zh.srt").exists()
    assert "专业译文：hello episode two" in (season_dir / "Show.S01E02.zh.srt").read_text(encoding="utf-8")


def test_translate_for_import_directory_reports_chinese_external_skip_when_all_episodes_have_chinese_subtitles(
    tmp_path: Path,
) -> None:
    library_dir = tmp_path / "library"
    season_dir = library_dir / "Show.S01"
    season_dir.mkdir(parents=True)

    for episode in ("Show.S01E01", "Show.S01E02"):
        (season_dir / f"{episode}.mkv").write_bytes(b"video")
        (season_dir / f"{episode}.chs.srt").write_text(
            "1\n00:00:01,000 --> 00:00:03,000\n你好\n",
            encoding="utf-8",
        )

    service = SubtitleTranslatorService(api_key="demo-key")
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-dir-skip",
            task_id="dir-skip",
            task_hash="hash-dir-skip",
            target_path=str(season_dir),
        )
    )

    assert result.success is False
    assert result.skipped is True
    assert result.message == "字幕翻译已跳过：已检测到中文字幕外挂字幕。"


def test_translate_for_import_directory_reports_chinese_embedded_skip_when_all_episodes_have_chinese_embedded_subtitles(
    tmp_path: Path,
    monkeypatch,
) -> None:
    library_dir = tmp_path / "library"
    season_dir = library_dir / "Show.S01"
    season_dir.mkdir(parents=True)

    episode1 = season_dir / "Show.S01E01.mkv"
    episode2 = season_dir / "Show.S01E02.mkv"
    episode1.write_bytes(b"video-1")
    episode2.write_bytes(b"video-2")

    def fake_run(args: list[str], capture_output: bool, text: bool, timeout: float) -> subprocess.CompletedProcess[str]:
        assert args[0] == "ffprobe"
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                {
                    "streams": [
                        {
                            "index": 2,
                            "codec_name": "subrip",
                            "tags": {"language": "chi", "title": "简体中文"},
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            stderr="",
        )

    monkeypatch.setattr(subtitle_support.subprocess, "run", fake_run)

    service = SubtitleTranslatorService(api_key="demo-key")
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-dir-embedded-skip",
            task_id="dir-embedded-skip",
            task_hash="hash-dir-embedded-skip",
            target_path=str(season_dir),
        )
    )

    assert result.success is False
    assert result.skipped is True
    assert result.message == "字幕翻译已跳过：视频内已检测到中文字幕轨。"


def test_translate_for_import_skips_when_directory_has_no_video_files(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    season_dir = library_dir / "Show.S01"
    season_dir.mkdir(parents=True)
    (season_dir / "notes.txt").write_text("no video here", encoding="utf-8")

    service = SubtitleTranslatorService(api_key="demo-key")
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-empty-dir",
            task_id="empty-dir",
            task_hash="hash-empty-dir",
            target_path=str(season_dir),
        )
    )

    assert result.success is False
    assert result.skipped is True
    assert result.message == "字幕翻译已跳过：未找到可翻译的外挂字幕或英文内嵌字幕。"


def test_translate_for_import_directory_mixes_external_and_embedded_episode_subtitles(
    tmp_path: Path,
    monkeypatch,
) -> None:
    library_dir = tmp_path / "library"
    season_dir = library_dir / "Show.S01"
    season_dir.mkdir(parents=True)

    episode1 = season_dir / "Show.S01E01.mkv"
    episode2 = season_dir / "Show.S01E02.mkv"
    episode1.write_bytes(b"video-1")
    episode2.write_bytes(b"video-2")
    (season_dir / "Show.S01E01.srt").write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nhello external\n",
        encoding="utf-8",
    )

    def fake_request(_: str, user_payload: dict[str, object]) -> str:
        source_lines = user_payload.get("source_lines")
        assert isinstance(source_lines, list)
        return json.dumps({"translations": [f"专业译文：{line}" for line in source_lines]}, ensure_ascii=False)

    def fake_run(args: list[str], capture_output: bool, text: bool, timeout: float) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        assert timeout == 60.0
        if args[0] == "ffprobe":
            assert str(episode2) in args
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "index": 2,
                                "codec_name": "subrip",
                                "tags": {"language": "eng", "title": "English"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                stderr="",
            )
        if args[0] == "ffmpeg":
            Path(args[-1]).write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nhello embedded\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(subtitle_support.subprocess, "run", fake_run)

    service = SubtitleTranslatorService(
        api_key="demo-key",
        request_chat_completion_func=fake_request,
    )
    result = service.translate_for_import(
        SubtitleTranslateInput(
            task_ref="hash-dir-2",
            task_id="dir-2",
            task_hash="hash-dir-2",
            target_path=str(season_dir),
        )
    )

    assert result.success is True
    assert result.translated_count == 2
    assert (season_dir / "Show.S01E01.zh.srt").exists()
    assert (season_dir / "Show.S01E02.zh.srt").exists()
    assert "专业译文：hello external" in (season_dir / "Show.S01E01.zh.srt").read_text(encoding="utf-8")
    assert "专业译文：hello embedded" in (season_dir / "Show.S01E02.zh.srt").read_text(encoding="utf-8")


def test_translate_for_import_skips_when_no_subtitle_file(tmp_path: Path, monkeypatch) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")

    def fake_run(args: list[str], capture_output: bool, text: bool, timeout: float) -> subprocess.CompletedProcess[str]:
        assert args[0] == "ffprobe"
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps({"streams": []}, ensure_ascii=False),
            stderr="",
        )

    monkeypatch.setattr(subtitle_support.subprocess, "run", fake_run)

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


def test_translate_for_import_skips_when_chinese_external_subtitle_exists(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")
    subtitle_file = library_dir / "Interstellar (2014).chs.srt"
    subtitle_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\n你好，宇航员\n",
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
    assert result.skipped is True
    assert "中文字幕外挂字幕" in result.message


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


def test_translate_single_file_fails_when_subtitle_kind_is_unsupported(tmp_path: Path) -> None:
    subtitle_file = tmp_path / "Interstellar (2014).vtt"
    subtitle_file.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nhello\n", encoding="utf-8")

    service = SubtitleTranslatorService(api_key="demo-key")
    result = service._translate_single_file(
        subtitle_file=subtitle_support._SubtitleFile(
            source_path=subtitle_file,
            translated_path=tmp_path / "Interstellar (2014).zh.vtt",
            kind="vtt",
        ),
        movie_title="Interstellar",
    )

    assert result.success is False
    assert result.skipped is False
    assert "暂不支持的字幕格式" in result.message


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


def test_translate_for_import_extracts_embedded_english_subtitle_when_no_external_subtitle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")

    def fake_request(_: str, user_payload: dict[str, object]) -> str:
        source_lines = user_payload.get("source_lines")
        assert isinstance(source_lines, list)
        return json.dumps({"translations": [f"专业译文：{line}" for line in source_lines]}, ensure_ascii=False)

    def fake_run(args: list[str], capture_output: bool, text: bool, timeout: float) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        assert timeout == 60.0
        if args[0] == "ffprobe":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "index": 2,
                                "codec_name": "subrip",
                                "tags": {"language": "eng", "title": "English"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                stderr="",
            )
        if args[0] == "ffmpeg":
            Path(args[-1]).write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nhello movie\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(subtitle_support.subprocess, "run", fake_run)

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

    extracted_file = library_dir / "Interstellar (2014).srt"
    translated_file = library_dir / "Interstellar (2014).zh.srt"
    assert result.success is True
    assert result.skipped is False
    assert extracted_file.exists()
    assert translated_file.exists()
    assert "专业译文：hello movie" in translated_file.read_text(encoding="utf-8")


def test_translate_for_import_skips_when_embedded_chinese_subtitle_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")

    def fake_run(args: list[str], capture_output: bool, text: bool, timeout: float) -> subprocess.CompletedProcess[str]:
        assert args[0] == "ffprobe"
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                {
                    "streams": [
                        {
                            "index": 2,
                            "codec_name": "subrip",
                            "tags": {"language": "chi", "title": "简体中文"},
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            stderr="",
        )

    monkeypatch.setattr(subtitle_support.subprocess, "run", fake_run)

    service = SubtitleTranslatorService(api_key="demo-key")
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
    assert "中文字幕轨" in result.message


def test_translate_for_import_skips_when_only_non_text_embedded_english_subtitle_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")

    def fake_run(args: list[str], capture_output: bool, text: bool, timeout: float) -> subprocess.CompletedProcess[str]:
        assert args[0] == "ffprobe"
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                {
                    "streams": [
                        {
                            "index": 2,
                            "codec_name": "hdmv_pgs_subtitle",
                            "tags": {"language": "eng", "title": "English PGS"},
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            stderr="",
        )

    monkeypatch.setattr(subtitle_support.subprocess, "run", fake_run)

    service = SubtitleTranslatorService(api_key="demo-key")
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
    assert "未找到可翻译的外挂字幕或英文内嵌字幕" in result.message


def test_probe_embedded_subtitles_falls_back_to_ffmpeg_when_ffprobe_missing(tmp_path: Path, monkeypatch) -> None:
    target_file = tmp_path / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")

    def fake_run(args: list[str], capture_output: bool, text: bool, timeout: float) -> subprocess.CompletedProcess[str]:
        if args[0] == "ffprobe":
            raise FileNotFoundError("ffprobe")
        assert args[0] == "ffmpeg"
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="",
            stderr="Stream #0:2(eng): Subtitle: subrip (default)\n",
        )

    monkeypatch.setattr(subtitle_support.subprocess, "run", fake_run)

    service = SubtitleTranslatorService(api_key="demo-key")
    streams, error = service._probe_embedded_subtitles(target_file)

    assert error is None
    assert len(streams) == 1
    assert streams[0].stream_index == 2
    assert streams[0].language == "eng"
    assert streams[0].codec_name == "subrip"


def test_probe_embedded_subtitles_ignores_invalid_ffprobe_stream_items(tmp_path: Path, monkeypatch) -> None:
    target_file = tmp_path / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")

    def fake_run(args: list[str], capture_output: bool, text: bool, timeout: float) -> subprocess.CompletedProcess[str]:
        assert args[0] == "ffprobe"
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                {
                    "streams": [
                        {
                            "index": 2,
                            "codec_name": "subrip",
                            "tags": {"language": "eng", "title": "English"},
                        },
                        {
                            "index": "not-a-number",
                            "codec_name": "subrip",
                            "tags": {"language": "eng"},
                        },
                        {"index": -1, "codec_name": "ass", "tags": ["invalid-tags"]},
                        "not-a-dict",
                    ]
                },
                ensure_ascii=False,
            ),
            stderr="",
        )

    monkeypatch.setattr(subtitle_support.subprocess, "run", fake_run)

    service = SubtitleTranslatorService(api_key="demo-key")
    streams, error = service._probe_embedded_subtitles(target_file)

    assert error is None
    assert len(streams) == 1
    assert streams[0].stream_index == 2
    assert streams[0].language == "eng"
    assert streams[0].title == "English"


def test_translate_for_import_fails_when_extracted_embedded_subtitle_file_is_invalid(
    tmp_path: Path,
    monkeypatch,
) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir(parents=True)
    target_file = library_dir / "Interstellar (2014).mkv"
    target_file.write_bytes(b"video")

    def fake_run(args: list[str], capture_output: bool, text: bool, timeout: float) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        assert timeout == 60.0
        if args[0] == "ffprobe":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "index": 2,
                                "codec_name": "subrip",
                                "tags": {"language": "eng", "title": "English"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                stderr="",
            )
        if args[0] == "ffmpeg":
            Path(args[-1]).write_text("hello movie", encoding="utf-8")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {args}")

    def fake_build_subtitle_file(_: Path) -> None:
        return None

    monkeypatch.setattr(subtitle_support.subprocess, "run", fake_run)
    monkeypatch.setattr(subtitle_support, "_build_subtitle_file", fake_build_subtitle_file)

    service = SubtitleTranslatorService(api_key="demo-key")
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
    assert "提取后的字幕文件不可用" in result.message


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


def test_translate_for_import_fails_when_writing_translated_subtitle(tmp_path: Path, monkeypatch) -> None:
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
        return json.dumps({"translations": [f"专业译文：{line}" for line in source_lines]}, ensure_ascii=False)

    original_write_text = Path.write_text

    def failing_write_text(self: Path, data: str, encoding: str | None = None, errors: str | None = None, newline: str | None = None) -> int:
        if self.name.endswith(".zh.srt"):
            raise OSError("disk full")
        return original_write_text(self, data, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "write_text", failing_write_text)

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
    assert "写入字幕文件失败" in result.message


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


def test_request_chat_completion_raises_on_http_error(monkeypatch) -> None:
    client_ctor = Mock()
    post = Mock(
        return_value=httpx.Response(
            401,
            text="unauthorized",
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )
    )
    client_instance = Mock(__enter__=Mock(return_value=Mock(post=post)), __exit__=Mock(return_value=None))
    client_ctor.return_value = client_instance
    monkeypatch.setattr(httpx, "Client", client_ctor)

    service = SubtitleTranslatorService(api_key="demo-key")

    with pytest.raises(RuntimeError, match="HTTP 401"):
        service._request_chat_completion(system_prompt="system", user_payload={"source_lines": ["hello"]})


def test_request_chat_completion_raises_when_response_is_not_json(monkeypatch) -> None:
    client_ctor = Mock()
    response = Mock(status_code=200)
    response.json.side_effect = ValueError("bad json")
    post = Mock(return_value=response)
    client_instance = Mock(__enter__=Mock(return_value=Mock(post=post)), __exit__=Mock(return_value=None))
    client_ctor.return_value = client_instance
    monkeypatch.setattr(httpx, "Client", client_ctor)

    service = SubtitleTranslatorService(api_key="demo-key")

    with pytest.raises(RuntimeError, match="响应不是 JSON"):
        service._request_chat_completion(system_prompt="system", user_payload={"source_lines": ["hello"]})


def test_request_chat_completion_raises_when_content_is_missing(monkeypatch) -> None:
    client_ctor = Mock()
    post = Mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{}]},
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )
    )
    client_instance = Mock(__enter__=Mock(return_value=Mock(post=post)), __exit__=Mock(return_value=None))
    client_ctor.return_value = client_instance
    monkeypatch.setattr(httpx, "Client", client_ctor)

    service = SubtitleTranslatorService(api_key="demo-key")

    with pytest.raises(RuntimeError, match="响应缺少 content 字段"):
        service._request_chat_completion(system_prompt="system", user_payload={"source_lines": ["hello"]})


def test_request_chat_completion_raises_when_content_is_empty(monkeypatch) -> None:
    client_ctor = Mock()
    post = Mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "   "}}]},
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )
    )
    client_instance = Mock(__enter__=Mock(return_value=Mock(post=post)), __exit__=Mock(return_value=None))
    client_ctor.return_value = client_instance
    monkeypatch.setattr(httpx, "Client", client_ctor)

    service = SubtitleTranslatorService(api_key="demo-key")

    with pytest.raises(RuntimeError, match="模型返回空内容"):
        service._request_chat_completion(system_prompt="system", user_payload={"source_lines": ["hello"]})


def test_translate_lines_professional_builds_expected_request_payload() -> None:
    seen_system_prompt: list[str] = []
    seen_user_payload: list[dict[str, object]] = []

    def fake_request(system_prompt: str, user_payload: dict[str, object]) -> str:
        seen_system_prompt.append(system_prompt)
        seen_user_payload.append(user_payload)
        return json.dumps({"translations": ["专业译文：hello"]}, ensure_ascii=False)

    service = SubtitleTranslatorService(
        api_key="demo-key",
        request_chat_completion_func=fake_request,
    )
    result = service._translate_lines_professional(
        source_lines=["hello"],
        movie_title="Interstellar",
    )

    assert result == ["专业译文：hello"]
    assert seen_system_prompt and "专业影视字幕译者" in seen_system_prompt[0]
    assert seen_user_payload == [
        {
            "movie_title": "Interstellar",
            "source_lines": ["hello"],
            "rules": {
                "target_language": "zh-CN",
                "style": "专业影视字幕",
                "return_json_only": True,
                "json_schema": {"translations": ["与 source_lines 等长的中文字符串数组"]},
            },
        }
    ]
