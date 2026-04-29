from __future__ import annotations

from pathlib import Path


def test_feishu_sdk_install_and_operator_doc_stay_aligned() -> None:
    requirements_text = Path("requirements.txt").read_text(encoding="utf-8")
    getting_started_text = Path("docs/GETTING_STARTED.md").read_text(encoding="utf-8")

    assert "lark-oapi==1.5.3" in requirements_text
    assert getting_started_text.count("lark-oapi==1.5.3") == 0
    assert "标准 `requirements.txt` 已包含 Feishu SDK" in getting_started_text
    assert "是否真的启用 Feishu 长连接，仍取决于你是否同时填写 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`" in getting_started_text
