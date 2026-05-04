from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

import httpx

from app.clients.fanart import FanartMovieImages
from app.clients.tmdb import TmdbCreditPerson, TmdbMovie
from app.operational_logging import emit_operational_log
from app.services.cast_localization import (
    CastLocalizationInput,
    CastLocalizationService,
)

LookupMovieFunc = Callable[[str, str], Awaitable[TmdbMovie | None]]
LookupMovieByTmdbIdFunc = Callable[[str], Awaitable[TmdbMovie | None]]
LookupTvByTmdbIdFunc = Callable[[str], Awaitable[TmdbMovie | None]]
GetMovieImagesFunc = Callable[[str], Awaitable[FanartMovieImages | None]]
DownloadImageFunc = Callable[[str], Awaitable[bytes]]
LookupMediaCreditsFunc = Callable[[str, str], Awaitable[tuple[TmdbCreditPerson, ...]]]

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
        lookup_tv_by_tmdb_id_func: LookupTvByTmdbIdFunc | None = None,
        download_image_func: DownloadImageFunc | None = None,
        lookup_movie_credits_func: LookupMediaCreditsFunc | None = None,
        lookup_tv_credits_func: LookupMediaCreditsFunc | None = None,
        cast_localization_service: CastLocalizationService | None = None,
    ) -> None:
        self._lookup_movie_func = lookup_movie_func
        self._get_movie_images_func = get_movie_images_func
        self._lookup_movie_by_tmdb_id_func = lookup_movie_by_tmdb_id_func
        self._lookup_tv_by_tmdb_id_func = lookup_tv_by_tmdb_id_func
        self._download_image_func = download_image_func
        self._lookup_movie_credits_func = lookup_movie_credits_func
        self._lookup_tv_credits_func = lookup_tv_credits_func
        self._cast_localization_service = cast_localization_service

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
        except (httpx.HTTPError, ValueError) as exc:
            message = f"Fanart 查询失败：{exc}"
            _print_colored_error(
                problem=message,
                fix="检查 `FANART_API_KEY`、网络连通性，以及 `FANART_BASE_URL` 是否可访问。",
            )
            return MetadataScrapeResult(success=False, message=message)
        fanart_images = _with_tmdb_image_fallback(
            tmdb_movie=tmdb_movie,
            fanart_images=fanart_images,
        )

        if target_path.is_dir():
            metadata_path = target_path / ".luminarr.metadata.json"
        else:
            metadata_path = target_path.with_suffix(".metadata.json")
        if target_path.is_file():
            nfo_path = target_path.with_suffix(".nfo")
        else:
            primary_video_path = None
            if target_path.exists() and target_path.is_dir():
                video_suffixes = {".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".ts", ".m2ts", ".webm"}
                candidates = sorted(
                    candidate
                    for candidate in target_path.rglob("*")
                    if candidate.is_file() and candidate.suffix.lower() in video_suffixes
                )
                if candidates:
                    if len(candidates) == 1:
                        primary_video_path = candidates[0]
                    else:
                        normalized_dir_name = "".join(ch for ch in target_path.name.casefold() if ch.isalnum())
                        for candidate in candidates:
                            if "".join(ch for ch in candidate.stem.casefold() if ch.isalnum()) == normalized_dir_name:
                                primary_video_path = candidate
                                break
            if primary_video_path is not None:
                nfo_path = primary_video_path.with_suffix(".nfo")
            else:
                nfo_path = target_path / "movie.nfo"
        localized_credits, reference_credits = await self._lookup_media_credit_truth(tmdb_movie)
        subtitle_translation_payload = _build_subtitle_translation_payload(
            localized_credits=localized_credits,
            reference_credits=reference_credits,
        )
        cast_truth = _build_cast_truth(
            localized_credits=localized_credits,
            reference_credits=reference_credits,
        )
        cast_truth = await self._localize_cast_truth(
            tmdb_movie=tmdb_movie,
            cast_truth=cast_truth,
        )
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
                "media_type": tmdb_movie.media_type,
                "overview": tmdb_movie.overview,
                "popularity": tmdb_movie.popularity,
                "vote_count": tmdb_movie.vote_count,
                "vote_average": tmdb_movie.vote_average,
                "genres": [dict(row) for row in tmdb_movie.genres],
                "countries": [dict(row) for row in tmdb_movie.countries],
                "studios": [dict(row) for row in tmdb_movie.studios],
            },
            "fanart": {
                "poster_url": fanart_images.poster_url if fanart_images is not None else "",
                "backdrop_url": fanart_images.backdrop_url if fanart_images is not None else "",
            },
        }
        if cast_truth:
            payload["tmdb"]["cast"] = cast_truth
        if subtitle_translation_payload is not None:
            payload["subtitle_translation"] = subtitle_translation_payload
        if _resolve_write_strategy_for_path(
            artifact_path=metadata_path,
            default_strategy=WRITE_STRATEGY_OVERWRITE,
        ) != WRITE_STRATEGY_SKIP:
            try:
                metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                message = f"写入 metadata 文件失败：{exc}"
                _print_colored_error(
                    problem=message,
                    fix="检查导入目录写权限和磁盘空间，再重试确认导入。",
                )
                return MetadataScrapeResult(success=False, message=message)
        if _resolve_write_strategy_for_path(
            artifact_path=nfo_path,
            default_strategy=WRITE_STRATEGY_MISSING_ONLY,
        ) != WRITE_STRATEGY_SKIP:
            try:
                nfo_lines = [
                    "<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"yes\"?>",
                    "<movie>",
                    f"  <title>{escape(tmdb_movie.title)}</title>",
                    f"  <originaltitle>{escape(tmdb_movie.original_title or tmdb_movie.title)}</originaltitle>",
                ]
                if tmdb_movie.year:
                    nfo_lines.append(f"  <year>{escape(tmdb_movie.year)}</year>")
                if tmdb_movie.tmdb_id:
                    nfo_lines.append(f"  <tmdbid>{escape(tmdb_movie.tmdb_id)}</tmdbid>")
                    nfo_lines.append(f"  <uniqueid type=\"tmdb\" default=\"true\">{escape(tmdb_movie.tmdb_id)}</uniqueid>")
                if tmdb_movie.overview:
                    nfo_lines.append(f"  <plot>{escape(tmdb_movie.overview)}</plot>")
                if tmdb_movie.vote_average > 0:
                    nfo_lines.append(f"  <rating>{escape(str(tmdb_movie.vote_average))}</rating>")
                if tmdb_movie.vote_count > 0:
                    nfo_lines.append(f"  <votes>{escape(str(tmdb_movie.vote_count))}</votes>")
                for genre in tmdb_movie.genres:
                    genre_name = str(genre.get("name", "")).strip()
                    if genre_name:
                        nfo_lines.append(f"  <genre>{escape(genre_name)}</genre>")
                for country in tmdb_movie.countries:
                    country_name = str(country.get("name", "")).strip()
                    if country_name:
                        nfo_lines.append(f"  <country>{escape(country_name)}</country>")
                for studio in tmdb_movie.studios:
                    studio_name = str(studio.get("name", "")).strip()
                    if studio_name:
                        nfo_lines.append(f"  <studio>{escape(studio_name)}</studio>")
                for cast_member in cast_truth:
                    cast_name = str(cast_member.get("name", "")).strip()
                    cast_role = str(cast_member.get("character", "")).strip()
                    cast_sort_name = str(cast_member.get("original_name", "")).strip()
                    cast_thumb = str(cast_member.get("profile_image_url", "")).strip()
                    if not cast_name:
                        continue
                    nfo_lines.append("  <actor>")
                    nfo_lines.append(f"    <name>{escape(cast_name)}</name>")
                    if cast_role:
                        nfo_lines.append(f"    <role>{escape(cast_role)}</role>")
                    if cast_sort_name:
                        nfo_lines.append(f"    <sortname>{escape(cast_sort_name)}</sortname>")
                    if cast_thumb:
                        nfo_lines.append(f"    <thumb>{escape(cast_thumb)}</thumb>")
                    nfo_lines.append("  </actor>")
                if fanart_images is not None and fanart_images.poster_url:
                    nfo_lines.append(f"  <thumb aspect=\"poster\">{escape(fanart_images.poster_url)}</thumb>")
                if fanart_images is not None and fanart_images.backdrop_url:
                    nfo_lines.extend(
                        [
                            "  <fanart>",
                            f"    <thumb>{escape(fanart_images.backdrop_url)}</thumb>",
                            "  </fanart>",
                        ]
                    )
                nfo_lines.append("</movie>")
                nfo_path.write_text("\n".join(nfo_lines) + "\n", encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                message = f"写入 NFO 文件失败：{exc}"
                _print_colored_error(
                    problem=message,
                    fix="检查导入目录写权限和磁盘空间，再重试确认导入。",
                )
                return MetadataScrapeResult(success=False, message=message)
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

    async def _localize_cast_truth(
        self,
        *,
        tmdb_movie: TmdbMovie,
        cast_truth: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if self._cast_localization_service is None or not cast_truth:
            return cast_truth
        localization_input = CastLocalizationInput(
            title=tmdb_movie.title,
            original_title=tmdb_movie.original_title,
            year=tmdb_movie.year,
            tmdb_id=tmdb_movie.tmdb_id,
            cast_truth=tuple(dict(row) for row in cast_truth),
        )
        try:
            matches = await self._cast_localization_service.localize(localization_input=localization_input)
        except Exception as exc:
            emit_operational_log(
                title="演员中文化补充失败",
                detail=(
                    f"title={tmdb_movie.title or '-'} "
                    f"original_title={tmdb_movie.original_title or '-'} "
                    f"year={tmdb_movie.year or '-'} 错误={exc}"
                ),
                fix_hint="检查 AI cast localization 配置、可达性与响应结构；当前会软降级回 TMDB-only cast truth。",
            )
            return cast_truth
        if not matches:
            return cast_truth
        match_by_cast_id = {match.cast_id.strip(): match for match in matches if match.cast_id.strip()}
        match_by_order = {match.order: match for match in matches if match.order >= 0}
        enriched_truth: list[dict[str, object]] = []
        for index, cast_member in enumerate(cast_truth):
            merged = dict(cast_member)
            cast_id = str(cast_member.get("id", "")).strip()
            order_value = cast_member.get("order")
            order = order_value if isinstance(order_value, int) else index
            match = match_by_cast_id.get(cast_id) or match_by_order.get(order)
            if match is not None:
                localized_name = match.localized_name.strip()
                localized_character = match.localized_character.strip()
                if localized_name and _contains_cjk(localized_name):
                    merged["name"] = localized_name
                if localized_character and _contains_cjk(localized_character):
                    merged["character"] = localized_character
            enriched_truth.append(merged)
        return enriched_truth

    async def _lookup_media_credit_truth(
        self,
        tmdb_movie: TmdbMovie,
    ) -> tuple[tuple[TmdbCreditPerson, ...], tuple[TmdbCreditPerson, ...]]:
        lookup_func = self._resolve_media_credits_lookup(tmdb_movie.media_type)
        if lookup_func is None or not tmdb_movie.tmdb_id.strip():
            return (), ()
        try:
            localized_credits = await lookup_func(tmdb_movie.tmdb_id, "zh-CN")
            reference_credits = await lookup_func(tmdb_movie.tmdb_id, "en-US")
        except (httpx.HTTPError, ValueError) as exc:
            emit_operational_log(
                title="字幕人名映射生成失败",
                detail=f"tmdb_id={tmdb_movie.tmdb_id or '-'} media_type={tmdb_movie.media_type or '-'} 错误={exc}",
                fix_hint="检查 TMDB credits 接口、网络与本地化响应；当前会回退到无 trusted name map 的字幕翻译。",
            )
            return (), ()
        return localized_credits, reference_credits

    def _resolve_media_credits_lookup(self, media_type: str) -> LookupMediaCreditsFunc | None:
        if media_type == "tv":
            return self._lookup_tv_credits_func
        return self._lookup_movie_credits_func

    async def _resolve_tmdb_movie(
        self,
        *,
        title: str,
        year: str,
        tmdb_id: str,
    ) -> tuple[TmdbMovie | None, MetadataScrapeResult | None]:
        if tmdb_id and (
            self._lookup_movie_by_tmdb_id_func is not None or self._lookup_tv_by_tmdb_id_func is not None
        ):
            tmdb_movie, error_result = await self._lookup_localized_media_by_tmdb_id(tmdb_id)
            if error_result is not None:
                return None, error_result
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
        except (httpx.HTTPError, ValueError) as exc:
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
        if tmdb_movie.tmdb_id and (
            self._lookup_movie_by_tmdb_id_func is not None or self._lookup_tv_by_tmdb_id_func is not None
        ):
            localized_movie, error_result = await self._lookup_localized_media_by_tmdb_id(tmdb_movie.tmdb_id)
            if error_result is not None:
                return None, error_result
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

    async def _lookup_localized_media_by_tmdb_id(
        self,
        tmdb_id: str,
    ) -> tuple[TmdbMovie | None, MetadataScrapeResult | None]:
        for lookup_func in (self._lookup_movie_by_tmdb_id_func, self._lookup_tv_by_tmdb_id_func):
            if lookup_func is None:
                continue
            try:
                tmdb_movie = await lookup_func(tmdb_id)
            except httpx.HTTPStatusError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    continue
                message = f"TMDB 详情查询失败：{exc}"
                _print_colored_error(
                    problem=message,
                    fix="检查 `TMDB_API_KEY`、网络连通性，以及 `TMDB_BASE_URL` 是否可访问；如果这是已确认媒体身份，优先确认 `tmdb_id` 是否仍有效。",
                )
                return None, MetadataScrapeResult(success=False, message=message)
            except (httpx.HTTPError, ValueError) as exc:
                message = f"TMDB 详情查询失败：{exc}"
                _print_colored_error(
                    problem=message,
                    fix="检查 `TMDB_API_KEY`、网络连通性，以及 `TMDB_BASE_URL` 是否可访问；如果这是已确认媒体身份，优先确认 `tmdb_id` 是否仍有效。",
                )
                return None, MetadataScrapeResult(success=False, message=message)
            if tmdb_movie is not None:
                return tmdb_movie, None
        return None, None

    async def _write_image_artifacts(
        self,
        *,
        target_path: Path,
        fanart_images: FanartMovieImages | None,
    ) -> tuple[list[Path], MetadataScrapeResult | None]:
        if fanart_images is None or self._download_image_func is None:
            return [], None

        def cleanup_written_artifacts() -> None:
            for artifact_path in reversed(created_paths):
                try:
                    if artifact_path.exists():
                        artifact_path.unlink()
                except OSError:
                    continue

        artifact_specs: list[tuple[str, str, Path]] = []
        if fanart_images.poster_url:
            poster_suffix = Path(urlparse(fanart_images.poster_url).path).suffix.lower()
            if poster_suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                poster_suffix = ".jpg"
            if target_path.is_file():
                poster_path = target_path.with_name(f"{target_path.stem}-poster{poster_suffix}")
            else:
                poster_path = target_path / f"poster{poster_suffix}"
            artifact_specs.append(("poster", fanart_images.poster_url, poster_path))
        if fanart_images.backdrop_url:
            backdrop_suffix = Path(urlparse(fanart_images.backdrop_url).path).suffix.lower()
            if backdrop_suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                backdrop_suffix = ".jpg"
            if target_path.is_file():
                backdrop_path = target_path.with_name(f"{target_path.stem}-backdrop{backdrop_suffix}")
            else:
                backdrop_path = target_path / f"backdrop{backdrop_suffix}"
            artifact_specs.append(("backdrop", fanart_images.backdrop_url, backdrop_path))
        created_paths: list[Path] = []
        for label, image_url, artifact_path in artifact_specs:
            if _resolve_write_strategy_for_path(
                artifact_path=artifact_path,
                default_strategy=WRITE_STRATEGY_MISSING_ONLY,
            ) == WRITE_STRATEGY_SKIP:
                continue
            try:
                payload = await self._download_image_func(image_url)
            except (httpx.HTTPError, ValueError) as exc:
                cleanup_written_artifacts()
                message = f"下载 {label} 图片失败：{exc}"
                _print_colored_error(
                    problem=message,
                    fix="检查图片 URL、代理和网络连通性；当前 metadata / NFO 已写入，但图片产物需要修复后重试。",
                )
                return [], MetadataScrapeResult(success=False, message=message)
            if not payload:
                cleanup_written_artifacts()
                message = f"下载 {label} 图片失败：响应为空"
                _print_colored_error(
                    problem=message,
                    fix="检查图片 URL 是否仍可访问；当前 metadata / NFO 已写入，但图片产物需要修复后重试。",
                )
                return [], MetadataScrapeResult(success=False, message=message)
            try:
                artifact_path.write_bytes(payload)
            except OSError as exc:
                cleanup_written_artifacts()
                message = f"写入 {label} 图片失败：{exc}"
                _print_colored_error(
                    problem=message,
                    fix="检查导入目录写权限和磁盘空间，再重试确认导入。",
                )
                return [], MetadataScrapeResult(success=False, message=message)
            created_paths.append(artifact_path)
        return created_paths, None

def _print_colored_error(*, problem: str, fix: str) -> None:
    emit_operational_log(title="元数据刮削失败", detail=problem, fix_hint=fix)


def _with_tmdb_image_fallback(
    *,
    tmdb_movie: TmdbMovie,
    fanart_images: FanartMovieImages | None,
) -> FanartMovieImages | None:
    tmdb_poster_url = _build_tmdb_image_url(tmdb_movie.poster_path)
    tmdb_backdrop_url = _build_tmdb_image_url(tmdb_movie.backdrop_path)
    poster_url = fanart_images.poster_url if fanart_images is not None else ""
    backdrop_url = fanart_images.backdrop_url if fanart_images is not None else ""
    resolved_poster_url = poster_url or tmdb_poster_url
    resolved_backdrop_url = backdrop_url or tmdb_backdrop_url
    if not resolved_poster_url and not resolved_backdrop_url:
        return fanart_images
    return FanartMovieImages(
        poster_url=resolved_poster_url,
        backdrop_url=resolved_backdrop_url,
    )


def _build_tmdb_image_url(image_path: str) -> str:
    cleaned_path = image_path.strip()
    if not cleaned_path:
        return ""
    if cleaned_path.startswith("http://") or cleaned_path.startswith("https://"):
        return cleaned_path
    if not cleaned_path.startswith("/"):
        cleaned_path = f"/{cleaned_path}"
    return f"https://image.tmdb.org/t/p/original{cleaned_path}"


def _resolve_chinese_scrape_movie(
    *,
    tmdb_movie: TmdbMovie,
    failure_message: str,
) -> tuple[TmdbMovie | None, MetadataScrapeResult | None]:
    chinese_title = ""
    if re.search(r"[\u4e00-\u9fff]", tmdb_movie.title):
        chinese_title = tmdb_movie.title.strip()
    elif re.search(r"[\u4e00-\u9fff]", tmdb_movie.original_title):
        chinese_title = tmdb_movie.original_title.strip()
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
            poster_path=tmdb_movie.poster_path,
            backdrop_path=tmdb_movie.backdrop_path,
            overview=tmdb_movie.overview,
            popularity=tmdb_movie.popularity,
            vote_count=tmdb_movie.vote_count,
            vote_average=tmdb_movie.vote_average,
            genres=tmdb_movie.genres,
            countries=tmdb_movie.countries,
            studios=tmdb_movie.studios,
        ),
        None,
    )


