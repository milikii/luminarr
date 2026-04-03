from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from app.clients.fanart import FanartMovieImages
from app.clients.tmdb import TmdbMovie

LookupMovieFunc = Callable[[str, str], Awaitable[TmdbMovie | None]]
GetMovieImagesFunc = Callable[[str], Awaitable[FanartMovieImages | None]]


@dataclass(frozen=True, slots=True)
class MetadataScrapeInput:
    task_ref: str
    task_id: str
    task_hash: str
    title: str
    year: str
    target_path: str


@dataclass(frozen=True, slots=True)
class MetadataScrapeResult:
    success: bool
    message: str
    metadata_path: str = ""


class MetadataScraperService:
    def __init__(
        self,
        lookup_movie_func: LookupMovieFunc,
        get_movie_images_func: GetMovieImagesFunc,
    ) -> None:
        self._lookup_movie_func = lookup_movie_func
        self._get_movie_images_func = get_movie_images_func

    async def scrape_for_import(self, scrape_input: MetadataScrapeInput) -> MetadataScrapeResult:
        title = scrape_input.title.strip()
        year = scrape_input.year.strip()
        target_path = Path(scrape_input.target_path).expanduser()
        if not title:
            message = "metadata 标题为空，已跳过刮削。"
            _print_colored_error(
                problem=message,
                fix="确认导入目标文件名中包含可识别片名，例如 `Dune (2021).mkv`。",
            )
            return MetadataScrapeResult(success=False, message=message)

        try:
            tmdb_movie = await self._lookup_movie_func(title, year)
        except Exception as exc:
            message = f"TMDB 查询失败：{exc}"
            _print_colored_error(
                problem=message,
                fix="检查 `TMDB_API_KEY`、网络连通性，以及 `TMDB_BASE_URL` 是否可访问。",
            )
            return MetadataScrapeResult(success=False, message=message)
        if tmdb_movie is None:
            message = f"TMDB 未命中：title={title}, year={year or '-'}"
            _print_colored_error(
                problem=message,
                fix="确认电影名和年份是否正确，或先用 `search` 指令确认资源标题。",
            )
            return MetadataScrapeResult(success=False, message=message)

        movie_id = tmdb_movie.tmdb_id.strip()
        if not movie_id:
            message = "TMDB 返回缺少 movie id，无法请求 Fanart。"
            _print_colored_error(
                problem=message,
                fix="检查 TMDB 响应内容是否完整，必要时重试导入流程。",
            )
            return MetadataScrapeResult(success=False, message=message)

        try:
            fanart_images = await self._get_movie_images_func(movie_id)
        except Exception as exc:
            message = f"Fanart 查询失败：{exc}"
            _print_colored_error(
                problem=message,
                fix="检查 `FANART_API_KEY`、网络连通性，以及 `FANART_BASE_URL` 是否可访问。",
            )
            return MetadataScrapeResult(success=False, message=message)

        metadata_path = _resolve_metadata_sidecar_path(target_path)
        payload = {
            "task_ref": scrape_input.task_ref,
            "task_id": scrape_input.task_id,
            "task_hash": scrape_input.task_hash,
            "target_path": str(target_path),
            "tmdb": {
                "id": movie_id,
                "title": tmdb_movie.title,
                "original_title": tmdb_movie.original_title,
                "year": tmdb_movie.year,
            },
            "fanart": {
                "poster_url": fanart_images.poster_url if fanart_images is not None else "",
                "backdrop_url": fanart_images.backdrop_url if fanart_images is not None else "",
            },
        }
        try:
            metadata_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            message = f"写入 metadata 文件失败：{exc}"
            _print_colored_error(
                problem=message,
                fix="检查导入目录写权限和磁盘空间，再重试确认导入。",
            )
            return MetadataScrapeResult(success=False, message=message)

        message = f"metadata 刮削成功：{metadata_path}"
        return MetadataScrapeResult(success=True, message=message, metadata_path=str(metadata_path))


def _resolve_metadata_sidecar_path(target_path: Path) -> Path:
    if target_path.is_dir():
        return target_path / ".luminarr.metadata.json"
    return target_path.with_suffix(".metadata.json")


def _print_colored_error(*, problem: str, fix: str) -> None:
    print(f"\033[31m[元数据刮削失败]\033[0m {problem}", flush=True)
    print(f"\033[33m[处理建议]\033[0m {fix}", flush=True)
