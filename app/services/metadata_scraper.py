from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape
import re

from app.clients.fanart import FanartMovieImages
from app.clients.tmdb import TmdbMovie

LookupMovieFunc = Callable[[str, str], Awaitable[TmdbMovie | None]]
LookupMovieByTmdbIdFunc = Callable[[str], Awaitable[TmdbMovie | None]]
GetMovieImagesFunc = Callable[[str], Awaitable[FanartMovieImages | None]]
DownloadImageFunc = Callable[[str], Awaitable[bytes]]

WRITE_STRATEGY_OVERWRITE = "overwrite"
WRITE_STRATEGY_MISSING_ONLY = "missing_only"
WRITE_STRATEGY_SKIP = "skip"


@dataclass(frozen=True, slots=True)
class MetadataScrapeInput:
    task_ref: str
    task_id: str
    task_hash: str
    title: str
    year: str
    target_path: str
    tmdb_id: str = ""


@dataclass(frozen=True, slots=True)
class MetadataScrapeResult:
    success: bool
    message: str
    metadata_path: str = ""
    nfo_path: str = ""


class MetadataScraperService:
    def __init__(
        self,
        lookup_movie_func: LookupMovieFunc,
        get_movie_images_func: GetMovieImagesFunc,
        lookup_movie_by_tmdb_id_func: LookupMovieByTmdbIdFunc | None = None,
        download_image_func: DownloadImageFunc | None = None,
    ) -> None:
        self._lookup_movie_func = lookup_movie_func
        self._get_movie_images_func = get_movie_images_func
        self._lookup_movie_by_tmdb_id_func = lookup_movie_by_tmdb_id_func
        self._download_image_func = download_image_func

    async def scrape_for_import(self, scrape_input: MetadataScrapeInput) -> MetadataScrapeResult:
        title = scrape_input.title.strip()
        year = scrape_input.year.strip()
        tmdb_id = scrape_input.tmdb_id.strip()
        target_path = Path(scrape_input.target_path).expanduser()
        if not title and not tmdb_id:
            message = "metadata 标题为空，已跳过刮削。"
            _print_colored_error(
                problem=message,
                fix="确认导入目标文件名中包含可识别片名，例如 `Dune (2021).mkv`。",
            )
            return MetadataScrapeResult(success=False, message=message)

        tmdb_movie, error_result = await self._resolve_tmdb_movie(title=title, year=year, tmdb_id=tmdb_id)
        if error_result is not None:
            return error_result
        assert tmdb_movie is not None

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
        nfo_path = _resolve_nfo_sidecar_path(target_path)
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
        error_result = _write_text_artifact(
            artifact_path=metadata_path,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            label="metadata",
            write_strategy=WRITE_STRATEGY_OVERWRITE,
        )
        if error_result is not None:
            return error_result
        error_result = _write_text_artifact(
            artifact_path=nfo_path,
            content=_render_movie_nfo(tmdb_movie=tmdb_movie, fanart_images=fanart_images),
            label="NFO",
            write_strategy=WRITE_STRATEGY_MISSING_ONLY,
        )
        if error_result is not None:
            return error_result
        image_artifacts, error_result = await self._write_image_artifacts(
            target_path=target_path,
            fanart_images=fanart_images,
        )
        if error_result is not None:
            return error_result

        image_suffix = ""
        if image_artifacts:
            image_suffix = "；图片：" + "、".join(str(path) for path in image_artifacts)
        message = f"metadata 刮削成功：{metadata_path}；NFO：{nfo_path}{image_suffix}"
        return MetadataScrapeResult(
            success=True,
            message=message,
            metadata_path=str(metadata_path),
            nfo_path=str(nfo_path),
        )

    async def _resolve_tmdb_movie(
        self,
        *,
        title: str,
        year: str,
        tmdb_id: str,
    ) -> tuple[TmdbMovie | None, MetadataScrapeResult | None]:
        if tmdb_id and self._lookup_movie_by_tmdb_id_func is not None:
            try:
                tmdb_movie = await self._lookup_movie_by_tmdb_id_func(tmdb_id)
            except Exception as exc:
                message = f"TMDB 详情查询失败：{exc}"
                _print_colored_error(
                    problem=message,
                    fix="检查 `TMDB_API_KEY`、网络连通性，以及 `TMDB_BASE_URL` 是否可访问；如果这是已确认媒体身份，优先确认 `tmdb_id` 是否仍有效。",
                )
                return None, MetadataScrapeResult(success=False, message=message)
            if tmdb_movie is None:
                message = f"TMDB 未命中：tmdb_id={tmdb_id}"
                _print_colored_error(
                    problem=message,
                    fix="检查这次导入链里保存的 `media_identity.tmdb_id` 是否正确；当前不会回退到 title/year 二次猜片。",
                )
                return None, MetadataScrapeResult(success=False, message=message)
            return _resolve_chinese_scrape_movie(
                tmdb_movie=tmdb_movie,
                failure_message=f"TMDB 未返回中文标题：tmdb_id={tmdb_id}",
            )

        try:
            tmdb_movie = await self._lookup_movie_func(title, year)
        except Exception as exc:
            message = f"TMDB 查询失败：{exc}"
            _print_colored_error(
                problem=message,
                fix="检查 `TMDB_API_KEY`、网络连通性，以及 `TMDB_BASE_URL` 是否可访问。",
            )
            return None, MetadataScrapeResult(success=False, message=message)
        if tmdb_movie is None:
            message = f"TMDB 未命中：title={title}, year={year or '-'}"
            _print_colored_error(
                problem=message,
                fix="确认电影名和年份是否正确，或先用 `search` 指令确认资源标题。",
            )
            return None, MetadataScrapeResult(success=False, message=message)
        if tmdb_movie.tmdb_id and self._lookup_movie_by_tmdb_id_func is not None:
            try:
                localized_movie = await self._lookup_movie_by_tmdb_id_func(tmdb_movie.tmdb_id)
            except Exception as exc:
                message = f"TMDB 详情查询失败：{exc}"
                _print_colored_error(
                    problem=message,
                    fix="检查 `TMDB_API_KEY`、网络连通性，以及 `TMDB_BASE_URL` 是否可访问；当前不会回退成英文标题刮削。",
                )
                return None, MetadataScrapeResult(success=False, message=message)
            if localized_movie is None:
                message = f"TMDB 未命中：tmdb_id={tmdb_movie.tmdb_id}"
                _print_colored_error(
                    problem=message,
                    fix="检查搜索确认后落下来的 `tmdb_id` 是否仍有效；当前不会回退成 title/year 英文刮削。",
                )
                return None, MetadataScrapeResult(success=False, message=message)
            return _resolve_chinese_scrape_movie(
                tmdb_movie=localized_movie,
                failure_message=f"TMDB 未返回中文标题：tmdb_id={tmdb_movie.tmdb_id}",
            )
        return _resolve_chinese_scrape_movie(
            tmdb_movie=tmdb_movie,
            failure_message=f"TMDB 未返回中文标题：title={title}, year={year or '-'}",
        )

    async def _write_image_artifacts(
        self,
        *,
        target_path: Path,
        fanart_images: FanartMovieImages | None,
    ) -> tuple[list[Path], MetadataScrapeResult | None]:
        if fanart_images is None or self._download_image_func is None:
            return [], None

        artifact_specs = _build_image_artifact_specs(target_path=target_path, fanart_images=fanart_images)
        created_paths: list[Path] = []
        for label, image_url, artifact_path in artifact_specs:
            if _resolve_write_strategy_for_path(
                artifact_path=artifact_path,
                default_strategy=WRITE_STRATEGY_MISSING_ONLY,
            ) == WRITE_STRATEGY_SKIP:
                continue
            try:
                payload = await self._download_image_func(image_url)
            except Exception as exc:
                _cleanup_written_artifacts(created_paths)
                message = f"下载 {label} 图片失败：{exc}"
                _print_colored_error(
                    problem=message,
                    fix="检查图片 URL、代理和网络连通性；当前 metadata / NFO 已写入，但图片产物需要修复后重试。",
                )
                return [], MetadataScrapeResult(success=False, message=message)
            if not payload:
                _cleanup_written_artifacts(created_paths)
                message = f"下载 {label} 图片失败：响应为空"
                _print_colored_error(
                    problem=message,
                    fix="检查图片 URL 是否仍可访问；当前 metadata / NFO 已写入，但图片产物需要修复后重试。",
                )
                return [], MetadataScrapeResult(success=False, message=message)
            try:
                artifact_path.write_bytes(payload)
            except Exception as exc:
                _cleanup_written_artifacts(created_paths)
                message = f"写入 {label} 图片失败：{exc}"
                _print_colored_error(
                    problem=message,
                    fix="检查导入目录写权限和磁盘空间，再重试确认导入。",
                )
                return [], MetadataScrapeResult(success=False, message=message)
            created_paths.append(artifact_path)
        return created_paths, None