def _build_subtitle_translation_payload(
    *,
    localized_credits: Sequence[TmdbCreditPerson],
    reference_credits: Sequence[TmdbCreditPerson],
) -> dict[str, object] | None:
    trusted_name_map = _build_trusted_person_name_map(
        localized_credits=localized_credits,
        reference_credits=reference_credits,
    )
    if not trusted_name_map:
        return None
    return {
        "trusted_name_map": trusted_name_map,
        "source_priority": ("tmdb_zh_cn_credits", "original_name_fallback"),
    }


def _build_trusted_person_name_map(
    *,
    localized_credits: Sequence[TmdbCreditPerson],
    reference_credits: Sequence[TmdbCreditPerson],
) -> dict[str, str]:
    localized_by_person_id = _aggregate_credit_truth_by_person_id(localized_credits)
    reference_by_person_id = _aggregate_credit_truth_by_person_id(reference_credits)
    trusted_name_map: dict[str, str] = {}
    for reference in reference_by_person_id.values():
        localized = localized_by_person_id.get(reference.person_id)
        if localized is None:
            continue
        _add_trusted_name_mapping(
            trusted_name_map,
            source_name=reference.name,
            localized_name=localized.name,
        )
        _add_trusted_name_mapping(
            trusted_name_map,
            source_name=reference.original_name,
            localized_name=localized.name,
        )
        _add_trusted_name_mapping(
            trusted_name_map,
            source_name=reference.character,
            localized_name=localized.character,
        )
    return trusted_name_map


