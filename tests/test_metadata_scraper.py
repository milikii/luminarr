from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.clients.fanart import FanartMovieImages
from app.clients.tmdb import TmdbMovie
from app.services.metadata_scraper import MetadataScrapeInput, MetadataScraperService


def test_scrape_for_import_writes_metadata_sidecar(tmp_path: Path) -> None:
    target_file = tmp_path / "Interstellar (2014).mkv"
    target_file.write_bytes(b"demo")

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Interstellar"
        assert year == "2014"
        return TmdbMovie(title="Interstellar", original_title="Interstellar", year="2014", tmdb_id="157336")

    async def fake_fanart(_: str) -> FanartMovieImages | None:
        return FanartMovieImages(
            poster_url="https://img.example/poster.jpg",
            backdrop_url="https://img.example/bg.jpg",
        )

    service = MetadataScraperService(fake_tmdb_lookup, fake_fanart)
    result = _run(
        service.scrape_for_import(
            MetadataScrapeInput(
                task_ref="87",
                task_id="87",
                task_hash="hash-87",
                title="Interstellar",
                year="2014",
                target_path=str(target_file),
            )
        )
    )
    assert result.success is True
    metadata_path = target_file.with_suffix(".metadata.json")
    assert metadata_path.exists()
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["tmdb"]["id"] == "157336"
    assert payload["fanart"]["poster_url"] == "https://img.example/poster.jpg"


def test_scrape_for_import_returns_failed_when_tmdb_not_found(tmp_path: Path) -> None:
    target_file = tmp_path / "Unknown (2026).mkv"
    target_file.write_bytes(b"demo")

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return None

    async def fake_fanart(_: str) -> FanartMovieImages | None:
        return None

    service = MetadataScraperService(fake_tmdb_lookup, fake_fanart)
    result = _run(
        service.scrape_for_import(
            MetadataScrapeInput(
                task_ref="87",
                task_id="87",
                task_hash="hash-87",
                title="Unknown",
                year="2026",
                target_path=str(target_file),
            )
        )
    )
    assert result.success is False
    assert "TMDB 未命中" in result.message
    assert not target_file.with_suffix(".metadata.json").exists()


def test_scrape_for_import_succeeds_without_fanart_images(tmp_path: Path) -> None:
    target_file = tmp_path / "The Matrix (1999).mkv"
    target_file.write_bytes(b"demo")

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="The Matrix", original_title="The Matrix", year="1999", tmdb_id="603")

    async def fake_fanart(_: str) -> FanartMovieImages | None:
        return None

    service = MetadataScraperService(fake_tmdb_lookup, fake_fanart)
    result = _run(
        service.scrape_for_import(
            MetadataScrapeInput(
                task_ref="603",
                task_id="603",
                task_hash="hash-603",
                title="The Matrix",
                year="1999",
                target_path=str(target_file),
            )
        )
    )
    assert result.success is True
    metadata_path = target_file.with_suffix(".metadata.json")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["tmdb"]["id"] == "603"
    assert payload["fanart"]["poster_url"] == ""
    assert payload["fanart"]["backdrop_url"] == ""


def _run(coroutine):
    return asyncio.run(coroutine)