def _resolve_metadata_sidecar_path(target_path: Path) -> Path:
    if target_path.is_dir():
        return target_path / ".luminarr.metadata.json"
    return target_path.with_suffix(".metadata.json")


def _resolve_nfo_sidecar_path(target_path: Path) -> Path:
    if target_path.is_file():
        return target_path.with_suffix(".nfo")
    primary_video_path = _find_primary_video_file(target_path)
    if primary_video_path is not None:
        return primary_video_path.with_suffix(".nfo")
    return target_path / "movie.nfo"


def _find_primary_video_file(target_path: Path) -> Path | None:
    if not target_path.exists() or not target_path.is_dir():
        return None
    video_suffixes = {".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".ts", ".m2ts", ".webm"}
    candidates = sorted(
        candidate
        for candidate in target_path.rglob("*")
        if candidate.is_file() and candidate.suffix.lower() in video_suffixes
    )
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    normalized_dir_name = _normalize_for_match(target_path.name)
    for candidate in candidates:
        if _normalize_for_match(candidate.stem) == normalized_dir_name:
            return candidate
    return None


def _render_movie_nfo(*, tmdb_movie: TmdbMovie, fanart_images: FanartMovieImages | None) -> str:
    lines = [
        "<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"yes\"?>",
        "<movie>",
        f"  <title>{escape(tmdb_movie.title)}</title>",
        f"  <originaltitle>{escape(tmdb_movie.original_title or tmdb_movie.title)}</originaltitle>",
    ]
    if tmdb_movie.year:
        lines.append(f"  <year>{escape(tmdb_movie.year)}</year>")
    if tmdb_movie.tmdb_id:
        lines.append(f"  <tmdbid>{escape(tmdb_movie.tmdb_id)}</tmdbid>")
        lines.append(f"  <uniqueid type=\"tmdb\" default=\"true\">{escape(tmdb_movie.tmdb_id)}</uniqueid>")
    if fanart_images is not None and fanart_images.poster_url:
        lines.append(f"  <thumb aspect=\"poster\">{escape(fanart_images.poster_url)}</thumb>")
    if fanart_images is not None and fanart_images.backdrop_url:
        lines.extend(
            [
                "  <fanart>",
                f"    <thumb>{escape(fanart_images.backdrop_url)}</thumb>",
                "  </fanart>",
            ]
        )
    lines.append("</movie>")
    return "\n".join(lines) + "\n"


def _normalize_for_match(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def _build_image_artifact_specs(
    *,
    target_path: Path,
    fanart_images: FanartMovieImages,
) -> list[tuple[str, str, Path]]:
    specs: list[tuple[str, str, Path]] = []
    if fanart_images.poster_url:
        specs.append(("poster", fanart_images.poster_url, _resolve_image_artifact_path(target_path, "poster", fanart_images.poster_url)))
    if fanart_images.backdrop_url:
        specs.append(("backdrop", fanart_images.backdrop_url, _resolve_image_artifact_path(target_path, "backdrop", fanart_images.backdrop_url)))
    return specs


def _resolve_image_artifact_path(target_path: Path, label: str, image_url: str) -> Path:
    suffix = _resolve_image_suffix(image_url)
    if target_path.is_file():
        return target_path.with_name(f"{target_path.stem}-{label}{suffix}")
    return target_path / f"{label}{suffix}"


def _resolve_image_suffix(image_url: str) -> str:
    path = urlparse(image_url).path
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return ".jpg"


def _cleanup_written_artifacts(created_paths: list[Path]) -> None:
    for artifact_path in reversed(created_paths):
        try:
            if artifact_path.exists():
                artifact_path.unlink()
        except OSError:
            continue


def _print_colored_error(*, problem: str, fix: str) -> None:
    print(f"\033[31m[元数据刮削失败]\033[0m {problem}", flush=True)
    print(f"\033[33m[处理建议]\033[0m {fix}", flush=True)


def _resolve_chinese_scrape_movie(
    *,
    tmdb_movie: TmdbMovie,
    failure_message: str,
) -> tuple[TmdbMovie | None, MetadataScrapeResult | None]:
    chinese_title = _resolve_preferred_chinese_title(tmdb_movie)
    if not chinese_title:
        _print_colored_error(
            problem=failure_message,
            fix="检查 TMDB 对应条目是否存在 `zh-CN` 本地化标题；当前为避免最终刮削落英文标题，会直接 fail-closed。",
        )
        return None, MetadataScrapeResult(success=False, message=failure_message)
    return (
        TmdbMovie(
            title=chinese_title,
            original_title=tmdb_movie.original_title or tmdb_movie.title,
            year=tmdb_movie.year,
            tmdb_id=tmdb_movie.tmdb_id,
            media_type=tmdb_movie.media_type,
        ),
        None,
    )


def _resolve_preferred_chinese_title(tmdb_movie: TmdbMovie) -> str:
    if _contains_chinese(tmdb_movie.title):
        return tmdb_movie.title.strip()
    if _contains_chinese(tmdb_movie.original_title):
        return tmdb_movie.original_title.strip()
    return ""


def _contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def _write_text_artifact(
    *,
    artifact_path: Path,
    content: str,
    label: str,
    write_strategy: str,
) -> MetadataScrapeResult | None:
    resolved_strategy = _resolve_write_strategy_for_path(
        artifact_path=artifact_path,
        default_strategy=write_strategy,
    )
    if resolved_strategy == WRITE_STRATEGY_SKIP:
        return None
    try:
        artifact_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        message = f"写入 {label} 文件失败：{exc}"
        _print_colored_error(
            problem=message,
            fix="检查导入目录写权限和磁盘空间，再重试确认导入。",
        )
        return MetadataScrapeResult(success=False, message=message)
    return None


def _resolve_write_strategy_for_path(*, artifact_path: Path, default_strategy: str) -> str:
    if default_strategy == WRITE_STRATEGY_OVERWRITE:
        return WRITE_STRATEGY_OVERWRITE
    if default_strategy == WRITE_STRATEGY_MISSING_ONLY and artifact_path.exists():
        return WRITE_STRATEGY_SKIP
    return default_strategy