def _build_cast_truth(
    *,
    localized_credits: Sequence[TmdbCreditPerson],
    reference_credits: Sequence[TmdbCreditPerson],
) -> list[dict[str, object]]:
    localized_by_person_id = _aggregate_credit_truth_by_person_id(localized_credits)
    reference_by_person_id = _aggregate_credit_truth_by_person_id(reference_credits)
    source_credits = tuple(reference_by_person_id.values()) or tuple(localized_by_person_id.values())
    cast_truth: list[dict[str, object]] = []
    seen_people: set[str] = set()
    for source_credit in sorted(source_credits, key=lambda item: (item.order, item.person_id, item.name.casefold())):
        person_id = source_credit.person_id.strip()
        if not person_id or person_id in seen_people:
            continue
        reference = reference_by_person_id.get(person_id, source_credit)
        localized = localized_by_person_id.get(person_id, source_credit)
        resolved_character = (localized.character or reference.character).strip()
        if not resolved_character:
            continue
        resolved_name = (localized.name or reference.name or reference.original_name).strip()
        if not resolved_name:
            continue
        profile_path = (localized.profile_path or reference.profile_path).strip()
        cast_truth.append(
            {
                "id": person_id,
                "name": resolved_name,
                "original_name": (reference.original_name or reference.name or resolved_name).strip(),
                "character": resolved_character,
                "original_character": reference.character.strip(),
                "department": (localized.department or reference.department).strip(),
                "job": (localized.job or reference.job).strip(),
                "order": localized.order if localized.order or localized.order == 0 else reference.order,
                "profile_path": profile_path,
                "profile_image_url": _build_tmdb_image_url(profile_path),
            }
        )
        seen_people.add(person_id)
    return cast_truth


