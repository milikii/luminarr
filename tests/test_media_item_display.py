from __future__ import annotations

from app.services.media_item_display import format_title_year


def test_format_title_year_omits_year_when_missing() -> None:
    assert format_title_year("Dune", "") == "Dune"


def test_format_title_year_keeps_existing_year_text() -> None:
    assert format_title_year("Dune", "2021") == "Dune (2021)"
