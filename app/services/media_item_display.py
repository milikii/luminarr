from __future__ import annotations


def format_title_year(title: str, year: str) -> str:
    year_text = year if year else "-"
    return f"{title} ({year_text})"