def _aggregate_credit_truth_by_person_id(
    credits: Sequence[TmdbCreditPerson],
) -> dict[str, TmdbCreditPerson]:
    grouped_credits: dict[str, list[TmdbCreditPerson]] = {}
    for credit in credits:
        person_id = credit.person_id.strip()
        if not person_id:
            continue
        grouped_credits.setdefault(person_id, []).append(credit)
    aggregated: dict[str, TmdbCreditPerson] = {}
    for person_id, person_credits in grouped_credits.items():
        aggregated[person_id] = _merge_credit_truth_rows(person_credits)
    return aggregated


def _merge_credit_truth_rows(
    credits: Sequence[TmdbCreditPerson],
) -> TmdbCreditPerson:
    ordered_credits = sorted(credits, key=_credit_truth_priority, reverse=True)
    cast_like_credits = [credit for credit in ordered_credits if credit.character.strip()]
    primary_credit = (cast_like_credits or ordered_credits)[0]
    resolved_name = _pick_credit_text(ordered_credits, field_name="name", prefer_chinese=True)
    resolved_original_name = _pick_credit_text(ordered_credits, field_name="original_name")
    resolved_character = _pick_credit_text(cast_like_credits, field_name="character", prefer_chinese=True)
    resolved_profile_path = _pick_credit_text(cast_like_credits or ordered_credits, field_name="profile_path")
    resolved_department = _pick_credit_text(cast_like_credits, field_name="department")
    resolved_job = _pick_credit_text(cast_like_credits, field_name="job")
    return TmdbCreditPerson(
        person_id=primary_credit.person_id,
        name=resolved_name or resolved_original_name,
        original_name=resolved_original_name or resolved_name,
        character=resolved_character,
        department=resolved_department,
        job=resolved_job,
        order=primary_credit.order,
        profile_path=resolved_profile_path,
    )


