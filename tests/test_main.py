from __future__ import annotations

from types import SimpleNamespace

import pytest
from telegram.error import NetworkError

from app.main import _run_application_polling


def test_run_application_polling_prints_colored_fix_hint_on_network_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = SimpleNamespace(run_polling=lambda **_: (_ for _ in ()).throw(NetworkError("dns fail")))

    with pytest.raises(NetworkError):
        _run_application_polling(app)

    captured = capsys.readouterr()
    assert "[Telegram 启动失败]" in captured.out
    assert "[处理建议]" in captured.out
