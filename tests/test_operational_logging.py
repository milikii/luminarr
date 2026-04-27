from __future__ import annotations

from app.operational_logging import emit_operational_log


def test_emit_operational_log_uses_shared_formatter(capsys) -> None:
    emit_operational_log(
        title="测试失败",
        detail="reason=db down",
        fix_hint="检查 SQLite 后重试。",
    )

    output = capsys.readouterr().out
    assert "[测试失败]" in output
    assert "reason=db down" in output
    assert "[处理建议]" in output
    assert "检查 SQLite 后重试。" in output
