from __future__ import annotations


def format_title_year(title: str, year: str) -> str:
    cleaned_title = title.strip()
    cleaned_year = year.strip()
    if not cleaned_year:
        return cleaned_title
    return f"{cleaned_title} ({cleaned_year})"
