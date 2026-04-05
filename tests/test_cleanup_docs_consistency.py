from __future__ import annotations

from pathlib import Path
import re


def _extract_window_dates(text: str) -> tuple[str, str]:
    start_match = re.search(r"- 开始日期：(\d{4}-\d{2}-\d{2})", text)
    end_match = re.search(r"- 最早可结束日期：(\d{4}-\d{2}-\d{2})", text)
    assert start_match is not None
    assert end_match is not None
    return start_match.group(1), end_match.group(1)


def test_cleanup_verification_window_docs_stay_in_sync() -> None:
    next_step_text = Path("docs/NEXT_STEP.md").read_text(encoding="utf-8")
    status_text = Path("docs/STATUS.md").read_text(encoding="utf-8")
    window_text = Path("docs/CLEANUP_VERIFICATION_WINDOW.md").read_text(encoding="utf-8")

    start_date, end_date = _extract_window_dates(window_text)

    assert f"开始日期固定为 {start_date}" in status_text
    assert f"最早可结束日期固定为 {end_date}" in status_text

    for text in (next_step_text, status_text):
        assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in text
        assert "`tests/test_cleanup_cross_channel_smoke.py`" in text
        assert "真实私聊 smoke" in text
        assert "当前结论" in text
        assert "chat-scoped task_ref -> jobs -> import correlation" in text
        assert "target-missing rejection guidance" in text