def _pick_credit_text(
    credits: Sequence[TmdbCreditPerson],
    *,
    field_name: str,
    prefer_chinese: bool = False,
) -> str:
    if prefer_chinese:
        for credit in credits:
            value = getattr(credit, field_name).strip()
            if value and _contains_cjk(value):
                return value
    for credit in credits:
        value = getattr(credit, field_name).strip()
        if value:
            return value
    return ""


def _credit_truth_priority(credit: TmdbCreditPerson) -> tuple[int, int, int, int, int]:
    return (
        1 if credit.character.strip() else 0,
        1 if credit.profile_path.strip() else 0,
        1 if credit.original_name.strip() else 0,
        1 if credit.name.strip() else 0,
        -credit.order,
    )


def _add_trusted_name_mapping(
    trusted_name_map: dict[str, str],
    *,
    source_name: str,
    localized_name: str,
) -> None:
    cleaned_source = source_name.strip()
    cleaned_localized = localized_name.strip()
    if not cleaned_source or not cleaned_localized:
        return
    if cleaned_source == cleaned_localized:
        return
    if not _contains_cjk(cleaned_localized):
        return
    trusted_name_map.setdefault(cleaned_source, cleaned_localized)


def _contains_cjk(value: str) -> bool:
    return re.search(r"[\u4e00-\u9fff]", value) is not None


def _resolve_write_strategy_for_path(*, artifact_path: Path, default_strategy: str) -> str:
    if default_strategy == WRITE_STRATEGY_OVERWRITE:
        return WRITE_STRATEGY_OVERWRITE
    if default_strategy == WRITE_STRATEGY_MISSING_ONLY and artifact_path.exists():
        return WRITE_STRATEGY_SKIP
    return default_strategy
