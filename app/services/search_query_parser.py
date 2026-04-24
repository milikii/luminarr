from __future__ import annotations

from dataclasses import dataclass

from app.search_title_normalization import finalize_parsed_query_title, normalize_spaces, strip_trailing_query_noise
from app.services.media_name_parser import parse_media_name


@dataclass(frozen=True, slots=True)
class ParsedMovieQuery:
    title: str
    year: str


def parse_movie_query(query: str) -> ParsedMovieQuery:
    cleaned_query = normalize_spaces(query)
    if not cleaned_query:
        return ParsedMovieQuery(title="", year="")

    parsed_name = parse_media_name(cleaned_query)
    year = str(parsed_name.year) if parsed_name.year is not None else ""
    title = finalize_parsed_query_title(
        cleaned_query=cleaned_query,
        parsed_title=parsed_name.title or cleaned_query,
        parsed_year=year,
    )
    title = strip_trailing_query_noise(title)
    return ParsedMovieQuery(title=title, year=year)
