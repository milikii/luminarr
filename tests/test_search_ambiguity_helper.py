from __future__ import annotations

from app.services.search_ambiguity_helper import format_ambiguous_clarification
from app.services.search_query_parser import parse_movie_query


def test_format_ambiguous_clarification_returns_prompt_for_distinct_years() -> None:
    text = format_ambiguous_clarification(
        query="Dune",
        parsed_query=parse_movie_query("Dune"),
        raw_results=(
            {"title": "Dune", "year": 1984},
            {"title": "Dune", "year": 2021},
            {"title": "Dune: Part Two", "year": 2024},
        ),
    )

    assert text is not None
    assert "片名可能有多个版本：Dune" in text
    assert "- Dune (1984)" in text
    assert "- Dune (2021)" in text
    assert "- Dune: Part Two (2024)" in text


def test_format_ambiguous_clarification_skips_query_with_year() -> None:
    text = format_ambiguous_clarification(
        query="Dune 2021",
        parsed_query=parse_movie_query("Dune 2021"),
        raw_results=(
            {"title": "Dune", "year": 1984},
            {"title": "Dune", "year": 2021},
            {"title": "Dune: Part Two", "year": 2024},
        ),
    )

    assert text is None


def test_format_ambiguous_clarification_dedupes_same_title_year() -> None:
    text = format_ambiguous_clarification(
        query="Infernal Affairs",
        parsed_query=parse_movie_query("Infernal Affairs"),
        raw_results=(
            {"title": "Infernal Affairs", "year": 2002},
            {"title": "Infernal Affairs", "year": 2002},
            {"title": "Infernal Affairs II", "year": 2003},
            {"title": "Infernal Affairs III", "year": 2003},
        ),
    )

    assert text is not None
    assert text.count("- Infernal Affairs (2002)") == 1
